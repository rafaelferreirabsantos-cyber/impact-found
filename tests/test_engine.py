"""Testes de regressão com dados ARTIFICIAIS, usados APENAS para validar código.
Não confundir com o retorno real do fundo; nenhum fixture é distribuído como backtest.
"""
import unittest
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.engine import Parameters,simulate,calc_signals,export_results


def fixture():
    rng=np.random.default_rng(1011)
    dates=pd.bdate_range('2021-01-01',periods=430)
    tickers=[f'TICK{i:02d}' for i in range(16)]
    sectors=['Financeiro','Indústria','Consumo','Utilidades']
    market=[]
    for i,t in enumerate(tickers):
        sig=0.0002+0.00022*i
        vola=0.006+0.00015*(i%5)
        vals=100*np.exp(np.cumsum(rng.normal(sig,vola,len(dates))))
        raw=vals*1.2
        for j,d in enumerate(dates):market.append({'date':d,'ticker':t,'adj_close':vals[j],'close':raw[j],'volume':3_000_000})
    universe=pd.DataFrame({'ticker':tickers,'sector':[sectors[i%4] for i in range(16)],
                           'issuer':[f'ISSUER{i:02d}' for i in range(16)]})
    cdi=pd.Series(0.0004,index=dates,name='cdi_return')
    benchmark=pd.Series(np.linspace(100,160,len(dates)),index=dates,name='benchmark_price')
    p=Parameters(n_assets=8,min_holdings=8,sector_cap=0.5,issuer_cap=0.125,
       momentum_long=90,momentum_skip=10,vol_window=21,adv_window=15,min_adv_brl=1_000_000,
       execution_cost_bps=20)
    return pd.DataFrame(market),cdi,universe,benchmark,p

class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m,cls.cdi,cls.uni,cls.bench,cls.p=fixture()

    def test_signal_and_selection(self):
        p=self.p;m=self.m
        adj=m.pivot(index='date',columns='ticker',values='adj_close')
        close=m.pivot(index='date',columns='ticker',values='close')
        volume=m.pivot(index='date',columns='ticker',values='volume')
        sig=adj.index[290]
        f,chosen=calc_signals(sig,adj,close,volume,self.uni,p)
        self.assertEqual(len(chosen),8)
        self.assertTrue((f.score>=0).all() and (f.score<=1).all())
        ref=f.iloc[0]
        expected=p.momentum_weight*ref.momentum_pct+(1-p.momentum_weight)*ref.lowvol_pct
        self.assertAlmostEqual(ref.score,expected)
        sectors=dict(self.uni.set_index('ticker').sector)
        self.assertLessEqual(max(sum(sectors[t]==sec for t in chosen) for sec in set(sectors.values())),4)

    def test_execution_one_session_after_signal(self):
        daily,holdings,trades,metrics,quality=simulate(self.m,self.cdi,self.uni,self.p,self.bench)
        self.assertGreater(len(daily),100)
        self.assertTrue((holdings.weight==1/self.p.n_assets).all())
        dates=sorted(pd.to_datetime(self.m.date.unique()))
        for sig,ex in holdings[['signal_date','execution_date']].drop_duplicates().itertuples(index=False,name=None):
            s=pd.Timestamp(sig);e=pd.Timestamp(ex)
            self.assertEqual(e,dates[dates.index(s)+1])
        self.assertGreater(daily.cost_brl.sum(),0)
        self.assertTrue(np.isfinite(daily.nav_brl).all())
        self.assertGreater(float(daily.nav_brl.min()),0)
        self.assertEqual(quality['universe_mode'][:4],'FIXO')
        self.assertIsNotNone(metrics['ibov_return_total'])
        self.assertEqual(len(holdings)%8,0)

    def test_cost_reduces_nav(self):
        low=replace(self.p,execution_cost_bps=0)
        high=replace(self.p,execution_cost_bps=40)
        d0,_,_,_,_=simulate(self.m,self.cdi,self.uni,low)
        d1,_,_,_,_=simulate(self.m,self.cdi,self.uni,high)
        self.assertLess(d1.nav_brl.iloc[-1],d0.nav_brl.iloc[-1])
        self.assertEqual(d0.cost_brl.sum(),0)
        self.assertGreater(d1.cost_brl.sum(),0)
        self.assertLessEqual(d1.cash_weight.max(),1.000001)
        self.assertGreaterEqual(d1.cash_weight.min(),-0.000001)

    def test_future_price_does_not_change_prior_signal(self):
        adj=self.m.pivot(index='date',columns='ticker',values='adj_close')
        close=self.m.pivot(index='date',columns='ticker',values='close')
        volume=self.m.pivot(index='date',columns='ticker',values='volume')
        dt=adj.index[290];future=adj.index[291]
        out1=calc_signals(dt,adj,close,volume,self.uni,self.p)
        adj2=adj.copy();adj2.loc[future,'TICK01']*=50
        out2=calc_signals(dt,adj2,close,volume,self.uni,self.p)
        self.assertEqual(out1[1],out2[1])
        pd.testing.assert_frame_equal(out1[0],out2[0])

    def test_snapshots_and_missing_stale(self):
        adj=self.m.pivot(index='date',columns='ticker',values='adj_close')
        close=self.m.pivot(index='date',columns='ticker',values='close')
        volume=self.m.pivot(index='date',columns='ticker',values='volume')
        dt=adj.index[290]
        members={dt-pd.Timedelta(days=5):set(self.uni.ticker[:12])}
        ranked,chosen=calc_signals(dt,adj,close,volume,self.uni,replace(self.p,min_holdings=6),members)
        self.assertTrue(set(chosen).issubset(members[next(iter(members))]))
        with self.assertRaises(ValueError):calc_signals(dt,adj,close,volume,self.uni,self.p,{dt-pd.Timedelta(days=160):set(self.uni.ticker)})

    def test_missing_cdi_rejected(self):
        # Missing CDI is never silently replaced by zero, which would flatter the strategy.
        missing_date = self.cdi.index[300]
        bad_cdi = self.cdi.drop(missing_date)
        with self.assertRaisesRegex(ValueError, 'CDI indisponível'):
            simulate(self.m, bad_cdi, self.uni, self.p)

    def test_export_format(self):
        d,h,t,m,q=simulate(self.m,self.cdi,self.uni,self.p)
        with tempfile.TemporaryDirectory() as tmp:
            path=export_results(Path(tmp),d,h,t,m,q,self.p)
            import json
            payload=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(payload['type'],'backtest_historico')
            self.assertEqual(len(payload['history']),len(d))
            self.assertEqual(len(payload['latest_holdings']),8)
            self.assertTrue((Path(tmp)/'ordens_e_custos.csv').exists())

    def test_export_sale_with_missing_score_is_json_null(self):
        d,h,t,m,q=simulate(self.m,self.cdi,self.uni,self.p)
        t.loc[0,'score']=np.nan  # Venda de ativo que deixou o conjunto elegível.
        with tempfile.TemporaryDirectory() as tmp:
            path=export_results(Path(tmp),d,h,t,m,q,self.p)
            import json
            payload=json.loads(path.read_text(encoding='utf-8'))
            self.assertIsNone(payload['trades'][0]['score'])

    def test_cdi_includes_bank_day_without_equity_session(self):
        d,_,_,_,_=simulate(self.m,self.cdi,self.uni,self.p)
        # Remover uma sessão de mercado da fixture, preservando a taxa oficial.
        bank_day=d.index[40]
        no_session=self.m.loc[self.m.date.ne(bank_day)]
        result,_,_,_,_=simulate(no_session,self.cdi,self.uni,self.p)
        after=result.index[result.index>bank_day][0]
        self.assertAlmostEqual(result.loc[after,'cdi_daily'],1.0004**2-1)
        expected=(1+self.cdi.loc[(self.cdi.index>result.index[0])&(self.cdi.index<=result.index[-1])]).prod()
        self.assertAlmostEqual(result.cdi_index.iloc[-1]/self.p.initial_nav,expected)

    def test_held_price_gap_is_never_filled(self):
        d,h,_,_,_=simulate(self.m,self.cdi,self.uni,self.p)
        first=h.iloc[0]
        day=d.index[d.index>pd.Timestamp(first.execution_date)][0]
        bad=self.m.loc[~(self.m.date.eq(day)&self.m.ticker.eq(first.ticker))]
        with self.assertRaisesRegex(ValueError,'Preço ajustado ausente'):
            simulate(bad,self.cdi,self.uni,self.p)

    def test_complete_lookback_is_required(self):
        adj=self.m.pivot(index='date',columns='ticker',values='adj_close')
        close=self.m.pivot(index='date',columns='ticker',values='close')
        volume=self.m.pivot(index='date',columns='ticker',values='volume')
        adj.loc[adj.index[250],'TICK00']=np.nan
        ranked,_=calc_signals(adj.index[290],adj,close,volume,self.uni,self.p)
        self.assertNotIn('TICK00',ranked.ticker.tolist())

    def test_order_at_close_gets_no_same_day_asset_return(self):
        d,h,_,_,_=simulate(self.m,self.cdi,self.uni,self.p)
        first_execution=pd.Timestamp(h.execution_date.min())
        self.assertEqual(d.index[1],first_execution)
        self.assertAlmostEqual(d.nav_brl.iloc[0],self.p.initial_nav)
        expected=self.p.initial_nav*(1+d.loc[first_execution,'cdi_daily'])/(1+self.p.execution_cost_bps/10000)
        self.assertAlmostEqual(d.loc[first_execution,'nav_brl'],expected,places=3)

    def test_future_prices_do_not_change_prior_nav_or_trades(self):
        d,h,t,_,_=simulate(self.m,self.cdi,self.uni,self.p)
        cutoff=d.index[100]
        changed=self.m.copy()
        changed.loc[changed.date>cutoff,['adj_close','close']]*=1.5
        d2,h2,t2,_,_=simulate(changed,self.cdi,self.uni,self.p)
        pd.testing.assert_frame_equal(d.loc[:cutoff],d2.loc[:cutoff])
        pd.testing.assert_frame_equal(t.loc[t.execution_date<=str(cutoff.date())],t2.loc[t2.execution_date<=str(cutoff.date())])

    def test_issuer_cap_is_enforced_even_with_fewer_slots(self):
        d,h,t,_,_=simulate(self.m,self.cdi,self.uni,replace(self.p,issuer_cap=0.05,min_holdings=1,n_assets=20))
        self.assertLessEqual(h.groupby(['execution_date','issuer']).weight.sum().max(),.05+1e-10)

if __name__=='__main__':unittest.main()
