"""Regressões da etapa 2. Fixtures artificiais em memória, nunca resultados."""
import unittest
from dataclasses import replace
import numpy as np
import pandas as pd
from test_engine import fixture
from src.engine import simulate
from src.validation import metrics,apply_fees
from src.validation_audit import independent_percentile


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.market,cls.cdi,cls.universe,cls.benchmark,cls.p=fixture()

    def test_percentile_ties_inclusive(self):
        np.testing.assert_allclose(independent_percentile([1,1,3,4]),[1/6,1/6,2/3,1])
        np.testing.assert_allclose(independent_percentile([1,1,3,4],low=True),[5/6,5/6,1/3,0])

    def test_starting_date_cdi_uses_interval_initial_rate(self):
        cdi=self.cdi.copy();cdi[:]=np.linspace(.0001,.0008,len(cdi))
        d,_,_,_,_=simulate(self.market,cdi,self.universe,self.p,cdi_convention='starting_date')
        expected=(1+cdi.loc[(cdi.index>=d.index[0])&(cdi.index<d.index[-1])]).prod()
        self.assertAlmostEqual(d.cdi_index.iloc[-1]/self.p.initial_nav,expected)
        self.assertAlmostEqual(d.cdi_return.iloc[1],cdi.loc[d.index[0]])

    def test_all_eligible_equal_weights_and_same_start(self):
        base,_,_,_,_=simulate(self.market,self.cdi,self.universe,self.p)
        d,h,_,_,_=simulate(self.market,self.cdi,self.universe,self.p,selection_mode='eligible_equal',nav_start=str(base.index[0].date()))
        self.assertEqual(d.index[0],base.index[0])
        self.assertTrue(h.groupby('execution_date').size().eq(16).all())
        self.assertTrue(h.weight.eq(1/16).all())
        self.assertTrue(np.allclose(h.groupby('execution_date').weight.sum(),1))

    def test_cost_callback_matches_identical_fixed_cost(self):
        a,_,ta,_,_=simulate(self.market,self.cdi,self.universe,self.p)
        b,_,tb,_,_=simulate(self.market,self.cdi,self.universe,self.p,cost_model=lambda *args:.002)
        pd.testing.assert_frame_equal(a,b)
        pd.testing.assert_frame_equal(ta,tb)

    def test_starting_cdi_includes_bank_day_without_exchange_session(self):
        bank_day=self.cdi.index[180]
        no_session=self.market.loc[self.market.date.ne(bank_day)]
        rates=self.cdi.copy();rates.loc[bank_day]=.001
        d,_,_,_,_=simulate(no_session,rates,self.universe,self.p,cdi_convention='starting_date')
        after=d.index[d.index>bank_day][0]
        self.assertAlmostEqual(d.loc[after,'cdi_return'],1.0004*1.001-1)

    def test_daily_sector_exposure_includes_price_drift(self):
        d,h,_,_,_=simulate(self.market,self.cdi,self.universe,self.p,record_exposures=True)
        sector=d.filter(like='sector_weight::')
        np.testing.assert_allclose(sector.sum(axis=1)+d.cash_weight,1,atol=1e-10)

    def test_drawdown_includes_initial_capital(self):
        dates=pd.date_range('2024-01-01',periods=3)
        r=pd.Series([-.1,0.,0.],index=dates);rf=pd.Series(0.,index=dates)
        self.assertAlmostEqual(metrics(r,rf)['max_drawdown'],-.1)

    def fee_fixture(self,dates,returns,cdi=None):
        d=pd.DataFrame(index=pd.to_datetime(dates));d['fund_return']=returns
        d['cdi_return']=0. if cdi is None else cdi
        d['nav_brl']=100*(1+d.fund_return).cumprod()
        return d

    def test_zero_fee_overlay_is_identity(self):
        d=self.fee_fixture(['2025-06-27','2025-06-30','2025-07-01'],[0.,.1,-.05])
        f=apply_fees(d,0,0)
        np.testing.assert_allclose(f.net_nav_brl,d.nav_brl)

    def test_management_fee_uses_elapsed_calendar_days(self):
        d=self.fee_fixture(['2024-01-01','2024-12-31'],[0.,0.])
        f=apply_fees(d,.02,0)
        self.assertAlmostEqual(f.net_nav_brl.iloc[-1],98.)

    def test_fee_provision_reverses_and_hwm_prevents_double_charge(self):
        d=self.fee_fixture(['2025-06-26','2025-06-27','2025-06-30','2025-07-01','2025-07-02'],[0.,.1,-.1,.05,.03])
        f=apply_fees(d,0,.2)
        self.assertAlmostEqual(f.performance_provision_brl.iloc[1],2.)
        self.assertEqual(f.performance_provision_brl.iloc[2],0.)
        self.assertEqual(f.performance_crystallized_brl.iloc[2],0.)
        self.assertAlmostEqual(f.hwm_cdi_brl.iloc[-1],100.)

    def test_fee_only_on_excess_above_cdi(self):
        d=self.fee_fixture(['2025-01-02','2025-01-03','2025-01-06'],[0.,.01,.01],[0.,.01,.01])
        f=apply_fees(d,0,.2)
        np.testing.assert_allclose(f.performance_provision_brl,0,atol=1e-12)

    def test_crystallization_deducts_liability_once(self):
        d=self.fee_fixture(['2025-06-27','2025-06-30','2025-07-01'],[0.,.1,0.])
        f=apply_fees(d,0,.2)
        self.assertAlmostEqual(f.performance_crystallized_brl.iloc[1],2.)
        self.assertAlmostEqual(f.net_nav_brl.iloc[1],108.)
        self.assertAlmostEqual(f.net_nav_brl.iloc[2],108.)
        self.assertAlmostEqual(f.hwm_cdi_brl.iloc[2],108.)

    def test_fee_state_does_not_depend_on_future_observations(self):
        d=self.fee_fixture(['2025-06-27','2025-06-30','2025-07-01'],[0.,.1,.05])
        complete=apply_fees(d,0,.2)
        prefix=apply_fees(d.iloc[:2],0,.2)
        pd.testing.assert_frame_equal(complete.iloc[:2],prefix)


if __name__=='__main__':unittest.main()
