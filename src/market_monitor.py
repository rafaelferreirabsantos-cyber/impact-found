"""ImpactUFSCar Found: cotações observadas + valorização INDICATIVA da carteira simulada.

Não executa ordens, não cria cota real e não supõe cotação em tempo real.
Provedores:
  brapi       - API B3 de terceiros; exige BRAPI_TOKEN para a carteira completa.
  yahoo_eod   - fechamento diário de pesquisa (NÃO intraday nem tempo real).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import time
import requests
import pandas as pd

TZ_UTC = timezone.utc
_BR_TICKER = re.compile(r'^[A-Z0-9]{4,8}$')
PUBLIC_Brapi = {'PETR4', 'VALE3', 'MGLU3', 'ITUB4'}


def utcnow():
    return datetime.now(TZ_UTC).isoformat(timespec='seconds')


def as_utc_string(value):
    if not value:
        return None
    try:
        stamp = pd.to_datetime(value, utc=True)
        if pd.isna(stamp): return None
        return stamp.isoformat()
    except Exception:
        return None


def normalize_symbol(raw):
    value = str(raw).strip().upper().replace('.SA', '')
    if not _BR_TICKER.fullmatch(value):
        raise ValueError(f'Ticker inválido: {raw!r}')
    return value


def parse_brapi_quote(doc: dict, ticker: str, req_utc: str) -> dict:
    """Preserva hora da fonte, em vez de tratar a hora do request como hora da negociação."""
    results = doc.get('results', [])
    if not isinstance(results, list) or not results:
        raise ValueError(f'Resposta brapi sem cotações para {ticker}')
    r = next((x for x in results if x.get('symbol', '').upper() == ticker), results[0])
    last = r.get('regularMarketPrice')
    if last is None or not isinstance(last,(int,float)) or last <= 0:
        raise ValueError(f'Preço de {ticker} inválido na resposta brapi')
    market_time = as_utc_string(r.get('regularMarketTime'))
    if not market_time:
        raise ValueError(f'Cotação {ticker} não informou horário; recusada para monitoramento')
    prev = r.get('regularMarketPreviousClose')
    prev = float(prev) if isinstance(prev,(int,float)) and prev>0 else None
    change = r.get('regularMarketChangePercent')
    change = float(change) if isinstance(change,(int,float)) else (100*(float(last)/prev-1) if prev else None)
    return {'ticker':ticker, 'price_brl':float(last),'previous_close_brl':prev,
            'change_pct':change,'market_time_utc':market_time,'requested_at_utc':req_utc,
            'source':'brapi', 'frequency_note':'Atraso depende do plano; gratuito ~30 min',
            'volume':r.get('regularMarketVolume')}


def fetch_brapi(tickers: list[str], *, token: str | None=None,
                timeout:float=12.0, session=None, max_workers:int=3) -> tuple[list[dict],list[dict]]:
    """No plano Free a API suporta UM ticker por request. Ausência de token não libera todos."""
    tickers=list(dict.fromkeys(normalize_symbol(t) for t in tickers))
    token = token if token is not None else os.environ.get('BRAPI_TOKEN','').strip()
    s=session or requests.Session()
    headers={'Accept':'application/json','User-Agent':'ImpactUFSCarFoundResearch/4.0'}
    if token:headers['Authorization']='Bearer '+token
    quotes=[];errors=[]
    def get_one(ticker):
        if not token and ticker not in PUBLIC_Brapi:
            return None, {'ticker':ticker,'reason':'token BRAPI_TOKEN necessário para este ticker'}
        url=f'https://brapi.dev/api/quote/{ticker}'
        last_error=None
        for attempt in range(2):
            try:
                r=s.get(url,headers=headers,timeout=timeout)
                if r.status_code==429:
                    raise RuntimeError('limite de requisições (HTTP 429)')
                r.raise_for_status()
                return parse_brapi_quote(r.json(),ticker,utcnow()),None
            except Exception as exc:
                last_error=str(exc)[:300]
                if attempt==0: time.sleep(0.2)
        return None, {'ticker':ticker,'reason':last_error}
    with ThreadPoolExecutor(max_workers=max(1,min(4,max_workers))) as ex:
        futures={ex.submit(get_one,t):t for t in tickers}
        for fut in as_completed(futures):
            quote,error=fut.result()
            if quote: quotes.append(quote)
            if error: errors.append(error)
    quotes.sort(key=lambda x:x['ticker'])
    errors.sort(key=lambda x:x['ticker'])
    return quotes,errors


def fetch_yahoo_eod(tickers:list[str]) -> tuple[list[dict],list[dict]]:
    """Alternativa explícita: últimos fechamentos diários, nunca tick-by-tick."""
    import yfinance as yf
    results=[];errors=[]
    for ticker in sorted(set(normalize_symbol(x) for x in tickers)):
        try:
            df=yf.download(ticker+'.SA',period='7d',interval='1d',auto_adjust=False,
                           progress=False,threads=False,timeout=15)
            if df.empty: raise ValueError('sem observações Yahoo')
            df.columns=df.columns.get_level_values(0) if isinstance(df.columns,pd.MultiIndex) else df.columns
            close=df['Close'].dropna()
            if close.empty: raise ValueError('sem fechamento')
            px=float(close.iloc[-1]); prev=float(close.iloc[-2]) if len(close)>1 else None
            dt=pd.Timestamp(close.index[-1]); dt=dt.tz_localize('America/Sao_Paulo') if dt.tzinfo is None else dt
            results.append({'ticker':ticker,'price_brl':px,'previous_close_brl':prev,
                'change_pct':100*(px/prev-1) if prev else None,
                'market_time_utc':dt.tz_convert('UTC').isoformat(),
                'requested_at_utc':utcnow(),'source':'yahoo_eod',
                'frequency_note':'Fechamento diário (end-of-day); NÃO é cotação intradiária',
                'volume':None})
        except Exception as exc: errors.append({'ticker':ticker,'reason':str(exc)[:300]})
    return results,errors


def reconstruct_positions(report:dict, market_csv:str|Path) -> tuple[list[dict],dict]:
    """Valoriza a ÚLTIMA composição ao último fechamento ajustado, como no backtest.

    'shares' no backtest são unidades ajustadas; NÃO usar essas quantidades como ações reais.
    Faz o ajuste por razão de adjusted close para calcular pesos simulados em D.
    """
    holdings=report.get('latest_holdings') or []
    history=report.get('history') or []
    if not holdings or not history: raise ValueError('Relatório sem carteira/PL do backtest')
    last=history[-1]
    df=pd.read_csv(market_csv,usecols=['date','ticker','adj_close','close'])
    df['date']=pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df['ticker']=df['ticker'].str.upper().str.replace('.SA','',regex=False)
    df=df.drop_duplicates(['date','ticker'])
    latest_dt=last['date']; cash_total=0.0
    positions=[]
    for row in holdings:
        t=row['ticker']; exday=row['execution_date']
        exe=df.loc[(df.date==exday)&(df.ticker==t)]
        px=df.loc[(df.date==latest_dt)&(df.ticker==t)]
        if len(exe)!=1 or len(px)!=1:
            raise ValueError(f'Preço de {t} ausente em {exday} ou {latest_dt}')
        ep=float(exe.adj_close.iloc[0]); lp=float(px.adj_close.iloc[0]); close=float(px.close.iloc[0])
        if min(ep,lp,close)<=0:raise ValueError('Preço inválido em posição')
        curr=float(row['notional_brl'])*lp/ep
        positions.append({'ticker':t,'weight_at_last_close':curr/float(last['nav']),
                          'notional_at_last_close_brl':curr,'reference_close_brl':close,
                          'reference_date':latest_dt,'signal_date':row['signal_date'],
                          'last_rebalance_date':exday,'sector':row['sector']})
    stock_value=sum(x['notional_at_last_close_brl'] for x in positions)
    cash_total=float(last['nav'])-stock_value
    if cash_total < -max(20,float(last['nav'])*1e-4):
        raise ValueError('Reconstrução resultou em caixa negativo além da tolerância')
    return positions, {'base_date':latest_dt,'nav_base_brl':float(last['nav']),
                       'equities_brl':stock_value,'cash_base_brl':max(0,cash_total),
                       'notes':'Pesos indicativos reconstruídos a partir da última carteira do backtest; sem negociação efetiva.'}


def build_snapshot(quote_rows:list[dict], errors:list[dict], *,
                   report:dict|None=None, market_csv:str|Path|None=None,
                   provider:str='brapi') -> dict:
    """Calcula variação desde o último fechamento CONHECIDO, sem inventar preços faltantes."""
    now=utcnow()
    obj={'schema':'impact-market-snapshot/1','kind':'cotacoes_observadas',
         'provider':provider,'fetched_at_utc':now, 'quotes':quote_rows,
         'errors':errors,'requested_count':len(quote_rows)+len(errors),
         'covered_count':len(quote_rows),'portfolio':None,
         'disclaimer':'Cotações de terceiros com possível atraso. Valorização indicativa de uma CARTEIRA SIMULADA; não é cota real e não representa ordens executadas.'}
    if not report or not market_csv:
        obj['status']='cotacoes_sem_backtest';return obj
    try:
        positions,base=reconstruct_positions(report,market_csv)
        qmap={x['ticker']:x for x in quote_rows}
        table=[];covered=0;mark_to_market=0.0
        for x in positions:
            row=dict(x);q=qmap.get(x['ticker'])
            if not q:
                row.update({'quote_brl':None,'change_since_close_pct':None,'quote_time_utc':None,'marked_brl':None})
            else:
                # Data anterior ao fechamento de referência não serve como atualização.
                stamp=pd.to_datetime(q['market_time_utc'], utc=True)
                quote_br_date=stamp.tz_convert('America/Sao_Paulo').date().isoformat()
                if quote_br_date < base['base_date']:
                    row.update({'quote_brl':None,'change_since_close_pct':None,'quote_time_utc':q['market_time_utc'],'marked_brl':None,'warning':'Cotação anterior à base do backtest'})
                else:
                    r=q['price_brl']/x['reference_close_brl']-1
                    val=x['notional_at_last_close_brl']*(1+r)
                    row.update({'quote_brl':q['price_brl'], 'change_since_close_pct':100*r,
                        'quote_time_utc':q['market_time_utc'], 'marked_brl':val})
                    covered+=1;mark_to_market+=val
            table.append(row)
        summary={**base,'positions':table,'covered_positions':covered,'total_positions':len(table),
                 'coverage_pct':100*covered/len(table)}
        if covered==len(table) and covered>0:
            est=mark_to_market+base['cash_base_brl']
            summary.update({'indicative_nav_brl':est,
                            'indicative_change_since_base_pct':100*(est/base['nav_base_brl']-1),
                            'valuation_status':'COMPLETE_ESTIMATE',
                            'valuation_note':'Estimativa por último preço vs. fechamento-base: não incorpora juros intradiários, proventos, spread e slippage.'})
        else:
            summary.update({'indicative_nav_brl':None, 'indicative_change_since_base_pct':None,
                            'valuation_status':'INCOMPLETE',
                            'valuation_note':'Cobertura de preços incompleta ou antiga; estimativa TOTAL bloqueada para evitar resultado falso.'})
        obj['portfolio']=summary
        obj['status']='ok' if covered==len(table) else 'parcial'
    except Exception as exc:
        obj['status']='erro_reconstrucao'
        obj['portfolio_error']=str(exc)
    return obj


def save_snapshot(obj:dict, path:str|Path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    tmp.replace(path)
    return path


def get_market_snapshot(root:Path, *, provider:str='brapi', token=None):
    output=root/'output'
    rp=output/'backtest_results.json'
    mp=output/'cache_precos_auditados.csv'
    if not mp.exists():mp=output/'cache_precos_yahoo.csv'
    report=json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else None
    if report and report.get('latest_holdings'):
        tickers=[x['ticker'] for x in report['latest_holdings']]
    else:
        tickers=['PETR4','VALE3','ITUB4','MGLU3']
    if provider=='brapi': quotes,errs=fetch_brapi(tickers,token=token)
    elif provider=='yahoo_eod':quotes,errs=fetch_yahoo_eod(tickers)
    else:raise ValueError('Provedor precisa ser brapi ou yahoo_eod')
    obj=build_snapshot(quotes,errs,report=report,market_csv=mp if mp.exists() else None,provider=provider)
    save_snapshot(obj,output/'market_snapshot.json')
    return obj


def main():
    import argparse
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description='Coleta cotações e marcação indicativa da carteira simulada')
    parser.add_argument('--provider',choices=['brapi','yahoo_eod'],default='brapi')
    parser.add_argument('--output-dir',default=str(root/'output'))
    a=parser.parse_args()
    if Path(a.output_dir).resolve() != (root/'output').resolve():
        raise SystemExit('Diretório de saída personalizado não é suportado neste comando.')
    x=get_market_snapshot(root,provider=a.provider)
    print('Provedor:',x['provider'],'|','cotações recebidas:',x['covered_count'],'/',x['requested_count'])
    if x['portfolio']:
        v=x['portfolio'];print('Cobertura da carteira:',v['covered_positions'],'/',v['total_positions'])
        if v['indicative_nav_brl'] is not None:
            print('PL *indicativo* R$',round(v['indicative_nav_brl'],2))
    print('Arquivo:',root/'output'/'market_snapshot.json')
    if x['errors']:print('Erros (primeiros 5):',x['errors'][:5])

if __name__=='__main__':main()
