"""Ingestão de mercado verificável. Nenhum dado sintético é usado na execução real."""
from __future__ import annotations

from pathlib import Path
import datetime as dt
import time
import json
import pandas as pd
import numpy as np


def _date_col(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if 'date' not in df.columns:
        raise ValueError('CSV sem coluna date (AAAA-MM-DD).')
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    return df


def read_market_csv(path: str | Path) -> pd.DataFrame:
    """CSV long: date,ticker,adj_close,close,volume.
    adj_close: preço ajustado por desdobramentos e dividendos; não substitua por close.
    """
    df = _date_col(pd.read_csv(path))
    required = {'date','ticker','adj_close','close','volume'}
    if not required.issubset(df.columns):
        raise ValueError(f'Market CSV exige colunas: {sorted(required)}')
    df['ticker'] = df['ticker'].str.upper().str.strip().str.replace('.SA','',regex=False)
    for c in ['adj_close','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['adj_close','close','volume'])
    df = df[(df.adj_close > 0) & (df.close > 0) & (df.volume >= 0)]
    if df.duplicated(['date','ticker']).any():
        raise ValueError('Market CSV contém duplicatas (date,ticker).')
    return df.sort_values(['date','ticker']).reset_index(drop=True)


def fetch_yahoo(tickers: list[str], start: str, end: str, cache: Path) -> pd.DataFrame:
    """Baixa Adj Close, Close e Volume do Yahoo Finance via yfinance.
    start é inclusivo; end exclusivo. Cache salvo para auditoria.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError('Instale dependências: pip install -r requirements.txt') from exc
    cache.parent.mkdir(parents=True, exist_ok=True)
    rows=[]
    actions=[]
    errors=[]
    for k in range(0,len(tickers),10):
        batch=tickers[k:k+10]
        names=[t+'.SA' for t in batch]
        try:
            raw=yf.download(names,start=start,end=end,auto_adjust=False,group_by='ticker',
                            actions=True,threads=False,progress=False,repair=False,timeout=22)
        except Exception as exc:
            errors.append(f'Lote {batch}: {exc}')
            continue
        for ticker, yahoo_ticker in zip(batch,names):
            try:
                if isinstance(raw.columns,pd.MultiIndex):
                    if yahoo_ticker in raw.columns.get_level_values(0):
                        frame=raw[yahoo_ticker]
                    elif yahoo_ticker in raw.columns.get_level_values(1):
                        frame=raw.xs(yahoo_ticker,axis=1,level=1)
                    else:
                        raise KeyError('Ticker ausente')
                else:
                    frame=raw
                if not {'Adj Close','Close','Volume'}.issubset(frame.columns):
                    raise ValueError('Adj Close/Close/Volume ausentes')
                temp=frame[['Adj Close','Close','Volume']].copy().dropna(subset=['Adj Close','Close','Volume'])
                if temp.empty:
                    raise ValueError('Histórico vazio; possível ticker descontinuado ou falha da fonte')
                ev=frame.reindex(columns=['Dividends','Stock Splits'],fill_value=0).fillna(0)
                ev=ev.loc[ev.ne(0).any(axis=1)].copy()
                ev.index=pd.to_datetime(ev.index).tz_localize(None).normalize()
                ev=ev.rename_axis('date').reset_index().rename(columns={'Dividends':'dividends','Stock Splits':'stock_splits'})
                ev['ticker']=ticker
                actions.append(ev)
                temp.index=pd.to_datetime(temp.index).tz_localize(None).normalize()
                temp=temp.reset_index().rename(columns={'Date':'date','index':'date',
                       'Adj Close':'adj_close','Close':'close','Volume':'volume'})
                temp['ticker']=ticker
                rows.append(temp[['date','ticker','adj_close','close','volume']])
            except Exception as exc:
                errors.append(f'{ticker}: {exc}')
        print(f'Yahoo: processado lote {k//10+1}, {len(batch)} ativos')
        time.sleep(0.35)
    if not rows:
        raise RuntimeError('Yahoo não retornou preços ajustados. Verifique rede, limite ou tickers. '+str(errors[:5]))
    if errors:
        print('ATENÇÃO: falhas parciais de coleta:', ' | '.join(errors[:15]))
    out=read_market_frame(pd.concat(rows,ignore_index=True))
    out.to_csv(cache,index=False)
    pd.concat(actions,ignore_index=True).to_csv(cache.with_name('eventos_corporativos_yahoo.csv'),index=False)
    cache.with_name('coleta_yahoo.json').write_text(json.dumps({
        'start':start,'end_exclusive':end,'requested':tickers,
        'downloaded':sorted(out.ticker.unique()),'errors':errors,
        'auto_adjust':False,'repair':False,'actions':True,
        'yfinance_version':yf.__version__},ensure_ascii=False,indent=2),encoding='utf-8')
    return out


def read_market_frame(df:pd.DataFrame) -> pd.DataFrame:
    p=Path('_temporary_')
    df=df.copy()
    df['date']=pd.to_datetime(df.date).dt.normalize()
    df['ticker']=df.ticker.astype(str).str.upper().str.replace('.SA','',regex=False)
    for c in ['adj_close','close','volume']:
        df[c]=pd.to_numeric(df[c],errors='coerce')
    df=df.dropna(subset=['adj_close','close','volume'])
    df=df[(df.adj_close>0)&(df.close>0)&(df.volume>=0)]
    if df.duplicated(['date','ticker']).any():
        raise ValueError('Duplicidade date/ticker na fonte de mercado.')
    return df.sort_values(['date','ticker']).reset_index(drop=True)


def read_cdi_csv(path:str|Path) -> pd.Series:
    """CSV date,rate_pct_daily (percentual por dia: 0,04 significa 0,04%)."""
    df=_date_col(pd.read_csv(path))
    if 'rate_pct_daily' not in df.columns:
        raise ValueError('CDI CSV deve ter date,rate_pct_daily.')
    d=pd.to_numeric(df.rate_pct_daily.astype(str).str.replace(',','.',regex=False),errors='coerce') /100.0
    out=pd.Series(d.to_numpy(),index=df.date,name='cdi_return').sort_index()
    if out.index.has_duplicates or out.isna().any() or (out.abs()>0.02).any():
        raise ValueError('CDI tem duplicatas, NAs ou taxas diárias implausíveis.')
    return out


def fetch_cdi_bcb(start:str,end:str,cache:Path)->pd.Series:
    """SGS 12 do Banco Central: Taxa DI diária, em % a.d., endpoint público."""
    import requests
    start_dt=pd.Timestamp(start)
    end_dt=pd.Timestamp(end)-pd.Timedelta(days=1)
    cache.parent.mkdir(parents=True,exist_ok=True)
    frames=[]
    current=start_dt
    while current<=end_dt:
        last=min(current+pd.DateOffset(years=2)-pd.Timedelta(days=1),end_dt)
        url='https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados'
        params={'formato':'json','dataInicial':current.strftime('%d/%m/%Y'),
                'dataFinal':last.strftime('%d/%m/%Y')}
        err=None
        for trial in range(3):
            try:
                r=requests.get(url,params=params,timeout=30,headers={'Accept':'application/json'})
                r.raise_for_status()
                data=r.json()
                if not isinstance(data,list):
                    raise ValueError(f'Resposta inesperada: {str(data)[:200]}')
                if data: frames.append(pd.DataFrame(data))
                err=None
                break
            except Exception as exc:
                err=exc
                time.sleep(1.3*(trial+1))
        if err:
            raise RuntimeError(f'Falha na consulta SGS 12, {current.date()}–{last.date()}: {err}') from err
        current=last+pd.Timedelta(days=1)
    if not frames:
        raise ValueError('BCB SGS 12 não retornou taxas.')
    frame=pd.concat(frames,ignore_index=True)
    result=pd.DataFrame({'date':pd.to_datetime(frame['data'],dayfirst=True).dt.strftime('%Y-%m-%d'),
                         'rate_pct_daily':pd.to_numeric(frame['valor'].str.replace(',','.',regex=False))})
    result.to_csv(cache,index=False)
    return read_cdi_csv(cache)


def read_benchmark_csv(path:str|Path)->pd.Series:
    df=_date_col(pd.read_csv(path))
    if 'adj_close' not in df.columns:
        raise ValueError('Benchmark exige date,adj_close.')
    s=pd.Series(pd.to_numeric(df.adj_close,errors='coerce').to_numpy(),index=df.date,name='benchmark_price').sort_index()
    return s[s>0].loc[~s.index.duplicated()]


def fetch_ibov(start:str,end:str,cache:Path)->pd.Series:
    try:
        import yfinance as yf
        data=yf.download('^BVSP',start=start,end=end,auto_adjust=False,progress=False,threads=False)
        if data.empty:raise RuntimeError('^BVSP vazio')
        if isinstance(data.columns,pd.MultiIndex):
            data.columns=data.columns.get_level_values(0)
        col='Adj Close' if 'Adj Close' in data else 'Close'
        out=pd.Series(data[col].to_numpy().flatten(),index=pd.to_datetime(data.index).tz_localize(None).normalize(),name='benchmark_price')
        out=out.dropna()
        cache.parent.mkdir(parents=True,exist_ok=True)
        pd.DataFrame({'date':out.index,'adj_close':out.values}).to_csv(cache,index=False)
        return out
    except Exception as exc:
        print(f'AVISO: benchmark IBOV indisponível: {exc}')
        return pd.Series(dtype=float,name='benchmark_price')
