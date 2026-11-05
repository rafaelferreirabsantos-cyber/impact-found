"""Auditoria reproduzível: cotações/volume oficial B3 contra o cache Yahoo.

Não cria preços para ativos ausentes. Correções são registradas linha a linha.
Execute depois do download: python -m src.audit_sources
"""
from pathlib import Path
import hashlib
import json
import zipfile
import requests
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def read_cotahist(path, tickers):
    rows=[]
    with zipfile.ZipFile(path) as archive:
        with archive.open(archive.namelist()[0]) as stream:
            for line in stream:
                # COTAHIST: registro 01, mercado à vista 010, moeda BRL.
                if line[:2]!=b'01' or line[24:27]!=b'010':continue
                ticker=line[12:24].decode('latin-1').strip()
                if ticker not in tickers:continue
                rows.append((line[2:10].decode(),ticker,int(line[108:121])/100,
                             int(line[152:170]),int(line[170:188])/100,
                             line[230:242].decode('latin-1')))
    frame=pd.DataFrame(rows,columns=['date','ticker','b3_close','b3_volume','turnover_brl','isin'])
    frame['date']=pd.to_datetime(frame.date,format='%Y%m%d')
    if frame.duplicated(['date','ticker']).any():raise ValueError('B3: cotações duplicadas')
    return frame


def audit_market(out,refresh=False):
    out=Path(out); raw=ROOT/'work'/'b3_raw';raw.mkdir(parents=True,exist_ok=True)
    market=pd.read_csv(out/'cache_precos_yahoo.csv',parse_dates=['date'])
    events=pd.read_csv(out/'eventos_corporativos_yahoo.csv',parse_dates=['date'])
    frames=[];manifest=[]
    for year in range(market.date.min().year,market.date.max().year+1):
        path=raw/f'COTAHIST_A{year}.ZIP'
        url=f'https://bvmf.bmfbovespa.com.br/InstDados/SerHist/{path.name}'
        if not path.exists() or (refresh and year==market.date.max().year):
            # O primeiro arquivo foi baixado durante a investigação do salto UGPA3.
            prior=ROOT/'work'/path.name
            if prior.exists() and year<market.date.max().year:path.write_bytes(prior.read_bytes())
            else:
                response=requests.get(url,timeout=90);response.raise_for_status()
                if not response.content.startswith(b'PK'):raise ValueError(f'B3: resposta não ZIP {year}')
                path.write_bytes(response.content)
        frames.append(read_cotahist(path,set(market.ticker)))
        manifest.append({'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(f'B3 {year}: {len(frames[-1])} registros de ações',flush=True)
    b3=pd.concat(frames,ignore_index=True)
    b3=b3.loc[b3.date.between(market.date.min(),market.date.max())]
    b3.to_csv(out/'cotacoes_b3_auditoria.csv',index=False)
    # Yahoo inclui algumas linhas sem negócios em feriados locais. Usar somente
    # sessões com negociação confirmada no arquivo oficial, sem criar pregões.
    off_calendar=market.loc[~market.date.isin(b3.date.unique())]
    off_calendar.to_csv(out/'registros_fora_calendario_b3.csv',index=False)
    market=market.loc[market.date.isin(b3.date.unique())].copy()
    data=market.drop(columns=['turnover_brl'],errors='ignore').merge(b3,on=['date','ticker'],how='left',validate='one_to_one')
    data['b3_close_split_adjusted']=data.b3_close.copy()
    for ticker,group in events.loc[events.stock_splits.gt(0)].groupby('ticker'):
        for event in group.itertuples():
            mask=data.ticker.eq(ticker)&data.date.lt(event.date)
            data.loc[mask,'b3_close_split_adjusted']/=event.stock_splits
    data['relative_price_difference']=data.close/data.b3_close_split_adjusted-1
    differences=data.loc[data.relative_price_difference.abs().gt(.03)].copy()
    differences.to_csv(out/'divergencias_yahoo_b3.csv',index=False)
    # Defeito confirmado: prefixo UGPA3 indevidamente dividido por ~2,1703,
    # inclusive o volume na base inversa. B3 não registra split em 28/06/2021.
    # Preservar fator de dividendos AdjClose/Close; restaurar base de splits B3.
    correction=data.ticker.eq('UGPA3')&data.date.lt('2021-06-28')&data.relative_price_difference.abs().gt(.03)
    patches=data.loc[correction].copy()
    if len(patches):
        ratio=patches.b3_close_split_adjusted/patches.close
        if not ratio.between(2.15,2.18).all():raise ValueError('UGPA3: divergência diferente da falha investigada')
        data.loc[correction,'adj_close']*=ratio
        data.loc[correction,'close']=patches.b3_close_split_adjusted
        # Yahoo volume é expresso na base de splits atual.
        data.loc[correction,'volume']=patches.b3_volume*(patches.b3_close/patches.b3_close_split_adjusted)
        patches['corrected_adj_close']=data.loc[correction,'adj_close']
        patches['corrected_close']=data.loc[correction,'close']
        patches['corrected_volume']=data.loc[correction,'volume']
    patches.to_csv(out/'correcoes_precos_b3.csv',index=False)
    other=differences.loc[~differences.index.isin(patches.index)]
    columns=['date','ticker','adj_close','close','volume','turnover_brl']
    data[columns].to_csv(out/'cache_precos_auditados.csv',index=False)
    summary={'b3_files':manifest,'b3_matched_rows':int(data.b3_close.notna().sum()),
             'discarded_non_session_dates':sorted(off_calendar.date.dt.strftime('%Y-%m-%d').unique()),
             'discarded_non_session_rows':len(off_calendar),
             'market_rows':len(data),'turnover_proxy_rows':int(data.turnover_brl.isna().sum()),
             'corrected_ugpa3_rows':len(patches),'other_divergent_rows':len(other),
             'other_divergent_tickers':sorted(other.ticker.unique()),
             'comparison_note':'Diferença entre Close Yahoo e fechamento B3 ajustado apenas por splits não prova erro: direitos de subscrição, cisões e reduções de capital podem alterar a base Yahoo. BRAP4/MGLU3 foram preservados; não há reconciliação independente integral desses eventos.',
             'method':'UGPA3: base de splits oficial B3 multiplicada pelo fator de dividendos Yahoo AdjClose/Close; demais preços Yahoo preservados. ADV: volume financeiro B3 quando disponível; close × volume Yahoo nos demais registros.',
             'corporate_actions_note':'Ajustes Yahoo são retrospectivos e não são base point-in-time; eventos não foram todos auditados junto a cada emissor.'}
    (out/'auditoria_fontes.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='b3_files'},ensure_ascii=True,indent=2))


if __name__=='__main__':audit_market(ROOT/'output')
