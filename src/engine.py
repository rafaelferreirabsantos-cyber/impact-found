"""Backtester diário sem look-ahead: sinais no mês t, execução no pregão t+1 ao fechamento.

O motor utiliza retorno total via adjusted close e pseudo-quantidades (não ações operacionais).
Não simula books, lotes, tributação, taxa de gestão/performance ou impacto não linear.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import json
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Parameters:
    initial_nav:float=100_000_000.0
    n_assets:int=20
    momentum_weight:float=0.75
    sector_cap:float=0.30
    issuer_cap:float=0.05
    momentum_long:int=252
    momentum_skip:int=21
    vol_window:int=63
    adv_window:int=21
    min_adv_brl:float=33_333_334.0
    execution_cost_bps:float=20.0
    max_snapshot_age_days:int=145
    min_holdings:int=8


def load_universe(path:Path)->pd.DataFrame:
    d=pd.read_csv(path,dtype=str)
    need={'ticker','issuer','sector'}
    if not need.issubset(d.columns):raise ValueError(f'Universo deve conter {need}')
    for c in need:d[c]=d[c].astype(str).str.strip()
    d['ticker']=d.ticker.str.upper()
    if d.duplicated('ticker').any():raise ValueError('ticker duplicado na configuração')
    if d[['ticker','issuer','sector']].isna().any().any():raise ValueError('Universo contém campo vazio')
    return d


def load_membership(path:Path):
    d=pd.read_csv(path)
    if not {'date','ticker'}.issubset(d.columns):raise ValueError('Snapshots precisam de date,ticker')
    d['date']=pd.to_datetime(d.date).dt.normalize()
    d['ticker']=d.ticker.astype(str).str.upper().str.replace('.SA','',regex=False)
    groups={pd.Timestamp(day):set(group.ticker) for day,group in d.groupby('date')}
    if not groups:raise ValueError('Snapshots vazios')
    return groups


def _pct_rank(s:pd.Series,ascending:bool=True)->pd.Series:
    # Rank percentílico 0..1, inclusivo nas extremidades. Quanto maior melhor.
    n=len(s)
    if n<=1:return pd.Series(1.0,index=s.index)
    return (s.rank(method='average',ascending=ascending)-1)/(n-1)


def calc_signals(day:pd.Timestamp,adjusted:pd.DataFrame,close:pd.DataFrame,volume:pd.DataFrame,
                 universe:pd.DataFrame,p:Parameters,membership:dict|None=None,
                 turnover_brl:pd.DataFrame|None=None):
    idx=adjusted.index
    loc=idx.get_loc(day)
    if loc < p.momentum_long or loc < p.vol_window or loc < p.adv_window:
        return None
    if membership is not None:
        available=[x for x in membership if x <=day]
        if not available:return None
        asof=max(available)
        if (day-asof).days>p.max_snapshot_age_days:
            raise ValueError(f'Snapshot PIT vencido em {day.date()}: último de {asof.date()}')
        eligible=universe[universe.ticker.isin(membership[asof])].copy()
    else:eligible=universe.copy()
    latest=adjusted.iloc[loc]
    prev=adjusted.iloc[loc-p.momentum_skip]
    old=adjusted.iloc[loc-p.momentum_long]
    mom=prev/old-1
    rets=adjusted.pct_change(fill_method=None)
    vol=rets.iloc[loc-p.vol_window+1:loc+1].std(ddof=1)*np.sqrt(252)
    financial_volume=close*volume if turnover_brl is None else turnover_brl.combine_first(close*volume)
    adv=financial_volume.rolling(p.adv_window,min_periods=p.adv_window).mean().iloc[loc]
    full_history=adjusted.iloc[loc-p.momentum_long:loc+1].notna().all()
    # Requisito: fechamento e histórico disponíveis; liquidez computada sem dados futuros.
    f=pd.DataFrame({'ticker':eligible.ticker})
    f['momentum']=f.ticker.map(mom)
    f['volatility']=f.ticker.map(vol)
    f['adv_brl']=f.ticker.map(adv)
    f=f.merge(eligible[['ticker','sector','issuer']],on='ticker',how='left')
    valid=(f.momentum.notna()&f.volatility.notna()&(f.volatility>0)&
           (f.adv_brl>=p.min_adv_brl)&f.ticker.map(latest).notna()&f.ticker.map(full_history).eq(True))
    f=f.loc[valid].copy()
    if len(f)<p.min_holdings:return None
    f['momentum_pct']=_pct_rank(f.momentum,ascending=True)
    f['lowvol_pct']=_pct_rank(f.volatility,ascending=False)
    f['score']=p.momentum_weight*f.momentum_pct+(1-p.momentum_weight)*f.lowvol_pct
    f=f.sort_values(['score','ticker'],ascending=[False,True]).reset_index(drop=True)
    chosen=[];sectors={};issuers={}
    for row in f.itertuples(index=False):
        # Usar pesos nominais de 1/N; não forçar redistribuição quando <N.
        if (sectors.get(row.sector,0)+1)/p.n_assets > p.sector_cap+1e-10:continue
        if (issuers.get(row.issuer,0)+1)/p.n_assets > p.issuer_cap+1e-10:continue
        chosen.append(row.ticker)
        sectors[row.sector]=sectors.get(row.sector,0)+1
        issuers[row.issuer]=issuers.get(row.issuer,0)+1
        if len(chosen)==p.n_assets:break
    if len(chosen)<p.min_holdings:return None
    return f,chosen


def simulate(market:pd.DataFrame,cdi:pd.Series,universe:pd.DataFrame,p:Parameters,
             benchmark:pd.Series|None=None,membership:dict|None=None,*,
             nav_start:str|None=None,selection_mode:str='ranked',
             cdi_convention:str='ending_date',cost_model=None,record_exposures:bool=False):
    """Returns: (daily_df, holdings_df, trades_df, metrics_dict, quality_dict).

    Para não negociar usando informação futura, sinais no fechamento de fim de mês
    são executados no fechamento do pregão seguinte, gerando retorno a partir da sessão seguinte.
    """
    if not 0<=p.momentum_weight<=1:raise ValueError('momentum_weight deve estar entre 0 e 1')
    if p.n_assets<1 or p.execution_cost_bps<0:raise ValueError('Parâmetros inválidos')
    if market.empty:raise ValueError('Sem preços históricos')
    if selection_mode not in {'ranked','eligible_equal'}:raise ValueError('Modo de seleção inválido')
    if cdi_convention not in {'ending_date','starting_date'}:raise ValueError('Convenção CDI inválida')
    market=market.copy()
    market['date']=pd.to_datetime(market.date).dt.normalize()
    adj=market.pivot(index='date',columns='ticker',values='adj_close').sort_index()
    close=market.pivot(index='date',columns='ticker',values='close').reindex(adj.index)
    volume=market.pivot(index='date',columns='ticker',values='volume').reindex(adj.index)
    # Nenhuma interpolação ou preenchimento de preço: posição sem preço interrompe o cálculo.
    turnover_brl=(market.pivot(index='date',columns='ticker',values='turnover_brl').reindex(adj.index)
                  if 'turnover_brl' in market else None)
    dates=adj.index
    if len(dates)<p.momentum_long+45:raise ValueError('Histórico insuficiente para 252 dias de formação e teste.')
    # Nunca formar no último mês parcial, além de excluir último pregão sem execução futura.
    month_ends=adj.groupby(adj.index.to_period('M')).tail(1).index
    schedules={}
    skipped=[]
    for sig in month_ends:
        if nav_start is not None and sig<pd.Timestamp(nav_start):continue
        pos=dates.get_loc(sig)
        if pos+1>=len(dates):continue
        signals=calc_signals(sig,adj,close,volume,universe,p,membership,turnover_brl)
        if signals is None:
            skipped.append(str(sig.date()))
            continue
        rank,selected=signals
        if selection_mode=='eligible_equal':selected=rank.ticker.tolist()
        schedules[dates[pos+1]]={'signal_date':sig,'selected':selected,'rank':rank}
    if not schedules:raise ValueError('Não foi possível gerar carteiras. Revise liquidez, histórico e snapshots PIT.')
    first_trade=min(schedules)
    start_signal=schedules[first_trade]['signal_date']
    dates=dates[dates>=start_signal]
    missing_cdi=dates.difference(cdi.dropna().index)
    # Nunca presumir CDI zero num pregão com taxa indisponível: isso falsearia o benchmark.
    if len(missing_cdi):
        raise ValueError(f'CDI indisponível em {len(missing_cdi)} pregões, exemplo: '
                         f'{list(missing_cdi[:5])}. Confira fonte ou reduza --end.')
    # Incluir CDI oficial em dias bancários sem pregão B3 (ex.: 24/12),
    # capitalizando todas as taxas em (fechamento anterior, fechamento atual].
    source_cdi=cdi.sort_index().astype(float)
    cdi_daily=pd.Series(0.0,index=dates,name='cdi_daily')
    for previous,current in zip(dates[:-1],dates[1:]):
        mask=((source_cdi.index>=previous)&(source_cdi.index<current) if cdi_convention=='starting_date'
              else (source_cdi.index>previous)&(source_cdi.index<=current))
        cdi_daily.loc[current]=float((1+source_cdi.loc[mask]).prod()-1)
    if (cdi_daily.abs()>0.02).any():raise ValueError('CDI fora de faixa plausível')
    shares={}
    cash=p.initial_nav
    nav_rows=[];trade_rows=[];holding_rows=[]
    previous_date=None
    for date in dates:
        px=adj.loc[date]
        old_values={}
        for t,qty in shares.items():
            if pd.isna(px.get(t,np.nan)):
                raise ValueError(f'Preço ajustado ausente para posição {t} em {date.date()}. '
                                 'Não é possível assumir saída de ativo, dividendos ou preço constante.')
            old_values[t]=float(qty*px[t])
        # Mark-to-market fechamento; CDI acumulado somente na parcela em caixa.
        if previous_date is not None: cash*=1+float(cdi_daily.loc[date])
        pre_nav=cash+sum(old_values.values())
        current_target={t:val/pre_nav for t,val in old_values.items()} if pre_nav>0 else {}
        cost=0.0; turnover=0.0;signal_date=None; chosen=[]
        if date in schedules:
            item=schedules[date]
            selected=item['selected'];signal_date=item['signal_date'];chosen=selected
            target_weight=1/len(selected) if selection_mode=='eligible_equal' else 1/p.n_assets
            weights={t:target_weight for t in selected}
            if px.reindex(selected).isna().any():
                raise ValueError(f'Preço de execução ausente em {date.date()}; não se presume ordem executada.')
            per_notional=p.execution_cost_bps/10000.0
            # Resolver autoconsistentemente base pós custos de transação.
            post_nav=pre_nav
            all_tickers=sorted(set(weights)|set(old_values))
            def fee_for(t,notional):
                rate=per_notional if cost_model is None else cost_model(t,notional,date,signal_date)
                if not np.isfinite(rate) or rate<0:raise ValueError('Custo não finito ou negativo')
                return notional*rate
            for _ in range(60):
                notionals={t:abs(post_nav*weights.get(t,0.0)-old_values.get(t,0.0)) for t in all_tickers}
                traded=sum(notionals.values())
                nxt=pre_nav-sum(fee_for(t,value) for t,value in notionals.items())
                if nxt<=0:raise ValueError('Custo de execução inviável')
                if abs(nxt-post_nav)<0.001:break
                post_nav=nxt
            traded=sum(abs(post_nav*weights.get(t,0.0)-old_values.get(t,0.0))
                       for t in (set(weights)|set(old_values)))
            cost=pre_nav-post_nav
            turnover=traded/(2*pre_nav)
            shares={t:(post_nav*w/px[t]) for t,w in weights.items()}
            cash=post_nav*max(0.0,1-sum(weights.values()))
            pre_nav=post_nav
            scores=item['rank'].set_index('ticker')
            for ticker in sorted(set(weights)|set(old_values)):
                new_w=weights.get(ticker,0.0)
                old_notional=old_values.get(ticker,0.0)
                new_notional=new_w*post_nav
                delta=new_notional-old_notional
                if abs(delta)<0.01:continue
                trade_rows.append({'execution_date':str(date.date()),
                    'signal_date':str(signal_date.date()),'ticker':ticker,
                    'action':'COMPRA' if delta>0 else 'VENDA',
                    'notional_brl':round(delta,2),'target_weight':round(new_w,6),
                    'score':round(float(scores.loc[ticker,'score']),5) if ticker in scores.index else None,
                    'execution_cost_brl':round(fee_for(ticker,abs(delta)),2)})
            for ticker in selected:
                row=scores.loc[ticker]
                holding_rows.append({'execution_date':str(date.date()),
                    'signal_date':str(signal_date.date()),'ticker':ticker,
                    'sector':str(row.sector),'issuer':str(row.issuer),
                    'momentum':float(row.momentum),'volatility':float(row.volatility),
                    'adv_brl':float(row.adv_brl),'score':float(row.score),
                    'weight':weights[ticker],'notional_brl':post_nav*weights[ticker]})
        nav_row={'date':date,'nav_brl':float(pre_nav),'cdi_daily':float(cdi_daily.loc[date]),
                         'cost_brl':float(cost),'one_way_turnover':float(turnover),
                         'n_holdings':len(shares),'cash_weight':cash/pre_nav if pre_nav>0 else np.nan}
        if record_exposures:
            sector_map=universe.set_index('ticker').sector.to_dict()
            for sector in universe.sector.unique():
                nav_row['sector_weight::'+sector]=sum(qty*px[t] for t,qty in shares.items() if sector_map[t]==sector)/pre_nav
        nav_rows.append(nav_row)
        previous_date=date
    daily=pd.DataFrame(nav_rows).set_index('date')
    daily['fund_return']=daily.nav_brl.pct_change().fillna(0.0)
    daily['cdi_index']=p.initial_nav*(1+daily.cdi_daily).cumprod()/(1+daily.cdi_daily.iloc[0])
    daily['cdi_return']=daily.cdi_index.pct_change().fillna(0.0)
    daily['fund_index']=daily.nav_brl/p.initial_nav*100
    daily['cdi_base100']=daily.cdi_index/p.initial_nav*100
    daily['ibov_base100']=np.nan
    if benchmark is not None and not benchmark.empty:
        bp=benchmark.reindex(daily.index)
        if bp.isna().any():
            print('AVISO: IBOV incompleto no período; não será usado como benchmark.')
        else:
            daily['ibov_base100']=bp/bp.iloc[0]*100
    holdings=pd.DataFrame(holding_rows)
    trades=pd.DataFrame(trade_rows)
    metrics=performance_metrics(daily,p)
    quality={'source_price_type':'Adjusted Close (Yahoo Finance ou CSV fornecido)',
       'universe_mode':'SNAPSHOTS PIT (verificar cobertura de deslistados)' if membership is not None else 'FIXO-RETROSPECTIVO (viés de sobrevivência)',
       'snapshot_dates':len(membership) if membership is not None else 0,
       'selection_mode':selection_mode,'cdi_convention':cdi_convention,
       'missing_cdi_sessions':len(missing_cdi),
       'price_fill_method':'Nenhum; lacunas não são interpoladas nem carregadas',
       'cdi_alignment':('Produto de todas as taxas SGS 12 em [fechamento anterior, fechamento atual), incluindo dias bancários sem pregão B3'
                        if cdi_convention=='starting_date' else 'Convenção legada da etapa 1: (fechamento anterior, fechamento atual]'),
       'extra_cdi_dates_between_sessions':int(len(source_cdi.loc[(source_cdi.index>dates[0])&(source_cdi.index<=dates[-1])].index.difference(dates))),
       'configured_assets':len(universe),'downloaded_assets':int(market.ticker.nunique()),
       'missing_assets':sorted(set(universe.ticker)-set(market.ticker)),
       'selected_unique_assets':int(holdings.ticker.nunique()),
       'market_start':str(market.date.min().date()),'market_end':str(market.date.max().date()),
       'first_execution_date':str(first_trade.date()),
       'signal_months_skipped':len(skipped),'example_skipped':skipped[:12],
       'no_realtime_quotes':True,'capacity_filter_adv_brl':p.min_adv_brl,
       'execution':'Sinal no fechamento do mês, execução no fechamento da sessão seguinte',
       'costs':'Custos lineares por nocional transacionado; sem taxas de gestão/performance/tributos',
       'known_limitations':[('Universo fixo de ações atuais induz viés de sobrevivência' if membership is None else 'Snapshots históricos ajudam a reduzir viés, mas é necessário incluir deslistados e dados completos'),
         'Eventos de deslistagem exigem tratamento PIT e série total return íntegra',
         'Execução ao fechamento é proxy; sem simulação microestrutural de book',
         'Sem aportes, resgates, imposto ou taxa de administração/performance']}
    return daily,holdings,trades,metrics,quality


def performance_metrics(daily:pd.DataFrame,p:Parameters)->dict:
    r=daily.fund_return.iloc[1:]
    rf=daily.cdi_return.iloc[1:]
    if r.empty:raise ValueError('Sem dias de carteira')
    years=len(r)/252
    fund_total=float(daily.nav_brl.iloc[-1]/p.initial_nav-1)
    cdi_total=float(daily.cdi_index.iloc[-1]/p.initial_nav-1)
    fund_cagr=(1+fund_total)**(1/years)-1 if years else np.nan
    excess=r-rf
    ann_vol=float(r.std(ddof=1)*np.sqrt(252))
    sharpe=float(np.sqrt(252)*excess.mean()/r.std(ddof=1)) if r.std(ddof=1)>0 else None
    fund_index=daily.fund_index
    dd=fund_index/fund_index.cummax()-1
    losses=np.quantile(r,0.05)
    es=float(-r[r<=losses].mean())
    ibov=daily.ibov_base100.dropna()
    ibov_total=float(ibov.iloc[-1]/ibov.iloc[0]-1) if len(ibov)>1 else None
    return {'start':str(daily.index[0].date()),'end':str(daily.index[-1].date()),
       'observations':len(r),'initial_nav_brl':p.initial_nav,
       'final_nav_brl':float(daily.nav_brl.iloc[-1]),
       'return_total':fund_total,'cdi_return_total':cdi_total,
       'excess_over_cdi_pp':(fund_total-cdi_total)*100,'ibov_return_total':ibov_total,
       'return_annualized':float(fund_cagr),'vol_annualized':ann_vol,
       'sharpe_over_cdi':sharpe,'max_drawdown':float(dd.min()),
       'var_95_one_day':float(-losses),'es_95_one_day':es,
       'total_cost_brl':float(daily.cost_brl.sum()),
       'one_way_turnover_sum':float(daily.one_way_turnover.sum()),
       'rebalance_count':int((daily.one_way_turnover>0).sum()),
       'avg_holdings':float(daily.n_holdings.iloc[1:].mean())}


def export_results(out:Path,daily:pd.DataFrame,holdings:pd.DataFrame,trades:pd.DataFrame,
                   metrics:dict,quality:dict,p:Parameters)->Path:
    out.mkdir(parents=True,exist_ok=True)
    daily.to_csv(out/'patrimonio_diario.csv',float_format='%.10f')
    holdings.to_csv(out/'carteiras_por_rebalanceamento.csv',index=False,float_format='%.8f')
    trades.to_csv(out/'ordens_e_custos.csv',index=False,float_format='%.8f')
    monthly=daily[['nav_brl','cdi_index','ibov_base100']].groupby(daily.index.to_period('M')).last()
    monthly_returns=monthly.pct_change(fill_method=None)
    monthly_returns.iloc[0]=monthly.iloc[0]/daily[['nav_brl','cdi_index','ibov_base100']].iloc[0]-1
    monthly_returns.columns=['fund_return','cdi_return','ibov_return']
    monthly.join(monthly_returns).rename_axis('month').to_csv(out/'retornos_mensais.csv',float_format='%.10f')
    latest=[]
    if not holdings.empty:
        latest=holdings[holdings.execution_date==holdings.execution_date.max()].copy().round(6).to_dict(orient='records')
    history=[]
    for date,row in daily.iterrows():
        history.append({'date':str(date.date()),
          'fund':round(float(row.fund_index),5),'cdi':round(float(row.cdi_base100),5),
          'ibov':round(float(row.ibov_base100),5) if pd.notna(row.ibov_base100) else None,
          'nav':round(float(row.nav_brl),2),
          'n_holdings':int(row.n_holdings),'cash_weight':round(float(row.cash_weight),6)})
    payload={'name':'ImpactUFSCar Found',
         'type':'backtest_historico',
         'simulation_warning':'Pesquisa exploratória; NÃO é rentabilidade de fundo existente ou recomendação.',
         'metrics':metrics,'quality':quality,'parameters':asdict(p),
         'history':history,'latest_holdings':latest,
         'monthly_holdings':holdings.to_dict(orient='records'),
         'trades':trades.tail(180).astype(object).where(trades.tail(180).notna(),None).to_dict(orient='records')}
    result_path=out/'backtest_results.json'
    result_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (out/'metricas.json').write_text(json.dumps({'metrics':metrics,'quality':quality,'parameters':asdict(p)},ensure_ascii=False,indent=2),encoding='utf-8')
    return result_path
