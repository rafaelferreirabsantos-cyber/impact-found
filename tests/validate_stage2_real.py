"""Validação independente da execução real da etapa 2, após o pipeline."""
from pathlib import Path
import hashlib,json,sys,zipfile
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.validation import cost_factory,apply_fees
from src.validation_audit import dump

OUT=ROOT/'output'/'validacao_etapa2'
doc=json.loads((OUT/'validacao_resultados.json').read_text(encoding='utf-8'))
market=pd.read_csv(OUT/'precos_etapa2.csv',parse_dates=['date'])
adj=market.pivot(index='date',columns='ticker',values='adj_close')
cdi=pd.read_csv(ROOT/'output'/'cache_cdi_sgs12.csv',parse_dates=['date']).set_index('date').rate_pct_daily/100
score=pd.read_csv(OUT/'scores_mensais_auditados.csv',parse_dates=['signal_date'])
dates=None;details=[]
for strategy,weight in [('multifactor',.75),('momentum',1.),('low_volatility',0.),('eligible_equal',.75)]:
    folder=OUT/'cenarios'/strategy
    d=pd.read_csv(folder/'patrimonio_diario.csv',parse_dates=['date']).set_index('date')
    h=pd.read_csv(folder/'carteiras_mensais.csv',parse_dates=['execution_date','signal_date'])
    t=pd.read_csv(folder/'ordens.csv',parse_dates=['execution_date','signal_date'])
    if dates is None:dates=d.index
    else:assert d.index.equals(dates)
    assert d.nav_brl.gt(0).all() and d.cash_weight.between(-1e-10,1+1e-10).all()
    np.testing.assert_allclose(d.filter(like='sector_weight::').sum(axis=1)+d.cash_weight,1,atol=1e-10)
    if strategy!='eligible_equal':
        assert h.groupby(['execution_date','sector']).weight.sum().max()<=.30+1e-10
        assert h.groupby(['execution_date','issuer']).weight.sum().max()<=.05+1e-10
    for row in h.itertuples():
        s=score.loc[score.signal_date.eq(row.signal_date)].set_index('ticker')
        expected=weight*s.loc[row.ticker,'momentum_pct']+(1-weight)*s.loc[row.ticker,'lowvol_pct']
        assert abs(row.score-expected)<1e-10
        expected_weight=1/len(s) if strategy=='eligible_equal' else .05
        assert abs(row.weight-expected_weight)<1e-10
        pos=adj.index.get_loc(row.signal_date)
        assert row.execution_date==adj.index[pos+1]
    fee=(t.notional_brl.abs()*.002).groupby(t.execution_date).sum()
    np.testing.assert_allclose(d.cost_brl.reindex(fee.index),fee,atol=.02,rtol=0)
    positions=pd.Series(dtype=float);cash=100_000_000.;navs=[];previous=None
    for day in d.index:
        if previous is not None:
            if len(positions):positions*=adj.loc[day,positions.index]/adj.loc[previous,positions.index]
            cash*=float((1+cdi.loc[(cdi.index>=previous)&(cdi.index<day)]).prod())
        nav=cash+positions.sum();selected=h.loc[h.execution_date.eq(day)]
        if len(selected):
            post=nav-float(fee.loc[day]);positions=selected.set_index('ticker').notional_brl
            cash=post-positions.sum();nav=post
        navs.append(nav);previous=day
    error=float(np.max(np.abs(d.nav_brl.to_numpy()-navs)))
    assert error<1.,(strategy,error)
    expected_cdi=(1+cdi.loc[(cdi.index>=d.index[0])&(cdi.index<d.index[-1])]).prod()
    assert abs(expected_cdi-d.cdi_index.iloc[-1]/100_000_000)<1e-10
    details.append({'strategy':strategy,'selected_rows_checked':len(h),'orders_checked':len(t),'max_independent_nav_error_brl':error})

for event in doc['audit']['corporate_events']:
    if 'prefix_scale_factor' in event:
        actual=adj.loc[pd.Timestamp(event['date']),event['ticker']]/adj.loc[pd.Timestamp(event['previous']),event['ticker']]-1
        assert abs(actual-event['independent_return'])<1e-10
for code in ['ibovespa','ibxx']:
    b=pd.read_csv(OUT/f'indice_{code}_b3.csv',parse_dates=['date']).set_index('date').close
    assert b.reindex(dates).notna().all()
for name in ['operational_100m_eta05','operational_100m_eta10','operational_500m_eta05']:
    folder=OUT/'cenarios'/name;trades=pd.read_csv(folder/'ordens.csv');daily=pd.read_csv(folder/'patrimonio_diario.csv',parse_dates=['date']).set_index('date')
    model=cost_factory(market,1. if name.endswith('eta10') else .5)[0]
    expected=[abs(r.notional_brl)*model(r.ticker,abs(r.notional_brl),pd.Timestamp(r.execution_date),pd.Timestamp(r.signal_date)) for r in trades.itertuples()]
    fee=pd.Series(expected).groupby(pd.to_datetime(trades.execution_date)).sum()
    np.testing.assert_allclose(daily.cost_brl.reindex(fee.index),fee,atol=.03,rtol=0)
    assert daily.cash_weight.ge(-1e-10).all()
base_operational=pd.read_csv(OUT/'cenarios'/'operational_100m_eta05'/'patrimonio_diario.csv',parse_dates=['date']).set_index('date')
zero=apply_fees(base_operational,0,0)
np.testing.assert_allclose(zero.net_nav_brl,base_operational.nav_brl,atol=.001,rtol=0)
# Cristalizações são datas conhecidas e pertencem ao calendário oficial da amostra.
fees=apply_fees(base_operational,.02,.20)
for day in fees.index[fees.performance_crystallized_brl.gt(0)]:
    assert day in market.date.values
    prefix=apply_fees(base_operational.loc[:day],.02,.20)
    pd.testing.assert_series_equal(prefix.iloc[-1],fees.loc[day],check_names=False)
originals=['cache_precos_yahoo.csv','cache_precos_auditados.csv','cache_cdi_sgs12.csv','cache_ibov_yahoo.csv',
           'backtest_results.json','patrimonio_diario.csv','carteiras_por_rebalanceamento.csv','ordens_e_custos.csv','metricas.json']
with zipfile.ZipFile(ROOT/'work'/'etapa2'/'etapa1_antes_da_auditoria.zip') as archive:
    for name in originals:
        before=archive.read('output/'+name);after=(ROOT/'output'/name).read_bytes()
        assert hashlib.sha256(before).digest()==hashlib.sha256(after).digest(),name
summary={'status':'PASS','four_strategies_same_dates':True,'corporate_event_returns_reconciled':True,
         'official_benchmarks_complete':True,'cdi_initial_inclusive_final_exclusive':True,
         'variable_cost_ledger_checked':True,'fee_state_causal_and_zero_fee_identity':True,
         'original_stage1_files_unchanged':originals,'checks':details,
         'scope':'Consistência computacional dos dados disponíveis; não elimina viés de sobrevivência nem constitui auditoria integral de custódia/proventos.'}
dump(OUT/'validacao_independente.json',summary)
print(json.dumps(summary,ensure_ascii=True,indent=2))
