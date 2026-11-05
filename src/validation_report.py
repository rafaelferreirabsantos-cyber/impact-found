"""Relatório técnico, figuras e integração local da segunda etapa."""
from pathlib import Path
import base64,hashlib,html,json,shutil,zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from markdown_it import MarkdownIt
from .validation_data import ROOT,OUT
from .validation import NAMES,apply_fees,clean
from .validation_audit import dump
from .dashboard_builder import render_dashboard


def num(v,places=2):
    if v is None or not np.isfinite(v):return '—'
    return f'{v:,.{places}f}'.replace(',','@').replace('.',',').replace('@','.')


def pct(v):return '—' if v is None else num(100*v)+'%'


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in rows)


def figures(doc):
    folder=OUT/'figuras';folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'figure.facecolor':'#FAF7F8','axes.facecolor':'#FFFFFF',
                         'axes.edgecolor':'#D9C9D2','text.color':'#251B25','axes.labelcolor':'#514854',
                         'xtick.color':'#706575','ytick.color':'#706575','grid.color':'#EAE0E5','legend.frameon':False})
    colors={'multifactor':'#B41F44','momentum':'#7963B2','low_volatility':'#178577','eligible_equal':'#706575',
            'ibovespa':'#BA7A28','ibrx100':'#C77A95','cdi':'#4D7B83'}
    wealth=pd.read_csv(OUT/'patrimonios_comparados.csv',parse_dates=['date']).set_index('date')
    fig,axes=plt.subplots(2,1,figsize=(11.8,8.1),sharex=True,gridspec_kw={'height_ratios':[1.6,1]})
    for name in NAMES:
        nav=wealth[name];axes[0].plot(nav.index,nav/1e6,label=NAMES[name],color=colors[name],lw=2 if name=='multifactor' else 1.2)
        axes[1].plot(nav.index,(nav/nav.cummax()-1)*100,color=colors[name],lw=1.6 if name=='multifactor' else 1)
    axes[0].set(title='Comparação histórica condicionada aos mesmos 47 códigos',ylabel='Patrimônio fictício (R$ milhões)')
    axes[0].legend(ncol=3,fontsize=8,loc='upper left');axes[1].set(ylabel='Drawdown (%)')
    for ax in axes:ax.grid(alpha=.7)
    axes[1].xaxis.set_major_locator(mdates.YearLocator(1));axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.text(.08,.015,'31/01/2019–04/11/2026 · Estratégias: 20 bps por nocional · Índices/CDI: referências sem custo de replicação',fontsize=8,color='#706575')
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(folder/'comparacao_patrimonio_drawdown.png',dpi=170);plt.close(fig)
    annual=pd.read_csv(OUT/'metricas_por_ano.csv').pivot(index='strategy',columns='year',values='return_total').reindex(NAMES.keys())*100
    from matplotlib.colors import LinearSegmentedColormap
    cmap=LinearSegmentedColormap.from_list('impact',['#BD4C38','#FFF8FA','#B41F44'])
    fig,ax=plt.subplots(figsize=(11.8,4.7));image=ax.imshow(annual.to_numpy(),cmap=cmap,vmin=-35,vmax=35,aspect='auto')
    ax.set_xticks(range(len(annual.columns)),[str(x)+('*' if x in (2019,2026) else '') for x in annual.columns]);ax.set_yticks(range(len(annual)),[NAMES[x] for x in annual.index])
    for i in range(len(annual)):
        for j in range(len(annual.columns)):
            value=annual.iloc[i,j];ax.text(j,i,num(value,1),ha='center',va='center',fontsize=9,color='white' if abs(value)>20 else '#251B25')
    ax.set_title('Retornos por ano (%) · * anos parciais',pad=16);fig.colorbar(image,ax=ax,label='% no ano',shrink=.8)
    fig.tight_layout();fig.savefig(folder/'retornos_anuais.png',dpi=170);plt.close(fig)
    orders=pd.read_csv(OUT/'capacidade_ordens_multifatorial.csv',parse_dates=['execution_date'])
    fig,ax=plt.subplots(figsize=(11.8,4.2))
    for action,color in [('COMPRA','#B41F44'),('VENDA','#178577')]:
        sample=orders.loc[orders.action.eq(action)];ax.scatter(sample.execution_date,100*sample.participation_adv,s=10,alpha=.45,color=color,label=action.title())
    ax.axhline(10,color='#251B25',ls='--',lw=1,label='10% do ADV');ax.axhline(20,color='#BD4C38',ls=':',lw=1,label='20% do ADV')
    ax.set(title='Capacidade: tamanho de cada ordem / ADV conhecido no sinal',ylabel='% do volume médio diário');ax.grid(alpha=.7);ax.legend(ncol=4,fontsize=8)
    fig.text(.08,.015,'Diagnóstico de ordens simuladas. Pontos acima dos limites não representam execução assegurada.',fontsize=8,color='#706575')
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(folder/'capacidade_ordens.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11.8,4.8))
    for name,label,color in [('multifactor_gross','Bruto, sem negociação','#7963B2'),('multifactor','Após negociação 20 bps','#B41F44'),('operational_100m_eta05','Após slippage η=0,5','#178577')]:
        data=pd.read_csv(OUT/'cenarios'/name/'patrimonio_diario.csv',parse_dates=['date']).set_index('date')
        ax.plot(data.index,data.nav_brl/1e6,label=label,color=color,lw=1.5)
    for admin,perf,color in [(0.01,0.1,'#BA7A28'),(0.02,0.2,'#706575')]:
        fee=pd.read_csv(OUT/f'taxas_admin_{admin}_performance_{perf}.csv',parse_dates=['date']).set_index('date')
        ax.plot(fee.index,fee.net_nav_brl/1e6,label=f'Slippage + taxas {admin:.0%}/{perf:.0%}',color=color,lw=1.5)
    ax.plot(wealth.index,wealth.cdi/1e6,label='CDI',color='#4D7B83',lw=1.3,ls='--')
    ax.set(title='Cenários hipotéticos: bruto, negociação, slippage e taxas',ylabel='Patrimônio fictício (R$ milhões)');ax.grid(alpha=.7);ax.legend(ncol=3,fontsize=8,loc='upper left')
    fig.tight_layout();fig.savefig(folder/'bruto_liquido_taxas.png',dpi=170);plt.close(fig)
    return folder


def prepare_oos(doc):
    folder=OUT/'fora_da_amostra';folder.mkdir(exist_ok=True)
    h=pd.read_csv(OUT/'cenarios'/'multifactor'/'carteiras_mensais.csv')
    last=h.loc[h.execution_date.eq(h.execution_date.max())]
    last.to_csv(folder/'carteira_herdada_referencia.csv',index=False)
    checkpoint={'status':'PREPARADO, NÃO EXECUTADO','prospective_observations':0,
        'registered_protocol_sha256':doc['protocol_sha256'],'base_available_through':'2026-11-04',
        'base_2026_11_05':'PENDENTE: coletar e arquivar fechamento antes de medir o primeiro retorno prospectivo de 06/11/2026',
        'holdings_note':'Carteira herdada reconstruída ex post da formação de outubro/2026; não é evidência de decisão arquivada antes de sua execução.',
        'first_new_formation':'Último pregão B3 de novembro/2026; execução na sessão seguinte',
        'target_end':'2027-11-05','parameters':doc['protocol']['baseline'],
        'gates':['Resolver cobertura corporativa e política de mudanças de ticker antes de interpretar o resultado como validação integral.',
                 'Para cada decisão: arquivar dados disponíveis, instante de corte, universo conhecido, ranking, pesos, sinais e hashes antes de executar.',
                 'Sem mudança de mandato baseada em resultados, sem reescrever arquivos de decisão anteriores.',
                 'Parar o cálculo quando faltar dado de posição; registrar incidentes e versões, sem imputar preços.'],
        'engine_sha256':hashlib.sha256((ROOT/'src'/'engine.py').read_bytes()).hexdigest(),
        'research_code_sha256':hashlib.sha256((ROOT/'src'/'validation.py').read_bytes()).hexdigest()}
    dump(folder/'plano_e_checkpoint.json',checkpoint)
    pd.DataFrame(columns=['decision_timestamp_utc','data_cutoff','signal_date','execution_date','universe_hash','input_hash','ranking_hash','weights_hash','engine_hash','status']).to_csv(folder/'registro_decisoes_vazio.csv',index=False)
    pd.DataFrame(columns=['date','nav_brl','cdi_nav_brl','data_hash','incident_status']).to_csv(folder/'observacoes_prospectivas_vazias.csv',index=False)
    return checkpoint


def build():
    doc=json.loads((OUT/'validacao_resultados.json').read_text(encoding='utf-8'))
    independent=json.loads((OUT/'validacao_independente.json').read_text(encoding='utf-8'))
    if independent['status']!='PASS':raise ValueError('Validação independente pendente')
    figs=figures(doc);oos=prepare_oos(doc)
    sources=ROOT/'work'/'etapa2'/'fontes_primarias'/'manifesto_documentos.json'
    target=OUT/'fontes';target.mkdir(exist_ok=True)
    if sources.exists():shutil.copy2(sources,target/'manifesto_documentos_cvm.json')
    source_docs=json.loads((target/'manifesto_documentos_cvm.json').read_text(encoding='utf-8'))
    def url_for(part):return next(x['url'] for x in source_docs if part in x['file'])
    comparison={r['strategy']:r for r in doc['comparisons']}
    main=comparison['multifactor'];c=doc['capacity'];fees=doc['fees'];events=doc['audit']['corporate_events']
    annual=pd.read_csv(OUT/'metricas_por_ano.csv');regimes=pd.read_csv(OUT/'metricas_por_regime.csv')
    sectors=pd.read_csv(OUT/'exposicao_setorial_por_ano.csv');coverage=pd.read_csv(OUT/'cobertura_codigos_ausentes.csv')
    old=json.loads((ROOT/'output'/'backtest_results.json').read_text(encoding='utf-8'))['metrics']
    comparison_table=table(['Estratégia','Retorno total','Retorno a.a.','Vol. a.a.','Sharpe CDI','Sortino CDI','Calmar','Drawdown','Turnover a.a.'],
        [[NAMES[r['strategy']],pct(r['return_total']),pct(r['return_annualized']),pct(r['vol_annualized']),num(r['sharpe_over_cdi']),num(r['sortino_over_cdi']),num(r['calmar']),pct(r['max_drawdown']),num(r['turnover_annualized'])+'×' if r['turnover_annualized'] is not None else '—'] for r in doc['comparisons']])
    annual_table=table(['Estratégia']+[str(y)+('*' if y in (2019,2026) else '') for y in range(2019,2027)],
       [[NAMES[name]]+[pct(float(annual.loc[annual.strategy.eq(name)&annual.year.eq(y),'return_total'].iloc[0])) for y in range(2019,2027)] for name in NAMES])
    regime_table=table(['Regime','Sessões','Retorno a.a. condicional','Vol. a.a.','Sharpe CDI','Pior queda contígua','Turnover a.a. condicional'],
        [[r.regime,int(r.observations),pct(r.return_annualized),pct(r.vol_annualized),num(r.sharpe_over_cdi),pct(r.max_drawdown),num(r.turnover_annualized)+'×'] for r in regimes.loc[regimes.strategy.eq('multifactor')].itertuples()])
    event_table=table(['Evento','Retorno da etapa 1','Retorno independente','Tratamento'],
       [[e['ticker']+' · '+e['date'],pct(e['original_return']),pct(e['independent_return']),e['status']] for e in events])
    missing_table=table(['Código','Primeiro preço B3 na janela','Último preço B3','Observações'],
       [[r.ticker,r.first,r.last,int(r.observations)] for r in coverage.loc[coverage.ticker.isin(['CPLE6','BRFS3','JBSS3','MRFG3'])].itertuples()])
    operation_table=table(['Cenário','Capital inicial (R$ mi)','PL final (R$ mi)','Retorno a.a.','Custos acumulados (R$ mi)'],
       [[r['strategy'],num(r['initial_nav_brl']/1e6),num(r['final_nav_brl']/1e6),pct(r['return_annualized']),num(r['cost_total_brl']/1e6)] for r in [doc['operational'][0],main,*doc['operational'][1:]]])
    fee_table=table(['Administração / performance','PL final líquido (R$ mi)','Retorno líquido a.a.','Administração paga (R$ mi)','Performance paga (R$ mi)','Provisão pendente (R$ mi)'],
       [[pct(r['management_annual'])+' / '+pct(r['performance_rate']),num(r['final_nav_brl']/1e6),pct(r['return_annualized']),num(r['management_fee_total_brl']/1e6),num(r['performance_paid_total_brl']/1e6),num(r['performance_pending_brl']/1e6)] for r in fees])
    uncertainty_table=table(['Multifatorial menos','Diferença da média mensal × 12','IC 95% inferior','IC 95% superior','Inclui zero'],
       [[NAMES[r['comparison'].replace('multifactor_minus_','')],pct(r['annualized_arithmetic_mean_difference']),pct(r['ci95_low']),pct(r['ci95_high']),'Sim' if r['includes_zero'] else 'Não'] for r in doc['uncertainty']])
    sensitivity_table=table(['Variável','Valor','Retorno a.a.','Vol. a.a.','Sharpe CDI','Drawdown'],
       [[r['parameter'],num(r['value'],2)+(' (base)' if r['is_baseline'] else ''),pct(r['return_annualized']),pct(r['vol_annualized']),num(r['sharpe_over_cdi']),pct(r['max_drawdown'])] for r in doc['sensitivity']])
    max_sector=float(sectors.loc[sectors.strategy.eq('multifactor'),'maximum_weight'].max())
    report=f'''# ImpactUFSCar Found — segunda etapa de validação quantitativa

**Data do relatório: 05/11/2026. Corte dos dados: 04/11/2026. Status: CONDICIONAL.**

Este documento apresenta pesquisa de uma carteira fictícia. Não apresenta desempenho de fundo real, alpha validado ou capacidade de execução assegurada. As comparações usam os mesmos 47 códigos disponíveis, período de patrimônio de 31/01/2019 a 04/11/2026 e custos idênticos entre as quatro estratégias. Nenhum preço foi inventado para preencher histórico.

## 1. Conclusão sustentada pelos dados

O algoritmo do score 75/25 e a separação entre decisão e execução foram conferidos. A auditoria identificou e tratou diferenças econômicas em BRAP4/MGLU3 e corrigiu o alinhamento do CDI. Após essas revisões, o multifatorial apresenta retorno anualizado de **{pct(main['return_annualized'])}**, volatilidade de **{pct(main['vol_annualized'])}**, Sharpe sobre CDI de **{num(main['sharpe_over_cdi'])}** e drawdown de **{pct(main['max_drawdown'])}**. Seu PL final fictício é **R$ {num(main['final_nav_brl'])}**.

O multifatorial teve resultado pontual superior às outras três carteiras nesta amostra. Entretanto, os intervalos de incerteza incluem zero na comparação com Momentum puro, baixa volatilidade, Equal Weight e CDI. A comparação com os índices oficiais é positiva no intervalo estatístico empregado, mas continua condicionada ao universo retrospectivo, às hipóteses de dados, às múltiplas comparações e ao método de reamostragem. Isso não sustenta uma afirmação de alpha.

A viabilidade de execução integral com R$ 100 milhões iniciais **não foi comprovada**: {c['orders_over_10pct_adv']} de {c['orders']} ordens excedem 10% do ADV. Com slippage hipotético e taxas de 2%/20%, o retorno anualizado líquido cai para **{pct(fees[2]['return_annualized'])}**, frente a **{pct(comparison['cdi']['return_annualized'])}** do CDI. O cenário de 1%/10% permanece acima do CDI nesta amostra, sem comprovação prospectiva. Não foi alterado o mandato nem escolhida retrospectivamente uma configuração vencedora.

## 2. Preservação, protocolo e amostra

Antes das alterações, foram preservados o código, o template, a configuração e todos os resultados da etapa 1 em `work/etapa2/etapa1_antes_da_auditoria.zip`. Os CSVs de entrada, JSON histórico, patrimônio, seleções, ordens e métricas originais permaneceram byte a byte iguais, conforme `validacao_independente.json`. O HTML original foi preservado como `output/dashboard_com_resultados_etapa1.html`; o endereço atual recebeu a nova seção, mantendo as seções anteriores e a identidade visual.

O protocolo foi registrado antes das comparações: `protocolo_registrado.json`, SHA-256 **`{doc['protocol_sha256']}`**. A seleção principal permaneceu Momentum 12–1 75% + baixa volatilidade 25%, até 20 nomes, pesos nominais 5%, teto setorial 30%, teto de emissor 5%, ADV21 mínimo de R$ 33.333.334 e custos de 20 bps por nocional em compras e vendas.

Os preços começam em 02/01/2018, usados no aquecimento; o PL começa no fechamento de 31/01/2019 e as primeiras ordens são executadas em 01/02/2019. São 1.932 fechamentos, 1.931 intervalos de retorno e 94 rebalanceamentos. As três carteiras por score tiveram 20 ativos em todas as formações. O comparador Equal Weight inclui todos os elegíveis, em média {num(comparison['eligible_equal']['avg_holdings'])}; não é carteira aderente ao limite de 20 ou aos tetos de emissor/setor. Seu teto de emissor observado foi {pct(comparison['eligible_equal']['issuer_max_target'])}.

## 3. Auditoria dos dados e eventos societários

### 3.1 Universo retrospectivo e quatro séries ausentes

{missing_table}

Esses preços brutos foram recuperados diretamente dos arquivos anuais COTAHIST B3. Logo, os quatro códigos tinham histórico; sua ausência no Yahoo não autoriza excluí-los de um universo historicamente neutro. O CSV `historico_codigos_ausentes_b3.csv` preserva preços, volume financeiro e ISIN, mas **não foi usado como substituto de retorno total**.

- **CPLE6:** sequência de unificação das preferenciais e conversão em ordinárias CPLE3. O aviso da Copel de 17/11/2025 detalha conversão e resgate; a preferência passa por CPLE5 e envolve parcela em dinheiro de R$ 0,7749. Copel já está representada por CPLE3 no universo; simplesmente duplicar a série criaria dupla contagem de emissor e ignoraria os direitos próprios de cada classe. [Aviso original arquivado na CVM]({url_for('COPEL_2025-11-17_1446410')}).
- **BRFS3 e MRFG3:** a reorganização retira BRFS3 e altera MRFG3 para MBRF3; a série oficial mostra término dos dois códigos antigos em 22/09/2025 e início de MBRF3 em 23/09/2025. São necessárias relação de troca, eventuais pagamentos e política de posição, não uma substituição textual. [Comunicado oficial B3](https://sistemasweb.b3.com.br/PlantaoNoticias/Noticias/Detail?agencia=15&dataNoticia=2025-09-18+05%3A27%3A40&idNoticia=3073281).
- **JBSS3:** encerra negociação em 06/06/2025 e é sucedido pela estrutura de BDR JBSS32 a partir de 09/06/2025. A mudança envolve incorporação/resgate e frações; o novo instrumento é BDR, exigindo decisão de mandato. [Fato relevante original JBS de 06/06/2025]({url_for('JBS_2025-06-06_1387922')}).

**O viés de sobrevivência não foi eliminado nem quantificado com precisão.** Faltam composição histórica completa do universo, emissores que desapareceram e séries total return verificadas. Setores e identidades de emissor também são retrospectivos. Não é válido atribuir às quatro séries retorno zero, assumir caixa no período inteiro ou completar cotações com dados sintéticos. As comparações abaixo são condicionais ao mesmo subconjunto de 47 séries.

### 3.2 BRAP4 e MGLU3: preço versus riqueza econômica

{event_table}

**BRAP4, 17/12/2021:** o fechamento bruto cai de R$ 55,78 para R$ 23,14. O acionista também passa a ter direito a 0,332373453 ação VALE3 por ação BRAP4, mais R$ 6,043850916 de dividendo. Com VALE3 a R$ 79,17 no fechamento ex-direito, a riqueza econômica é `(23,14 + 0,332373453 × 79,17 + 6,043850916) / 55,78 − 1`, cerca de −0,51%. A etapa 1 indicava +0,61% no retorno ajustado. A correção encadeia esse retorno econômico e preserva os demais retornos diários.

As ações Vale são creditadas em 20/12 e o dinheiro em 29/12; entre ex-direito e pagamento, são direitos a receber, não caixa operacional disponível. A versão corrigida é uma proxy de retorno total com marcação econômica e reinvestimento implícito; não é reconstrução de custódia por liquidação. [B3, tratamento da restituição de capital](https://www.b3.com.br/data/files/EB/62/2B/92/FE5AD710C8F297D7AC094EA8/OC%20169-2021%20PRE%20%20Tratamento%20das%20Posi%C3%A7%C3%B5es%20e%20Garantias%20restitui%C3%A7%C3%A3o%20de%20capital%20da%20Bradespar%20S.A.%20em%20a%C3%A7%C3%B5es%20de%20emiss%C3%A3o%20da%20Vale%20S.A.%20%28PT%29.pdf), [aviso do dividendo]({url_for('BRADESPAR_2021-11-08_914312')}).

**MGLU3, 01/02/2024:** o aviso estabelece direito de subscrição de 9,5790177529%, a R$ 1,95 por nova ação. A ação fecha a R$ 2,10 na véspera e R$ 2,06 no dia ex-direito. O direito MGLU1 negociou efetivamente a R$ 0,20 no fechamento da B3, com volume financeiro de R$ 155.074. A riqueza marcada é `(2,06 + 0,095790177529 × 0,20) / 2,10 − 1`, cerca de −0,99%, contra +4,88% no ajuste original. O valor teórico ex-direito produziria outra convenção de retorno, −1,29%; ele foi registrado como referência e não apresentado como preço negociado. Não se supôs exercício ou venda garantida do direito. [Aviso original da Magalu]({url_for('MAGAZINE_2024-01-26_1186895')}).

O grupamento 10:1 de maio/2024, a bonificação de 5% da Magalu em dezembro/2025 e a bonificação de 12,95% da Bradespar em setembro/2021 foram conferidos contra preços B3 e avisos de emissores. Os retornos mecânicos coincidem com os ajustes da fonte nos pontos testados.

**Limite da reconciliação:** as correções são localizadas, documentadas e registradas em `correcoes_corporativas_etapa2.csv`; não houve suavização de retornos nem escolha de ajustes por rentabilidade. Restam 21 observações previamente sinalizadas fora dos grandes grupos BRAP4/MGLU3, além de diferenças menores e proventos de outros emissores ainda não integralmente conciliados. Parte das diferenças de nível decorre de operações além de splits; não é correto chamar toda diferença de preço de erro, nem declarar toda a base validada após conferir cinco eventos.

### 3.3 CDI, calendário e fontes dos índices

Foi corrigida a capitalização da Taxa DI: **data inicial inclusiva, final exclusiva**, pois a taxa de uma data remunera o intervalo de um dia útil iniciado nela. O fator entre dois fechamentos inclui as taxas oficiais em `[fechamento anterior, fechamento atual)`, inclusive dias bancários sem pregão. A etapa 1 utilizava `(anterior, atual]`. Isso altera o CDI acumulado de {pct(old['cdi_return_total'])} para {pct(comparison['cdi']['return_total'])}. [Manual B3CALC, convenção do produtório DI](https://www.b3.com.br/lumis/portal/file/fileDownload.jsp?fileId=8AE490CA7861D39C0178B17E20392164).

Foi mantida a exclusão das 43 linhas Yahoo de 25/01/2018 sem pregão B3 confirmado; não há interpolação, carregamento de preço ou CDI zero para lacuna. A falta de preço de posição interrompe o motor. O volume financeiro B3 é usado quando há correspondência exata ticker/data; nas demais 3.585 linhas da base original, permanece a aproximação Close × Volume Yahoo, com cobertura declarada.

Ibovespa e IBrX 100 foram baixados diretamente da API utilizada pela página oficial de estatísticas da B3, em matrizes anuais de fechamentos, sem preencher lacunas. Ambos cobrem integralmente o período comparado. O IBrX 100 é índice de retorno total; não é proxy de ETF. Na comparação entre Yahoo e B3 para Ibovespa, 93 observações diferiam mais de 10 bps em nível relativo, com desvio máximo de cerca de 0,82%; a etapa 2 usa a B3. URLs, respostas anuais e hashes estão em `fontes_indices.json` e `fontes/indices_b3/`. [Estatísticas oficiais do IBrX 100](https://sistemaswebb3-listados.b3.com.br/indexStatisticsPage/daily-evolution/IBXX?language=pt-br), [metodologia B3](https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/indice-brasil-100-ibrx-100.htm).

## 4. Auditoria do score, causalidade, dividendos e ordens

O Momentum é `AdjClose[t−21] / AdjClose[t−252] − 1`. A volatilidade é o desvio padrão amostral dos últimos 63 retornos diários, multiplicado por √252. Os percentis usam extremos 0 e 1, com rank médio em empates: `(rank médio − 1)/(N−1)`; na baixa volatilidade, o ranking é inverso. O score é **exatamente `0,75 × percentil Momentum + 0,25 × percentil baixa volatilidade`**. Essa convenção de percentil foi explicitada, evitando confusão com `rank(pct=True)`, cujo menor valor seria 1/N.

Foram conferidos 4.127 scores em 94 datas contra uma implementação independente, com erro máximo zero. Remover todo o histórico posterior ao sinal não alterou ranking nem seleção. Também foram testados preços futuros perturbados, efeito sobre PL/ordens anteriores, callback de custos e causalidade da provisão/cristalização de taxas. Isso confirma causalidade do algoritmo, **não** disponibilidade point-in-time dos ajustes, do universo ou dos setores.

Sinais são formados após o último fechamento do mês; as ordens são modeladas no fechamento da sessão seguinte. A carteira antiga recebe a valorização até esse fechamento; as compras novas não recebem o retorno ocorrido antes da execução. O custo de 0,20% incide em cada compra e cada venda; o tamanho pós-custo é resolvido de forma consistente. Não há venda final artificial da carteira no fim da amostra.

Os dividendos já estão incorporados no retorno ajustado: não há crédito duplicado em caixa. Contudo, isso não reconstrói pagamentos por data, impostos/JCP, reinvestimento executável, direitos residuais, liquidação D+2, frações ou despesas de custódia. Esses pontos permanecem limitações operacionais e de validação de dados.

## 5. Comparação principal e riscos

{comparison_table}

Turnover é one-way: metade do nocional absoluto comprado/vendido dividida pelo PL pré-negociação, somado e anualizado por 252/n. Índices e CDI não têm turnover de replicação disponível nesta simulação, por isso mostram “—”. Índices são referências teóricas sem custos; somente as quatro carteiras compartilham a hipótese de 20 bps por nocional.

Sharpe usa média do excesso diário sobre CDI dividida pelo desvio padrão do retorno da carteira e multiplicada por √252. Sortino usa o mesmo excesso e downside deviation `sqrt(média(min(excesso,0)²))`, calculada sobre todos os dias, com alvo CDI. Calmar é CAGR / magnitude do máximo drawdown. CAGR e volatilidade usam 252 sessões/ano. O drawdown inclui o capital inicial antes da primeira perda. CDI sem drawdown não recebe Calmar artificialmente infinito; Sortino sem downside também fica indefinido. VaR/ES estão nos CSVs completos.

![Patrimônio e drawdown](figuras/comparacao_patrimonio_drawdown.png)

### 5.1 Anos e exposições setoriais

{annual_table}

*2019 começa em 31/01; 2026 termina em 04/11. Os valores da tabela são retornos acumulados no trecho do ano, não sua anualização. Por exemplo, o multifatorial teve perdas em 2021 e 2024, apesar do ganho no período completo; em 2026 parcial ficou próximo da estabilidade e abaixo do CDI. Não se deve deduzir consistência anual a partir do retorno total.

![Retornos anuais](figuras/retornos_anuais.png)

Exposições diárias por setor, incluindo deriva, foram exportadas para cada carteira. Médias, máximos e pesos finais estão em `exposicao_setorial_por_ano.csv`; médias/máximos por regime estão em `exposicao_setorial_por_regime.csv`. A soma dos setores mais caixa foi conferida diariamente. O limite do multifatorial na formação foi 30%, mas a maior exposição setorial realizada entre formações chegou a **{pct(max_sector)}**. Não há rebalanceamento diário para conter essa deriva.

### 5.2 Regimes previamente definidos

{regime_table}

A classificação de cada dia usa apenas o Ibovespa até t−1: retorno de 126 sessões para alta/baixa e volatilidade de 63 sessões acima/abaixo de 25% a.a. Não se utilizou a mediana da volatilidade de toda a amostra nem rótulos definidos após observar crises.

Os retornos anualizados por regime são taxas condicionais de subconjuntos de dias, não uma carteira que pudesse ser mantida continuamente somente nesses regimes. Drawdowns foram medidos dentro de trechos contíguos, sem concatenar datas separadas; Calmar foi omitido nos regimes descontínuos. O regime de alta com volatilidade elevada tem apenas 37 observações: não permite uma conclusão estável sobre comportamento futuro. O CSV contém as sete referências/estratégias e todos os indicadores por regime.

## 6. Sensibilidade e incerteza

{sensitivity_table}

As configurações foram definidas antes das comparações e executadas uma variável por vez, com o mesmo início de PL. Não houve grade combinatória, seleção por maior CAGR, mudança de score ou escolha de limiar com base no resultado. Os testes mostram dependência de custo, janela, exclusão recente e liquidez; sua função é avaliar fragilidade. A estratégia principal continua 75/25.

{uncertainty_table}

Foram usados 93 meses completos, excluindo janeiro/2019 de base e novembro/2026 parcial, bootstrap pareado de blocos contíguos de 6 meses, 2.000 réplicas e semente fixa 20261105. O intervalo é da **diferença da média mensal multiplicada por 12**, não da diferença de CAGR. Não há ajuste de seleção do universo, de revisões de dados ou correção familiar de todas as comparações. Mesmo os intervalos positivos contra índices não eliminam essas limitações. Não foi feita afirmação de significância confirmatória ou causal.

## 7. Viabilidade operacional, custos e taxas

Foram avaliadas {c['orders']} ordens. A maior ordem equivale a **{pct(c['max_participation_adv'])}** do ADV21 conhecido na formação; o percentil 95 é **{pct(c['p95_participation_adv'])}**. Houve {c['orders_over_5pct_adv']} ordens acima de 5%, {c['orders_over_10pct_adv']} acima de 10% e {c['orders_over_20pct_adv']} acima de 20%. A maior participação no volume efetivamente observado na sessão foi {pct(c['max_participation_actual_day'])}; esse dado é diagnóstico ex-post, não entrada na seleção.

Ao teto de 10% do ADV, a pior ordem exigiria aproximadamente **{num(c['max_days_at_10pct_adv'],0)} sessões**. O capital inicial indicativo que limitaria todas as ordens dessa trajetória a 10% do ADV é cerca de **R$ {num(c['approx_initial_nav_capacity_at_10pct_brl']/1e6)} milhões**, uma aproximação linear, não uma capacidade garantida. O mínimo de capacidade instantânea calculado com frações de ordem e PL de cada data foi R$ {num(c['min_instantaneous_nav_capacity_at_10pct_brl']/1e6)} milhões; são conceitos diferentes. O filtro de R$ 33,33 milhões de ADV é fixo e não cresce com o PL.

![Participação das ordens](figuras/capacidade_ordens.png)

{operation_table}

O custo variável por ordem é `5 bps negociação + 5 bps meio spread + η × sigma_diária63(sinal) × sqrt(|ordem| / ADV21(sinal))`, com η=0,5 e η=1,0. Usam-se ADV e volatilidade conhecidos na decisão, inclusive para vendas; não se usa volume futuro para reduzir custo. O tamanho e o custo são resolvidos conjuntamente com o PL após custos. A forma de raiz quadrada é uma hipótese de pesquisa inspirada em [modelos de impacto de metaordens](https://arxiv.org/abs/1412.0141), **sem calibração de coeficientes, spreads ou livro para esses ativos da B3**.

Os cenários de R$ 100 e R$ 500 milhões mostram o efeito hipotético de tamanho. Eles ainda supõem preenchimento integral ao fechamento e não simulam fila, ordens parciais, caminho de execução em seis sessões, impacto permanente, decaimento ou oportunidade perdida. Portanto, o retorno após impacto é cenário de estresse, não evidência de executabilidade. Uma implementação operacional precisa definir e testar política de participação e ordens pendentes antes de reivindicar esse retorno.

### 7.1 Administração e performance hipotéticas

{fee_table}

As taxas incidem sobre o cenário operacional de R$ 100 milhões com η=0,5, e não sobre a curva bruta. Administração é debitada diariamente pela fração de dias corridos/365. Performance é provisionada somente sobre excedente à marca d’água líquida corrigida pelo CDI; a provisão reverte antes de cristalizar se o ganho recua. A cristalização ocorre no último dia útil de junho e no último dia útil até 30/12, datas conferidas no calendário da amostra. O estado da taxa não depende da existência de cotações posteriores. Ao final de novembro parcial, eventual provisão continua sendo passivo, sem cristalização antecipada. A política é hipotética e não pretende reproduzir regras de um regulamento constituído.

![Bruto, negociação, slippage e taxas](figuras/bruto_liquido_taxas.png)

## 8. Fora da amostra e próximos critérios de validação

A divisão 2019–2022 (desenvolvimento), 2023–2024 (validação) e 2025–04/11/2026 (holdout já observado) foi exportada em `diagnostico_temporal_retrospectivo.csv`. **Todos esses dados já estavam disponíveis nesta pesquisa.** Esses nomes não tornam a divisão um teste genuinamente fora da amostra e não foram usados para selecionar parâmetros.

Foi preparado um plano prospectivo, com 75/25 congelado, primeiro retorno novo em **06/11/2026** e horizonte até **05/11/2027**. O fechamento-base de 05/11 ainda precisa ser coletado/arquivado. A carteira herdada de outubro é inicialização reconstruída ex post; não foi apresentada como decisão registrada antes daquela execução. A próxima formação nova é o último pregão de novembro/2026, com execução na sessão seguinte.

O diretório `fora_da_amostra/` contém checkpoint, carteira de referência e dois registros deliberadamente **vazios** para decisões/observações futuras. Seu status é **PREPARADO, zero observações prospectivas**. Não houve agendamento de ordens, coleta futura simulada ou geração de performance fora da amostra.

Antes de usar esse acompanhamento como validação integral, será necessário: universo historicamente conhecido com deslistados; política documentada para conversões, BDRs, recebíveis e pagamentos; decisões e hashes arquivados antes das execuções; revisão de incidentes sem reescrever decisões antigas; dados de execução para calibrar spreads e impacto; política de participação/ordens pendentes; e critérios de avaliação mantidos até o fim do horizonte.

## 9. Testes, rastreabilidade e reprodução

Passaram **27 testes unitários**, com fixtures artificiais confinadas à memória/temporários. Esses testes não alimentam preços ou retornos do dashboard. A validação independente dos quatro cálculos reais conferiu {sum(r['selected_rows_checked'] for r in independent['checks'])} posições mensais e {sum(r['orders_checked'] for r in independent['checks'])} ordens. A maior diferença de reconstrução de PL foi **R$ {num(max(r['max_independent_nav_error_brl'] for r in independent['checks']),6)}**, explicada pelo arredondamento dos nocionais exportados.

Também foram conferidos: mesma janela entre carteiras; pesos e limites na formação; soma diária de setores e caixa; fechamento da sessão seguinte; custos variáveis por ordem; CDI direto das taxas oficiais; identidade do cenário de taxa zero; ausência de dupla cobrança na cristalização; reversão de provisão; estado das taxas sem dependência de observações futuras; retornos econômicos dos eventos revistos; cobertura completa dos dois índices; e preservação dos arquivos originais. Logs e CSVs acompanham o pacote.

O dashboard usa o mesmo template, CSS base, identidade vinho/bordô, gráficos SVG e funcionalidades anteriores. A nova seção permite comparar estratégias/referências, patrimônio/drawdown, anos/regimes, exposições, custos, taxas, sensibilidade e status de auditoria. A curva da etapa 1 continua identificada como preservada; as revisões ficam na seção de validação, sem reescrever a história da primeira entrega.

Para reproduzir os cálculos a partir dos caches entregues, dentro da pasta do projeto:

```shell
python -m pip install -r requirements-validation.txt
python -m src.validation_audit
python -m src.validation
python -m unittest discover -s tests -v
python tests/validate_stage2_real.py
python -m src.validation_report
python -m src.market_server --provider brapi --refresh-min 30
```

Os caches de índices oficiais, preços e reconciliações estão incluídos. Os ZIPs COTAHIST completos e PDFs de emissores ficam no ambiente de trabalho; o pacote contém seus URLs/hashes e os fatos numéricos extraídos, sem substituir a leitura dos originais. Para nova coleta, a fonte pode ter revisões; compare hashes e não trate uma base nova como réplica byte a byte da amostra congelada.

## 10. Parecer

**Validado no escopo computacional:** fórmula e convenção dos percentis, causalidade dos sinais, calendário/ordens no modelo, contabilização de custos, capitalização CDI corrigida, separação de taxas, comparabilidade temporal, posições/PL reconstituídos e cinco eventos específicos conferidos.

**Não validado integralmente:** neutralidade histórica do universo, todos os proventos e reestruturações, custódia/recebíveis por pagamento, replicação investível dos índices, slippage calibrado, execução ao patrimônio proposto e desempenho prospectivo.

**Conclusão:** os dados sustentam uma comparação exploratória reproduzível e identificam restrições relevantes de risco/capacidade. Não sustentam declarar a estratégia superior fora da amostra, o fundo economicamente viável com R$ 100 milhões ou a existência de alpha líquido após todos os custos. O mandato foi mantido; as pendências ficaram explícitas e versionadas.
'''
    (OUT/'RELATORIO_TECNICO.md').write_text(report,encoding='utf-8')
    body=MarkdownIt('commonmark',{'html':True}).enable('table').render(report)
    for file in figs.glob('*.png'):
        body=body.replace('src="figuras/'+file.name+'"','src="data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()+'"')
    css='body{font:16px/1.6 system-ui,sans-serif;color:#251B25;background:#F7F4F5;margin:0}main{max-width:1180px;margin:auto;padding:48px;background:white}h1,h2,h3{color:#941A3B;line-height:1.2}h1{border-bottom:5px solid #B41F44;padding-bottom:24px}h2{margin-top:44px}table{border-collapse:collapse;font-size:12px;width:100%;display:block;overflow:auto;margin:22px 0}td,th{padding:9px 11px;border:1px solid #EAE0E5;text-align:left}th{background:#FBE8EE}tr:nth-child(even){background:#FAF7F8}img{max-width:100%;height:auto}a{color:#941A3B}pre{overflow:auto;background:#FAF7F8;padding:18px;border-left:4px solid #B41F44}code{font-size:.88em}strong{color:#6C1730}@media print{body,main{background:white}main{padding:0}h2{break-after:avoid}table,img{break-inside:avoid}a{color:inherit}}'
    (OUT/'RELATORIO_TECNICO.html').write_text('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ImpactUFSCar Found — Validação etapa 2</title><style>'+css+'</style><main>'+body+'</main></html>',encoding='utf-8')
    # Recuperar o HTML original do snapshot, antes de substituir o endereço atual.
    original_html=ROOT/'output'/'dashboard_com_resultados_etapa1.html'
    if not original_html.exists():
        with zipfile.ZipFile(ROOT/'work'/'etapa2'/'etapa1_antes_da_auditoria.zip') as archive:
            original_html.write_bytes(archive.read('output/dashboard_com_resultados.html'))
    render_dashboard(ROOT/'output'/'backtest_results.json',ROOT/'output'/'dashboard_com_resultados.html',OUT/'validacao_resultados.json')
    shutil.copy2(ROOT/'output'/'dashboard_com_resultados.html',OUT/'dashboard_validacao_etapa2.html')
    print('Relatório e dashboard atualizados:',OUT)


if __name__=='__main__':build()
