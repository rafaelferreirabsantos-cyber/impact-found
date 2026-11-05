"""Conferência independente dos arquivos produzidos com dados reais.

Execute APÓS o backtest: python tests/validate_real_run.py
Não baixa, cria ou substitui preços. Não faz parte das fixtures unitárias.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'output'
doc=json.loads((out/'backtest_results.json').read_text(encoding='utf-8'))
p=doc['parameters'];metrics=doc['metrics']
market=pd.read_csv(out/'cache_precos_auditados.csv',parse_dates=['date'])
daily=pd.read_csv(out/'patrimonio_diario.csv',parse_dates=['date']).set_index('date')
hold=pd.read_csv(out/'carteiras_por_rebalanceamento.csv',parse_dates=['signal_date','execution_date'])
trades=pd.read_csv(out/'ordens_e_custos.csv',parse_dates=['signal_date','execution_date'])
cdi=pd.read_csv(out/'cache_cdi_sgs12.csv',parse_dates=['date']).set_index('date').rate_pct_daily/100
adj=market.pivot(index='date',columns='ticker',values='adj_close')
b3=pd.read_csv(out/'cotacoes_b3_auditoria.csv',parse_dates=['date'])
assert set(daily.index).issubset(set(b3.date))
assert p['initial_nav']==100_000_000 and p['momentum_weight']==.75
assert p['n_assets']==20 and p['sector_cap']==.3 and p['execution_cost_bps']==20
assert hold.groupby('execution_date').size().max()<=20
assert np.allclose(hold.weight,.05)
assert hold.groupby(['execution_date','sector']).weight.sum().max()<=.3+1e-10
assert hold.groupby(['execution_date','issuer']).weight.sum().max()<=.05+1e-10
assert daily.nav_brl.gt(0).all() and daily.cash_weight.between(-1e-9,1+1e-9).all()
month_ends=set(adj.groupby(adj.index.to_period('M')).tail(1).index)
for row in hold.itertuples():
    signal=pd.Timestamp(row.signal_date);execution=pd.Timestamp(row.execution_date)
    pos=adj.index.get_loc(signal)
    assert signal in month_ends and execution==adj.index[pos+1]
    expected=adj[row.ticker].iloc[pos-21]/adj[row.ticker].iloc[pos-252]-1
    assert abs(row.momentum-expected)<1e-8
    returns=adj[row.ticker].pct_change(fill_method=None).iloc[pos-62:pos+1]
    assert len(returns)==63 and returns.notna().all()
    assert abs(row.volatility-returns.std(ddof=1)*np.sqrt(252))<1e-8
assert np.allclose(trades.execution_cost_brl,trades.notional_brl.abs()*.002,atol=.011)
costs=trades.groupby('execution_date').execution_cost_brl.sum()
assert np.allclose(daily.cost_brl.reindex(costs.index),costs,atol=.1)
independent_costs=(trades.notional_brl.abs()*.002).groupby(trades.execution_date).sum()
expected_cdi=(1+cdi.loc[(cdi.index>daily.index[0])&(cdi.index<=daily.index[-1])]).prod()
assert abs(expected_cdi-daily.cdi_index.iloc[-1]/p['initial_nav'])<1e-10
# Reconstituir o PL com os nocionais das seleções e a valorização ajustada,
# independentemente do laço de execução e da resolução de custos do motor.
positions=pd.Series(dtype=float);cash=p['initial_nav'];navs=[];previous=None
for date in daily.index:
    if previous is not None:
        if len(positions):positions*=adj.loc[date,positions.index]/adj.loc[previous,positions.index]
        cash*=float((1+cdi.loc[(cdi.index>previous)&(cdi.index<=date)]).prod())
    nav=cash+positions.sum()
    selected=hold.loc[hold.execution_date.eq(date)]
    if len(selected):
        post=nav-float(independent_costs.loc[date])
        positions=selected.set_index('ticker').notional_brl
        assert abs(positions.sum()-post*selected.weight.sum())<.1
        cash=post-positions.sum();nav=post
    navs.append(nav);previous=date
max_error=float(np.max(np.abs(daily.nav_brl.to_numpy()-navs)))
assert max_error<1.0, max_error
assert abs(daily.nav_brl.iloc[-1]-metrics['final_nav_brl'])<.01
assert len(doc['monthly_holdings'])==len(hold)
summary={'status':'PASS','real_data_only':True,'monthly_signals_checked':len(hold),
         'rebalances_checked':int(hold.execution_date.nunique()),
         'max_independent_nav_error_brl':max_error,'daily_dates_on_official_b3_calendar':True,
         'momentum_volatility_execution_costs_and_caps':'PASS',
         'cdi_all_official_bank_dates_compounded':'PASS',
         'note':'Conferência de consistência computacional; não é auditoria independente integral da fonte ou de eventos societários.'}
(out/'validacao_execucao_real.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
