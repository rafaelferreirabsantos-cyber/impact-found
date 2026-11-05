"""CLI do ImpactUFSCar Found. Execute: python -m src.run --help"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import hashlib
import platform
import sys
import pandas as pd
from .data_sources import (fetch_yahoo,fetch_cdi_bcb,fetch_ibov,read_market_csv,read_cdi_csv,read_benchmark_csv)
from .engine import Parameters,load_universe,load_membership,simulate,export_results

ROOT=Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    a=argparse.ArgumentParser(description='Backtest histórico 12-1 Momentum + baixa volatilidade | ImpactUFSCar Found')
    a.add_argument('--start',default='2018-01-01',help='Início dos DADOS (a estratégia exige 252 pregões iniciais de aquecimento).')
    a.add_argument('--end',default=pd.Timestamp.today().strftime('%Y-%m-%d'),help='Fim exclusivo do histórico, AAAA-MM-DD.')
    a.add_argument('--market-csv',default=None,help='Em vez de Yahoo: CSV com date,ticker,adj_close,close,volume.')
    a.add_argument('--cdi-csv',default=None,help='Em vez de BCB: CSV com date,rate_pct_daily (%% por DIA).')
    a.add_argument('--benchmark-csv',default=None,help='Em vez de Yahoo IBOV: CSV date,adj_close.')
    a.add_argument('--universe-csv',default=str(ROOT/'config'/'universo_exploratorio.csv'))
    a.add_argument('--membership-csv',default=None,help='Snapshots IBrX: date,ticker, composição completa por data. Ativa modo point-in-time.')
    a.add_argument('--output-dir',default=str(ROOT/'output'))
    a.add_argument('--momentum-weight',type=float,default=0.75)
    a.add_argument('--n-assets',type=int,default=20)
    a.add_argument('--min-holdings',type=int,default=8)
    a.add_argument('--min-adv',type=float,default=33_333_334.0,help='Volume médio financeiro mínimo (R$/dia, janela 21).')
    a.add_argument('--cost-bps',type=float,default=20.0,help='Custo por nocional negociado, em bps. Ex.: 20 = 0,20%%')
    a.add_argument('--refresh',action='store_true',help='Refaz download e ignora cache local.')
    a.add_argument('--audit-json',default=None,help='Relatório de auditoria B3 associado ao CSV de preços.')
    a.add_argument('--skip-b3-audit',action='store_true',help='Desliga conferência B3; dados Yahoo ficam sem a correção conhecida de UGPA3.')
    return a.parse_args(argv)


def main(argv=None):
    a=parse_args(argv)
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    universe=load_universe(Path(a.universe_csv))
    p=Parameters(n_assets=a.n_assets,momentum_weight=a.momentum_weight,
       min_holdings=a.min_holdings,min_adv_brl=a.min_adv,execution_cost_bps=a.cost_bps)
    membership=load_membership(Path(a.membership_csv)) if a.membership_csv else None
    if membership:
        missing=set.union(*membership.values())-set(universe.ticker)
        if missing:raise ValueError('Tickers nos snapshots não presentes em universo_exploratorio.csv: '+str(sorted(missing)[:25]))
    else:
        print('AVISO: universo FIXO composto por ações atualmente conhecidas. Viés de sobrevivência. EXPLORATÓRIO.')
    market_cache=out/'cache_precos_yahoo.csv'
    cdi_cache=out/'cache_cdi_sgs12.csv'
    bench_cache=out/'cache_ibov_yahoo.csv'
    if a.market_csv:
        market=read_market_csv(a.market_csv)
    elif market_cache.exists() and not a.refresh:
        market=read_market_csv(market_cache)
        print('Utilizando cache local de preços.')
    else:
        market=fetch_yahoo(universe.ticker.tolist(),a.start,a.end,market_cache)
    if not a.market_csv and not a.skip_b3_audit:
        from .audit_sources import audit_market
        if not (out/'eventos_corporativos_yahoo.csv').exists():
            market=fetch_yahoo(universe.ticker.tolist(),a.start,a.end,market_cache)
        audit_market(out,refresh=a.refresh)
        market=read_market_csv(out/'cache_precos_auditados.csv')
        a.audit_json=str(out/'auditoria_fontes.json')
    market=market.loc[(market.date>=pd.Timestamp(a.start))&(market.date<pd.Timestamp(a.end))]
    if a.cdi_csv:
        cdi=read_cdi_csv(a.cdi_csv)
    elif cdi_cache.exists() and not a.refresh:
        cdi=read_cdi_csv(cdi_cache)
        print('Utilizando cache local de CDI.')
    else:
        cdi=fetch_cdi_bcb(a.start,a.end,cdi_cache)
    # Banco Central pode atualizar a série depois de Yahoo; truncar sem supor CDI=0.
    last_cdi=cdi.dropna().index.max()
    if pd.isna(last_cdi):raise ValueError('CDI sem histórico utilizável.')
    last_market=market.date.max()
    if last_market>last_cdi:
        print(f'AVISO: CDI termina em {last_cdi.date()} e preços vão até {last_market.date()}; '
              'período reduzido à última taxa CDI disponível para não falsificar benchmark.')
        market=market.loc[market.date<=last_cdi].copy()
    if a.benchmark_csv:benchmark=read_benchmark_csv(a.benchmark_csv)
    elif bench_cache.exists() and not a.refresh:benchmark=read_benchmark_csv(bench_cache)
    else:benchmark=fetch_ibov(a.start,a.end,bench_cache)
    # Etapa 2 confirmou a convenção DI: início inclusivo, fim exclusivo.
    # O parâmetro legado do motor fica disponível para reproduzir a etapa 1.
    daily,holdings,trades,metrics,quality=simulate(market,cdi,universe,p,benchmark,membership,cdi_convention='starting_date')
    quality.update({'data_start_requested':a.start,'data_end_exclusive':a.end,
                    'price_source':'CSV fornecido' if a.market_csv else 'Yahoo Finance via yfinance',
                    'cdi_source':'CSV fornecido' if a.cdi_csv else 'Banco Central SGS 12',
                    'benchmark':'IBOV (Yahoo Finance)' if not a.benchmark_csv else 'CSV fornecido',
                    'run_data_quality_note':'Validação necessária: emissões, mudanças de ticker, dividendos, ITSA4 e listagem de empresas.'})
    if a.audit_json:
        quality['source_audit']=json.loads(Path(a.audit_json).read_text(encoding='utf-8'))
        quality['price_source']='Yahoo Finance (Adj Close) + correção UGPA3 conferida na B3 COTAHIST'
        quality['liquidity_source']='Volume financeiro B3; close × volume Yahoo nas datas sem correspondência de ticker'
        quality['run_data_quality_note']='Conferência de preços contra B3 e eventos Yahoo; não constitui auditoria independente integral de proventos ou base point-in-time.'
    manifest={'command':sys.argv,'python':platform.python_version(),
              'run_at_utc':pd.Timestamp.now(tz='UTC').isoformat(),'inputs':{}}
    for path in [Path(a.market_csv) if a.market_csv else (out/'cache_precos_auditados.csv' if a.audit_json else market_cache),
                 Path(a.cdi_csv) if a.cdi_csv else cdi_cache,
                 Path(a.benchmark_csv) if a.benchmark_csv else bench_cache,
                 Path(a.universe_csv),ROOT/'src'/'engine.py',ROOT/'src'/'data_sources.py',
                 ROOT/'src'/'run.py',ROOT/'src'/'audit_sources.py',ROOT/'dashboard'/'index.html',
                 out/'eventos_corporativos_yahoo.csv',out/'auditoria_fontes.json',out/'cotacoes_b3_auditoria.csv']:
        if path.exists():manifest['inputs'][str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'manifesto_execucao.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    result=export_results(out,daily,holdings,trades,metrics,quality,p)
    from .dashboard_builder import render_dashboard
    validation=out/'validacao_etapa2'/'validacao_resultados.json'
    render_dashboard(result,out/'dashboard_com_resultados.html',validation if validation.exists() else None)
    print('\nBACKTEST FINALIZADO. Dados históricos processados.')
    print('Período:',metrics['start'],'a',metrics['end'])
    print('Retorno acumulado:',f"{100*metrics['return_total']:.2f}%")
    print('CDI acumulado:',f"{100*metrics['cdi_return_total']:.2f}%")
    print('Qualificação do universo:',quality['universe_mode'])
    print('Arquivo de pesquisa:',result)
    print('Dashboard v3 (dados históricos integrados):',out/'dashboard_com_resultados.html')
    print('ATENÇÃO: pesquisa exploratória. Não é fundo real nem performance auditada.')

if __name__=='__main__':main()
