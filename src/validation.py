"""Segunda etapa quantitativa, protocolo congelado, dados e saídas segregados.

python -m src.validation_data
python -m src.validation_audit
python -m src.validation
"""
from dataclasses import replace,asdict
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd
from .engine import Parameters,simulate,load_universe
from .data_sources import read_market_csv,read_cdi_csv
from .validation_data import ROOT,OUT
from .validation_audit import dump

NAMES={'multifactor':'Multifatorial 75/25','momentum':'Momentum 100%',
       'low_volatility':'Baixa volatilidade 100%','eligible_equal':'Equal Weight de todos os elegíveis',
       'ibovespa':'Ibovespa B3','ibrx100':'IBrX 100 B3','cdi':'CDI SGS 12'}


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,(pd.Timestamp,pd.Period)):return str(value)
    return value


def metrics(returns,rf,turnover=None,cost=None,nav_initial=100_000_000):
    r=pd.Series(returns).astype(float);riskfree=pd.Series(rf).reindex(r.index).astype(float)
    if r.isna().any() or riskfree.isna().any() or len(r)<2:raise ValueError('Retornos incompletos')
    excess=r-riskfree;n=len(r);wealth=(1+r).cumprod();total=float(wealth.iloc[-1]-1)
    annual=float((1+total)**(252/n)-1);vol=float(r.std(ddof=1)*np.sqrt(252))
    peak=np.maximum.accumulate(np.r_[1.,wealth.to_numpy()])
    dd=np.r_[1.,wealth.to_numpy()]/peak-1;maxdd=float(dd.min())
    downside=float(np.sqrt(np.mean(np.minimum(excess.to_numpy(),0)**2)))
    return clean({'observations':n,'return_total':total,'return_annualized':annual,
        'cdi_return_total':float((1+riskfree).prod()-1),'vol_annualized':vol,
        'sharpe_over_cdi':float(np.sqrt(252)*excess.mean()/r.std(ddof=1)) if r.std(ddof=1)>1e-14 else None,
        'sortino_over_cdi':float(np.sqrt(252)*excess.mean()/downside) if downside>1e-14 else None,
        'calmar':annual/abs(maxdd) if maxdd<0 else None,'max_drawdown':maxdd,
        'var_95_one_day':float(-r.quantile(.05)),
        'es_95_one_day':float(-r.loc[r<=r.quantile(.05)].mean()),
        'turnover_sum':None if turnover is None else float(pd.Series(turnover).sum()),
        'turnover_annualized':None if turnover is None else float(pd.Series(turnover).sum()*252/n),
        'cost_total_brl':None if cost is None else float(pd.Series(cost).sum()),
        'final_nav_brl':nav_initial*(1+total)})


def apply_fees(daily,management=.02,performance=.20):
    """Provisão reversível e cristalização semestral; benchmark/HWM líquido CDI."""
    assets=float(daily.nav_brl.iloc[0]);hurdle=assets;rows=[];previous=daily.index[0]
    for i,(date,row) in enumerate(daily.iterrows()):
        management_fee=0.;crystallized=0.
        if i:
            assets*=1+row.fund_return
            management_fee=assets*(1-(1-management)**((date-previous).days/365))
            assets-=management_fee;hurdle*=1+row.cdi_return
        provision=performance*max(assets-hurdle,0.)
        # Calendário conhecido, sem consultar a próxima cotação para decidir:
        # último dia útil de junho / último dia útil até 30 de dezembro
        # (31/12 não é pregão B3). Conferido contra as sessões oficiais da amostra.
        crystal_day=(pd.offsets.BDay().rollback(pd.Timestamp(date.year,date.month,30))
                     if date.month in (6,12) else None)
        closes_half=crystal_day is not None and date==crystal_day
        if closes_half:
            crystallized=provision;assets-=crystallized;hurdle=max(hurdle,assets);provision=0.
        rows.append({'date':date,'net_nav_brl':assets-provision,'assets_after_admin_brl':assets,
                     'performance_provision_brl':provision,'hwm_cdi_brl':hurdle,
                     'management_fee_brl':management_fee,'performance_crystallized_brl':crystallized})
        previous=date
    result=pd.DataFrame(rows).set_index('date')
    result['net_return']=result.net_nav_brl.pct_change(fill_method=None).fillna(0.)
    return result


def cost_factory(market,eta=.5):
    adj=market.pivot(index='date',columns='ticker',values='adj_close')
    raw=market.pivot(index='date',columns='ticker',values='close')
    volume=market.pivot(index='date',columns='ticker',values='volume')
    amount=market.pivot(index='date',columns='ticker',values='turnover_brl').combine_first(raw*volume)
    adv=amount.rolling(21,min_periods=21).mean()
    sigma=adj.pct_change(fill_method=None).rolling(63,min_periods=63).std(ddof=1)
    def model(ticker,notional,date,signal):
        a=float(adv.loc[signal,ticker]);s=float(sigma.loc[signal,ticker])
        if not np.isfinite(a) or a<=0 or not np.isfinite(s):raise ValueError(f'Impacto sem ADV/volatilidade: {ticker} {signal}')
        return (5+5)/10000+eta*s*np.sqrt(notional/a)
    return model,adv,sigma,amount


def capacity(trades,daily,adv,amount):
    result=trades.copy()
    result['adv_known_brl']=[adv.loc[pd.Timestamp(r.signal_date),r.ticker] for r in result.itertuples()]
    result['actual_execution_turnover_brl']=[amount.loc[pd.Timestamp(r.execution_date),r.ticker] for r in result.itertuples()]
    result['participation_adv']=result.notional_brl.abs()/result.adv_known_brl
    result['participation_execution_volume']=result.notional_brl.abs()/result.actual_execution_turnover_brl
    result['days_at_10pct_adv']=np.ceil(result.participation_adv/.10)
    result['nav_brl']=[daily.loc[pd.Timestamp(day),'nav_brl'] for day in result.execution_date]
    result['order_fraction_nav']=result.notional_brl.abs()/result.nav_brl
    result['capacity_nav_at_10pct_brl']=.10*result.adv_known_brl/result.order_fraction_nav
    result.to_csv(OUT/'capacidade_ordens_multifatorial.csv',index=False)
    return clean({'orders':len(result),'max_participation_adv':result.participation_adv.max(),
        'p95_participation_adv':result.participation_adv.quantile(.95),
        'max_participation_actual_day':result.participation_execution_volume.max(),
        'orders_over_5pct_adv':int(result.participation_adv.gt(.05).sum()),
        'orders_over_10pct_adv':int(result.participation_adv.gt(.10).sum()),
        'orders_over_20pct_adv':int(result.participation_adv.gt(.20).sum()),
        'max_days_at_10pct_adv':result.days_at_10pct_adv.max(),
        'min_instantaneous_nav_capacity_at_10pct_brl':result.capacity_nav_at_10pct_brl.min(),
        'approx_initial_nav_capacity_at_10pct_brl':100_000_000*.1/result.participation_adv.max(),
        'note':'Capacidade indicativa baseada em ADV e ordens da trajetória de R$ 100 milhões iniciais; não garante liquidez nem preenchimento. Não se diluiu artificialmente a ordem em sessões posteriores.'})


def paired_bootstrap(dailies):
    monthly={}
    for name,data in dailies.items():
        monthly[name]=data.fund_return.groupby(data.index.to_period('M')).apply(lambda r:(1+r).prod()-1)
    frame=pd.DataFrame(monthly)
    # Janeiro/2019 é só a base, novembro/2026 é parcial; evitar compará-los a meses inteiros.
    frame=frame.loc[(frame.index>pd.Period('2019-01'))&(frame.index<pd.Period('2026-11'))]
    rng=np.random.default_rng(20261105);n=len(frame);block=6
    choices=rng.integers(0,n-block+1,size=(2000,math.ceil(n/block)))
    index=(choices[:,:,None]+np.arange(block)[None,None,:]).reshape(2000,-1)[:,:n]
    rows=[]
    for name in ['momentum','low_volatility','eligible_equal','ibovespa','ibrx100','cdi']:
        diff=(frame.multifactor-frame[name]).to_numpy()
        samples=diff[index].mean(axis=1)*12
        low,high=np.quantile(samples,[.025,.975])
        rows.append({'comparison':'multifactor_minus_'+name,'complete_months':n,'block_months':block,
                     'annualized_arithmetic_mean_difference':diff.mean()*12,
                     'ci95_low':low,'ci95_high':high,'includes_zero':bool(low<=0<=high)})
    pd.DataFrame(rows).to_csv(OUT/'incerteza_bootstrap_pareado.csv',index=False)
    return clean(rows)


def period_analysis(dailies,benchmark):
    annual=[];regime_rows=[];temporal=[];sector_rows=[];sector_regimes=[]
    returns=benchmark.pct_change(fill_method=None)
    trend=(benchmark.shift(1)/benchmark.shift(127)-1).ge(0)
    risk=(returns.shift(1).rolling(63,min_periods=63).std(ddof=1)*np.sqrt(252)).gt(.25)
    labels=pd.Series(np.where(trend,'Alta','Baixa'),index=benchmark.index)+' / '+pd.Series(np.where(risk,'Vol >25%','Vol ≤25%'),index=benchmark.index)
    labels.rename('regime_conhecido_ate_t_menos_1').to_csv(OUT/'regimes_predefinidos.csv')
    intervals={'desenvolvimento_retrospectivo':('2019-01-31','2022-12-31'),
               'validacao_retrospectiva':('2023-01-01','2024-12-31'),
               'holdout_ja_observado':('2025-01-01','2026-11-04')}
    for name,data in dailies.items():
        rf=data.cdi_return
        for year in sorted(data.index.year.unique()):
            mask=(data.index.year==year)&(data.index>data.index[0]);sample=data.loc[mask]
            record=metrics(sample.fund_return,rf.loc[mask],None if 'one_way_turnover' not in data else sample.one_way_turnover,
                           None if 'cost_brl' not in data else sample.cost_brl)
            annual.append({'strategy':name,'year':int(year),'partial_year':year in [2019,2026],**record})
            for col in data.columns:
                if col.startswith('sector_weight::'):
                    sector_rows.append({'strategy':name,'year':int(year),'sector':col.split('::')[1],
                                        'average_weight':sample[col].mean(),'maximum_weight':sample[col].max(),'last_weight':sample[col].iloc[-1]})
        for label in sorted(labels.reindex(data.index).unique()):
            mask=labels.reindex(data.index).eq(label)&(data.index>data.index[0]);sample=data.loc[mask]
            if len(sample)<2:continue
            record=metrics(sample.fund_return,sample.cdi_return,
                           None if 'one_way_turnover' not in sample else sample.one_way_turnover,
                           None if 'cost_brl' not in sample else sample.cost_brl)
            # Drawdown apenas dentro de cada trecho contíguo do regime.
            groups=mask.ne(mask.shift()).cumsum();worst=0.
            for _,part in data.loc[mask].groupby(groups.loc[mask]):
                vals=np.r_[1.,(1+part.fund_return).cumprod().to_numpy()]
                worst=min(worst,float((vals/np.maximum.accumulate(vals)-1).min()))
            record['max_drawdown']=worst
            record['calmar']=None  # Razão em regime descontínuo não tem interpretação temporal homogênea.
            regime_rows.append({'strategy':name,'regime':label,'drawdown_definition':'pior trecho contíguo',**record})
            for col in sample.columns:
                if col.startswith('sector_weight::'):
                    sector_regimes.append({'strategy':name,'regime':label,'sector':col.split('::')[1],
                                           'average_weight':sample[col].mean(),'maximum_weight':sample[col].max()})
        for label,(start,end) in intervals.items():
            sample=data.loc[(data.index>=start)&(data.index<=end)&(data.index>data.index[0])]
            temporal.append({'strategy':name,'period':label,'start':str(sample.index.min().date()),'end':str(sample.index.max().date()),
                             **metrics(sample.fund_return,sample.cdi_return)})
    for filename,rows in [('metricas_por_ano.csv',annual),('metricas_por_regime.csv',regime_rows),('diagnostico_temporal_retrospectivo.csv',temporal),('exposicao_setorial_por_ano.csv',sector_rows),('exposicao_setorial_por_regime.csv',sector_regimes)]:
        pd.DataFrame(rows).to_csv(OUT/filename,index=False)
    return clean({'annual':annual,'regimes':regime_rows,'temporal':temporal,'sectors':sector_rows,'sectors_by_regime':sector_regimes})


def run():
    audit=json.loads((OUT/'auditoria_etapa2.json').read_text(encoding='utf-8'))
    if audit['score_and_causality_original']['status']!='PASS':raise ValueError('Auditoria de score pendente')
    protocol=json.loads((ROOT/'config'/'validacao_etapa2_protocolo.json').read_text(encoding='utf-8'))
    registered=json.loads((OUT/'protocolo_registrado.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256((ROOT/'config'/'validacao_etapa2_protocolo.json').read_bytes()).hexdigest()
    if digest!=registered['protocol_sha256']:raise ValueError('Protocolo alterado após registro')
    market=read_market_csv(OUT/'precos_etapa2.csv');cdi=read_cdi_csv(ROOT/'output'/'cache_cdi_sgs12.csv')
    universe=load_universe(ROOT/'config'/'universo_exploratorio.csv')
    ibov=pd.read_csv(OUT/'indice_ibovespa_b3.csv',parse_dates=['date']).set_index('date').close
    ibxx=pd.read_csv(OUT/'indice_ibxx_b3.csv',parse_dates=['date']).set_index('date').close
    p=Parameters();dailies={};summaries=[];case_results={}
    def calculate(name,params=p,mode='ranked',model=None,keep=True):
        folder=OUT/'cenarios'/name;folder.mkdir(parents=True,exist_ok=True)
        d,h,t,_,q=simulate(market,cdi,universe,params,ibov,nav_start=protocol['nav_start'],
            selection_mode=mode,cdi_convention='starting_date',cost_model=model,record_exposures=keep)
        d.to_csv(folder/'patrimonio_diario.csv');h.to_csv(folder/'carteiras_mensais.csv',index=False);t.to_csv(folder/'ordens.csv',index=False)
        stat=metrics(d.fund_return.iloc[1:],d.cdi_return.iloc[1:],d.one_way_turnover.iloc[1:],d.cost_brl.iloc[1:],params.initial_nav)
        stat.update({'strategy':name,'label':NAMES.get(name,name),'initial_nav_brl':params.initial_nav,
                     'avg_holdings':float(d.n_holdings.iloc[1:].mean()),'rebalance_count':int(h.execution_date.nunique()),
                     'sector_max_target':float(h.groupby(['execution_date','sector']).weight.sum().max()),
                     'issuer_max_target':float(h.groupby(['execution_date','issuer']).weight.sum().max()),
                     'start':str(d.index[0].date()),'end':str(d.index[-1].date())})
        if d.index[0]!=pd.Timestamp(protocol['nav_start']):raise ValueError('Cenário saiu do período comparável')
        dump(folder/'metricas.json',clean(stat));print('Calculado:',name,flush=True)
        case_results[name]=(d,h,t,stat)
        return d,h,t,stat
    for name,weight,mode in [('multifactor',.75,'ranked'),('momentum',1.,'ranked'),('low_volatility',0.,'ranked'),('eligible_equal',.75,'eligible_equal')]:
        d,h,t,stat=calculate(name,replace(p,momentum_weight=weight),mode)
        dailies[name]=d;summaries.append(stat)
    reference=dailies['multifactor'];dates=reference.index
    for name,price in [('ibovespa',ibov),('ibrx100',ibxx),('cdi',reference.cdi_index)]:
        aligned=price.reindex(dates)
        if aligned.isna().any():raise ValueError(f'Benchmark {name} sem cobertura completa; não preencher')
        d=pd.DataFrame(index=dates);d['nav_brl']=p.initial_nav*aligned/aligned.iloc[0]
        d['fund_return']=d.nav_brl.pct_change(fill_method=None).fillna(0.);d['cdi_return']=reference.cdi_return
        dailies[name]=d
        stat=metrics(d.fund_return.iloc[1:],d.cdi_return.iloc[1:]);stat.update({'strategy':name,'label':NAMES[name],
            'start':str(dates[0].date()),'end':str(dates[-1].date()),'initial_nav_brl':p.initial_nav,
            'note':'Índice teórico sem custos de replicação, taxas ou ordens próprias; não carteira investível com custos iguais aos das quatro estratégias.'})
        summaries.append(stat)
    pd.DataFrame(summaries).to_csv(OUT/'comparacao_estrategias.csv',index=False)
    wealth=pd.DataFrame({name:d.nav_brl for name,d in dailies.items()});wealth.rename_axis('date').to_csv(OUT/'patrimonios_comparados.csv')
    analysis=period_analysis(dailies,ibov)
    uncertainty=paired_bootstrap(dailies)
    sensitivity=[]
    for key,values in protocol['sensitivity_one_factor_at_a_time'].items():
        baseline=getattr(p,key)
        for value in values:
            if value==baseline:stat=case_results['multifactor'][3]
            elif key=='momentum_weight' and value==1.:stat=case_results['momentum'][3]
            else:
                _,_,_,stat=calculate(f'sens_{key}_{str(value).replace(".","p")}',replace(p,**{key:value}),keep=False)
            sensitivity.append({'parameter':key,'value':value,'is_baseline':value==baseline,**stat})
    pd.DataFrame(sensitivity).to_csv(OUT/'sensibilidade_sem_otimizacao.csv',index=False)
    model,adv,sigma,amount=cost_factory(market,.5)
    capacity_summary=capacity(case_results['multifactor'][2],reference,adv,amount)
    operations=[]
    for name,params,model_spec in [('multifactor_gross',replace(p,execution_cost_bps=0),None),
        ('operational_100m_eta05',p,model),('operational_100m_eta10',p,cost_factory(market,1.)[0]),
        ('operational_500m_eta05',replace(p,initial_nav=500_000_000),model)]:
        _,_,_,stat=calculate(name,params,model=model_spec);operations.append(stat)
    base_operational=case_results['operational_100m_eta05'][0]
    fees=[]
    for admin,perf in protocol['fees']['annual_management_performance_pairs']:
        label=f'admin_{admin}_performance_{perf}'
        fee_frame=apply_fees(base_operational,admin,perf)
        fee_frame.to_csv(OUT/f'taxas_{label}.csv')
        stat=metrics(fee_frame.net_return.iloc[1:],base_operational.cdi_return.iloc[1:])
        fees.append({'scenario':label,'management_annual':admin,'performance_rate':perf,
            'management_fee_total_brl':float(fee_frame.management_fee_brl.sum()),
            'performance_paid_total_brl':float(fee_frame.performance_crystallized_brl.sum()),
            'performance_pending_brl':float(fee_frame.performance_provision_brl.iloc[-1]),**stat})
    pd.DataFrame(operations).to_csv(OUT/'cenarios_operacionais.csv',index=False)
    pd.DataFrame(fees).to_csv(OUT/'cenarios_taxas.csv',index=False)
    dump(OUT/'capacidade_resumo.json',capacity_summary)
    history=[{'date':str(date.date()),**{name:float(dailies[name].loc[date,'nav_brl']/p.initial_nav*100) for name in dailies}} for date in dates]
    result={'schema':'impact-validation/2.0','status':audit['status'],'protocol_sha256':digest,
        'period':{'start':str(dates[0].date()),'end':str(dates[-1].date()),'returns':len(dates)-1},
        'audit':audit,'protocol':protocol,'comparisons':summaries,'history':history,
        'sensitivity':sensitivity,'analysis':analysis,'uncertainty':uncertainty,
        'capacity':capacity_summary,'operational':operations,'fees':fees,
        'conclusion_status':'CONDICIONAL; sem alpha validado, sem teste prospectivo observado, sem comprovação de capacidade executável',
        'warnings':['Mesmos 47 códigos retrospectivos; viés de sobrevivência não resolvido.',
                    'Proventos e pagamentos não integralmente reconstruídos; preços de referência ainda sujeitos a revisão.',
                    'Índices oficiais são referências teóricas sem custo de replicação.',
                    'Retorno bruto, líquido de negociação e líquido de taxas são cenários separados.']}
    dump(OUT/'validacao_resultados.json',clean(result))
    # Manifesto após finalizar os cálculos. Não altera o protocolo previamente registrado.
    files=[ROOT/'config'/'validacao_etapa2_protocolo.json',ROOT/'src'/'engine.py',ROOT/'src'/'validation.py',
           ROOT/'src'/'validation_audit.py',ROOT/'src'/'validation_data.py',OUT/'precos_etapa2.csv',
           ROOT/'output'/'cache_cdi_sgs12.csv',OUT/'indice_ibovespa_b3.csv',OUT/'indice_ibxx_b3.csv']
    dump(OUT/'manifesto_calculo.json',{'protocol_sha256':digest,'files':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(pd.DataFrame(summaries)[['strategy','return_annualized','vol_annualized','sharpe_over_cdi','max_drawdown']].to_string(index=False))
    return result


if __name__=='__main__':run()
