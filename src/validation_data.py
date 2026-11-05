"""Fontes oficiais e independentes para a segunda etapa. Sem preços sintéticos."""
from pathlib import Path
import base64,hashlib,json
import requests
import pandas as pd
from .audit_sources import read_cotahist

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'/'validacao_etapa2'


def fetch_index(code,start_year=2018,end_year=2026):
    folder=OUT/'fontes'/'indices_b3';folder.mkdir(parents=True,exist_ok=True)
    rows=[];sources=[]
    for year in range(start_year,end_year+1):
        path=folder/f'{code}_{year}.json'
        payload={'language':'pt-br','index':code,'year':str(year)}
        url='https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/'+base64.b64encode(json.dumps(payload).encode()).decode()
        if not path.exists():
            response=requests.get(url,timeout=35);response.raise_for_status();data=response.json()
            if not data.get('results'):raise ValueError(f'B3 {code} {year}: sem resultados')
            path.write_text(response.text,encoding='utf-8')
        data=json.loads(path.read_text(encoding='utf-8'))
        for item in data['results']:
            for month in range(1,13):
                raw=item.get(f'rateValue{month}')
                if raw is None or str(raw).strip() in ('','-'):continue
                date=pd.Timestamp(year=year,month=month,day=int(item['day']))
                if date>=pd.Timestamp('2026-11-05'):continue
                value=float(str(raw).replace('.','').replace(',','.'))
                if value<=0:raise ValueError('Índice não positivo')
                rows.append((date,value))
        sources.append({'index':code,'year':year,'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(f'Índice oficial {code} {year}: recebido',flush=True)
    frame=pd.DataFrame(rows,columns=['date','close']).sort_values('date')
    if frame.date.duplicated().any():raise ValueError('Índice B3 duplicado')
    frame.to_csv(OUT/f'indice_{code.lower()}_b3.csv',index=False)
    return frame.set_index('date').close,sources


def missing_tickers():
    tickers={'CPLE6','CPLE5','CPLE3','BRFS3','MRFG3','MBRF3','JBSS3','JBSS32'}
    frames=[]
    for year in range(2018,2027):
        frames.append(read_cotahist(ROOT/'work'/'b3_raw'/f'COTAHIST_A{year}.ZIP',tickers))
        print('Históricos B3 dos códigos ausentes:',year,flush=True)
    frame=pd.concat(frames,ignore_index=True)
    frame=frame.loc[frame.date.lt('2026-11-05')]
    frame.to_csv(OUT/'historico_codigos_ausentes_b3.csv',index=False)
    coverage=frame.groupby('ticker').agg(first=('date','min'),last=('date','max'),observations=('date','size'),financial_volume_brl=('turnover_brl','sum')).reset_index()
    coverage.to_csv(OUT/'cobertura_codigos_ausentes.csv',index=False)
    return coverage


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=[]
    for code in ['IBXX','IBOVESPA']:
        _,manifest=fetch_index(code);sources.extend(manifest)
    (OUT/'fontes_indices.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
    coverage=missing_tickers()
    print(coverage.to_string(index=False))


if __name__=='__main__':prepare()
