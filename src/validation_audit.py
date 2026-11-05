"""Auditoria prévia à comparação. Preserva a etapa 1 e registra cada ajuste."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib,zipfile
import numpy as np
import pandas as pd
from .engine import Parameters,load_universe,calc_signals
from .data_sources import read_market_csv,read_cdi_csv
from .validation_data import ROOT,OUT


def dump(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def independent_percentile(values,low=False):
    v=np.asarray(values);n=len(v)
    if n<=1:return np.ones(n)
    comparisons=(v[None,:]>v[:,None]) if low else (v[None,:]<v[:,None])
    ties=(v[None,:]==v[:,None]).sum(axis=1)
    return (comparisons.sum(axis=1)+(ties-1)/2)/(n-1)


def corporate_reconciliation(market):
    b3=pd.read_csv(ROOT/'output'/'cotacoes_b3_auditoria.csv',parse_dates=['date']).set_index(['date','ticker'])
    y=market.set_index(['date','ticker']);events=[]
    def official(date,ticker):return float(b3.loc[(pd.Timestamp(date),ticker),'b3_close'])
    def old_return(previous,date,ticker):return float(y.loc[(pd.Timestamp(date),ticker),'adj_close']/y.loc[(pd.Timestamp(previous),ticker),'adj_close']-1)
    # Ação VALE3 a receber, marcada pelo fechamento ex-direito + dividendo a receber.
    target=(official('2021-12-17','BRAP4')+.332373453*official('2021-12-17','VALE3')+6.043850916)/official('2021-12-16','BRAP4')-1
    events.append({'ticker':'BRAP4','previous':'2021-12-16','date':'2021-12-17',
        'description':'Restituição de capital: 0,332373453 VALE3 por BRAP4 + R$ 6,043850916 de dividendo',
        'original_return':old_return('2021-12-16','2021-12-17','BRAP4'),'independent_return':target,
        'status':'CORRIGIDO: marcação econômica de ação e direitos a receber; sem simulação de custódia e pagamento',
        'source_documents':['BRADESPAR_2021-11-11_915967.pdf','BRADESPAR_2021-11-08_914312.pdf','BRADESPAR_2021-12-17_926814.pdf']})
    # Direito MGLU1: fechamento efetivamente negociado, não valor teórico inventado.
    rights=[]
    rights_cache=OUT/'direito_mglu1_b3.csv'
    if rights_cache.exists():rights=pd.read_csv(rights_cache).to_dict(orient='records')
    else:
        with zipfile.ZipFile(ROOT/'work'/'b3_raw'/'COTAHIST_A2024.ZIP') as archive:
            with archive.open(archive.namelist()[0]) as stream:
                for line in stream:
                    if line[:2]==b'01' and line[12:24].strip()==b'MGLU1' and line[2:10]==b'20240201' and line[24:27]==b'010':
                        rights.append({'date':'2024-02-01','ticker':'MGLU1','close':int(line[108:121])/100,'turnover_brl':int(line[170:188])/100})
    if len(rights)!=1:raise ValueError('Não foi possível validar o direito MGLU1 no arquivo B3')
    pd.DataFrame(rights).to_csv(OUT/'direito_mglu1_b3.csv',index=False)
    alpha=.095790177529;issue_price=1.95
    target=(official('2024-02-01','MGLU3')+alpha*rights[0]['close'])/official('2024-01-31','MGLU3')-1
    terp=(official('2024-01-31','MGLU3')+alpha*issue_price)/(1+alpha)
    events.append({'ticker':'MGLU3','previous':'2024-01-31','date':'2024-02-01',
        'description':'Direito 9,5790177529%; subscrição a R$ 1,95; MGLU1 a R$ 0,20 no fechamento B3',
        'original_return':old_return('2024-01-31','2024-02-01','MGLU3'),'independent_return':target,
        'terp_reference_return':official('2024-02-01','MGLU3')/terp-1,
        'status':'CORRIGIDO: ação + direito marcado a mercado; não pressupõe exercício ou venda assegurada',
        'source_documents':['MAGAZINE_2024-01-26_1186895.pdf']})
    for ticker,previous,date,multiplier,source in [
        ('BRAP4','2021-09-20','2021-09-21',1.1295,'BRADESPAR_2021-09-21_902373.pdf'),
        ('MGLU3','2024-05-24','2024-05-27',.1,'MAGAZINE_2024-04-24_1225389.pdf'),
        ('MGLU3','2025-12-29','2025-12-30',1.05,'MAGAZINE_2025-12-22_1460683.pdf')]:
        independent=multiplier*official(date,ticker)/official(previous,ticker)-1
        old=old_return(previous,date,ticker)
        events.append({'ticker':ticker,'previous':previous,'date':date,'description':f'Conversão mecânica de quantidades × {multiplier}',
                       'original_return':old,'independent_return':independent,
                       'status':'RECONCILIADO' if abs(old-independent)<1e-5 else 'DIVERGÊNCIA A INVESTIGAR','source_documents':[source]})
    adjusted=market.copy()
    corrections=[]
    for event in events[:2]:
        # Encadear a série pelo retorno econômico documentado. Escala constante
        # anterior ao evento preserva todos os demais retornos, sem suavização.
        factor=(1+event['original_return'])/(1+event['independent_return'])
        mask=adjusted.ticker.eq(event['ticker'])&adjusted.date.lt(event['date'])
        changed=adjusted.loc[mask,['date','ticker','adj_close']].copy()
        changed['new_adj_close']=changed.adj_close*factor
        changed['event_date']=event['date'];changed['factor']=factor
        corrections.append(changed)
        adjusted.loc[mask,'adj_close']*=factor
        event['prefix_scale_factor']=factor
        event['difference_bps']=(event['original_return']-event['independent_return'])*10000
    pd.concat(corrections,ignore_index=True).to_csv(OUT/'correcoes_corporativas_etapa2.csv',index=False)
    pd.DataFrame(events).to_csv(OUT/'reconciliacao_eventos.csv',index=False)
    adjusted.to_csv(OUT/'precos_etapa2.csv',index=False)
    return adjusted,events


def audit_scores(market,filename='scores_mensais_auditados.csv'):
    universe=load_universe(ROOT/'config'/'universo_exploratorio.csv');p=Parameters()
    adj=market.pivot(index='date',columns='ticker',values='adj_close').sort_index()
    close=market.pivot(index='date',columns='ticker',values='close').reindex(adj.index)
    volume=market.pivot(index='date',columns='ticker',values='volume').reindex(adj.index)
    turnover=market.pivot(index='date',columns='ticker',values='turnover_brl').reindex(adj.index)
    rows=[];max_error=0.;future_checks=0
    for day in adj.groupby(adj.index.to_period('M')).tail(1).index:
        pos=adj.index.get_loc(day)
        if pos+1>=len(adj) or day<pd.Timestamp('2019-01-31'):continue
        result=calc_signals(day,adj,close,volume,universe,p,turnover_brl=turnover)
        if result is None:continue
        rank,selected=result
        # Implementação independente de percentis, sem chamar _pct_rank.
        expected=.75*independent_percentile(rank.momentum)+.25*independent_percentile(rank.volatility,low=True)
        err=float(np.max(np.abs(rank.score.to_numpy()-expected)));max_error=max(max_error,err)
        if err>1e-12:raise AssertionError('Score 75/25 divergente')
        # Truncar inteiramente os dados futuros confirma causalidade do sinal.
        prefix=calc_signals(day,adj.loc[:day],close.loc[:day],volume.loc[:day],universe,p,turnover_brl=turnover.loc[:day])
        pd.testing.assert_frame_equal(rank,prefix[0]);assert selected==prefix[1];future_checks+=1
        exported=rank.copy();exported['signal_date']=day;exported['selected']=exported.ticker.isin(selected);rows.append(exported)
    pd.concat(rows,ignore_index=True).to_csv(OUT/filename,index=False)
    return {'status':'PASS','formula':'0,75 × (rank médio Momentum − 1)/(N − 1) + 0,25 × (rank médio inverso volatilidade − 1)/(N − 1)',
            'max_score_error':max_error,'months_compared_to_truncated_history':future_checks,
            'ranked_rows':int(sum(len(x) for x in rows)),'future_data_algorithm':'Nenhuma diferença após remover todo o histórico posterior ao sinal',
            'point_in_time_warning':'Testar causalidade do algoritmo não elimina composição retrospectiva, setores atuais, revisões posteriores ou ajustes da fonte.'}


def run_audit():
    OUT.mkdir(parents=True,exist_ok=True)
    market=read_market_csv(ROOT/'output'/'cache_precos_auditados.csv')
    original=market.copy()
    score_original=audit_scores(original,'scores_mensais_originais.csv')
    corrected,events=corporate_reconciliation(market)
    cdi=read_cdi_csv(ROOT/'output'/'cache_cdi_sgs12.csv')
    start=pd.Timestamp('2019-01-31');end=pd.Timestamp('2026-11-04')
    old_factor=float((1+cdi.loc[(cdi.index>start)&(cdi.index<=end)]).prod())
    correct_factor=float((1+cdi.loc[(cdi.index>=start)&(cdi.index<end)]).prod())
    b3_index=pd.read_csv(OUT/'indice_ibovespa_b3.csv',parse_dates=['date']).set_index('date').close
    yahoo_index=pd.read_csv(ROOT/'output'/'cache_ibov_yahoo.csv',parse_dates=['date']).set_index('date').adj_close
    comparison=pd.concat([b3_index.rename('b3'),yahoo_index.rename('yahoo')],axis=1).dropna()
    comparison['relative_difference']=comparison.yahoo/comparison.b3-1
    comparison.to_csv(OUT/'auditoria_ibovespa.csv')
    summary={'status':'CONDICIONAL — cálculo auditado, base não integralmente validada',
        'score_and_causality_original':score_original,'corporate_events':events,
        'cdi':{'first_stage_return':old_factor-1,'corrected_return':correct_factor-1,
               'correct_convention':'[fechamento anterior, fechamento atual), início inclusivo/fim exclusivo; Taxa DI de um dia útil',
               'reference':'https://www.b3.com.br/lumis/portal/file/fileDownload.jsp?fileId=8AE490CA7861D39C0178B17E20392164'},
        'survivorship':{'status':'NÃO RESOLVIDO','configured':51,'available_adjusted':47,
            'missing':['CPLE6','BRFS3','JBSS3','MRFG3'],
            'finding':'Os quatro códigos têm preços oficiais B3 no período; falha do fornecedor não é ausência histórica. Preços brutos recuperados não substituem proventos completos e política de conversão. Comparações ficam condicionadas aos mesmos 47 códigos disponíveis.',
            'pit_membership':'Template de composição histórica vazio; não foi inventado universo PIT.'},
        'benchmark_ibov':{'observations_compared':len(comparison),'differences_over_10bps':int(comparison.relative_difference.abs().gt(.001).sum()),
                          'max_abs_relative_difference':float(comparison.relative_difference.abs().max()),'stage2_source':'Fechamentos oficiais B3, sem preencher lacunas'},
        'dividends':{'status':'PARCIAL','accounting':'Retorno ajustado incorpora proventos uma única vez. Não há crédito adicional no caixa. Eventos revisados foram encadeados por riqueza econômica observada.',
                     'remaining':'Não é livro de custódia. Datas de pagamento, reinvestimento implícito, direitos recebidos, impostos e todas as demais operações ainda não estão integralmente reconstruídos.'},
        'execution':{'status':'PASS NO MODELO','signal':'Último pregão do mês, após fechamento','execution':'Fechamento da sessão seguinte, com retorno da nova posição somente no intervalo posterior',
                     'costs':'0,20% por nocional em compras e vendas; custo de liquidação final ausente porque não se vende a carteira no fim',
                     'limitations':'Negociação ao fechamento é proxy; liquidação financeira D+2 e livro de ordens não simulados.'},
        'remaining_price_divergences':'21 observações fora dos dois grandes grupos BRAP4/MGLU3 continuam registradas; diferenças menores que 3% e proventos de todos os emissores não foram integralmente conciliados. Não suavizar nem substituir automaticamente.',
        'reference_candidate':'precos_etapa2.csv; alterações de dados e alinhamento CDI não são otimização de parâmetros',
        'original_artifacts':'Preservados em output/ e work/etapa2/etapa1_antes_da_auditoria.zip'}
    dump(OUT/'auditoria_etapa2.json',summary)
    score_corrected=audit_scores(corrected)
    dump(OUT/'auditoria_scores_corrigidos.json',score_corrected)
    print(json.dumps({'audit_status':summary['status'],'score':score_original,'events':events,'cdi':summary['cdi']},ensure_ascii=True,indent=2))
    return summary


if __name__=='__main__':run_audit()
