# ImpactUFSCar Found — Plataforma Integrada v4.0

## Segunda etapa de validação — 05/11/2026

A seção **Validação** foi incorporada ao dashboard atual, conservando o CSS base,
a identidade visual e as seções anteriores. A etapa 1 foi preservada em
`output/dashboard_com_resultados_etapa1.html` e no snapshot
`work/etapa2/etapa1_antes_da_auditoria.zip`.

O parecer é **CONDICIONAL**. O score 75/25 e a causalidade do algoritmo foram
conferidos. Houve revisão dos eventos BRAP4/MGLU3 e correção do CDI para início
inclusivo/fim exclusivo. O viés de sobrevivência não foi eliminado, proventos
não foram integralmente reconstruídos por data de pagamento e a execução com
R$ 100 milhões não foi comprovada.

O relatório, os dados oficiais dos índices, as comparações, métricas por ano e
regime, exposições setoriais, sensibilidade, custos/slippage, taxas hipotéticas,
auditorias e o plano prospectivo estão em `output/validacao_etapa2/`.
O protocolo foi registrado antes das comparações e não houve escolha de
parâmetros para maximizar os resultados. Nenhuma performance futura foi criada.

Reprodução com os caches entregues, sem alterar a primeira execução:

```shell
python -m pip install -r requirements-validation.txt
python -m src.validation_audit
python -m src.validation
python -m unittest discover -s tests -v
python tests/validate_stage2_real.py
python -m src.validation_report
```

`python -m src.validation_data` consulta os índices oficiais B3 e extrai os
códigos antigos dos ZIPs COTAHIST já preservados em `work/b3_raw/`.
O relatório informa a cobertura e as limitações. Para conferência dos
documentos de emissores, use os URLs e hashes de
`output/validacao_etapa2/fontes/manifesto_documentos_cvm.json`.

Novas execuções do CLI histórico `src.run` passam a utilizar a convenção CDI
corrigida. A opção legada `ending_date` permanece no motor apenas para
reproduzir a etapa 1; a segunda etapa usa explicitamente `starting_date`.
Amostras novas exigem nova auditoria de dados e não substituem silenciosamente
a comparação congelada de 31/01/2019 a 04/11/2026.

## Primeiro backtest executado em 05/11/2026

Há agora um histórico exploratório em `output/dashboard_com_resultados.html`:
31/01/2019 a 04/11/2026, primeira execução em 01/02/2019, 94 rebalanceamentos.
Os resultados e limitações desta execução estão em `output/RELATORIO_BACKTEST.md`.
O universo é retrospectivo, com viés de sobrevivência: 47 de 51 códigos retornaram
histórico; BRFS3, CPLE6, JBSS3 e MRFG3 não retornaram preços nesta coleta.
Não são resultados auditados nem evidência validada de alpha.

O pipeline padrão agora confere os preços/volumes contra COTAHIST B3, registra
eventos Yahoo, corrige a falha de base de UGPA3 anterior a 28/06/2021 e remove
registros em dias sem pregão confirmado pela B3. A conferência não substitui
reconciliação integral de proventos, direitos, cisões e mudanças de ticker.
Os arquivos ZIP B3 ficam em `work/b3_raw/`; os CSVs originais e corrigidos,
as divergências e os hashes de auditoria ficam em `output/`.

O motor não preenche lacunas de preços e exige janela completa de formação.
O CDI inclui todos os dias bancários entre dois fechamentos, inclusive dias
sem negociação na B3. A integração conserva o template e injeta apenas o JSON
histórico no HTML gerado; o servidor abre esse HTML automaticamente.

Reproduzir o cálculo sem novo download:

```shell
python -m src.run --start 2018-01-01 --end 2026-11-05 --market-csv output/cache_precos_auditados.csv --cdi-csv output/cache_cdi_sgs12.csv --benchmark-csv output/cache_ibov_yahoo.csv --audit-json output/auditoria_fontes.json --momentum-weight 0.75 --n-assets 20 --cost-bps 20
python -m unittest discover -s tests -v
python tests/validate_real_run.py
```

Para uma coleta nova, use `python -m src.run --refresh` com as datas desejadas.
Os ZIPs anuais completos da B3 podem exigir centenas de MB na primeira consulta.
A opção `--skip-b3-audit` desliga a conferência e também a correção conhecida;
não foi usada para os resultados entregues. As seções abaixo descrevem o
pacote original, que não trazia backtest calculado.

**Status:** protótipo quantitativo com execução de backtest sobre históricos reais **quando esses dados forem baixados**. **Nenhum backtest real já calculado acompanha este pacote.** O dashboard v3 abre em modo demonstrativo com ações **fictícias e séries sintéticas**, identificadas como tal; ele só mostra histórico do mercado após importar o JSON produzido pelo motor Python. Os testes do software usam séries artificiais **somente em memória**, sem alimentar o dashboard distribuído.


## Desbloquear coleta de dados: execução fora do ambiente Python do ChatGPT

O Python hospedado no ChatGPT tem acesso à internet restrito e não é possível alterar esta política pelo código do projeto. **A solução prática é executar a coleta no seu computador com internet ou em um notebook hospedado (por exemplo, Google Colab)**, respeitando os termos do provedor. Não se deve fazer login nem inserir tokens em arquivos HTML públicos.

**No Windows:**

1. Instale Python 3.11+ em https://www.python.org/downloads/ com a opção *Add python.exe to PATH*.
2. Extraia o ZIP em uma pasta comum, sem caminhos excessivamente longos.
3. Rode `diagnosticar_windows.bat`: testa DNS e HTTPS do Banco Central, brapi e Yahoo e grava `diagnostico_rede.txt`.
4. Rode `rodar_windows.bat` para instalar dependências e criar o backtest histórico exploratório.
5. Rode `monitorar_windows.bat` para abrir `http://127.0.0.1:8765/` e acompanhar cotações no site. O botão de atualizar a tela não força cotações novas; por padrão o servidor consulta a fonte a cada 30 minutos.
6. Para monitorar a carteira inteira pela brapi, configure seu token **na variável de ambiente** `BRAPI_TOKEN`, não no JavaScript, e verifique sua cota/franquia contratada. Sem token, somente os tickers públicos suportados são consultados. Alternativa `python -m src.market_server --provider yahoo_eod --refresh-min 30` fornece apenas fechamentos diários, **não preços intradiários**.

**Se falhar:** o relatório de diagnóstico distingue falha DNS, HTTPS, HTTP 429 (limite da API) e HTTP 401/403 (autenticação/permissão). Falha HTTP não prova bloqueio de internet. Redes corporativas podem exigir permissão de firewall/proxy. Reproduza primeiro em uma rede pessoal; não tente burlar restrições administrativas.

**Dados reais versus tempo real:** o motor histórico depende de séries completas e dados corporativos ajustados; o monitor mostra preços observados da fonte com horário e possível atraso. Sem feed profissional/licença da B3, não afirmamos tempo real e não redistribuímos cotações publicamente. O fundo e o patrimônio seguem estritamente fictícios.

## Primeiro uso (Windows)

1. Descompacte `ImpactUFSCar_Found_Plataforma_v4.zip` em uma pasta no Windows.
2. Instale Python 3.11 ou superior em [python.org](https://www.python.org/downloads/), marcando **Add Python to PATH** durante a instalação (caso ainda não esteja instalado).
3. Com internet ativa, dê duplo clique em **`rodar_windows.bat`**. O arquivo instala pandas, numpy, requests e yfinance; baixa os preços das ações, o índice Ibovespa e o CDI diário; executa a seleção histórica e grava os resultados.
4. Ao terminar, abra **`output/dashboard_com_resultados.html`** no navegador. O site é autônomo e **não precisa de servidor**.
5. Como alternativa, abra **`dashboard/index.html`** e importe manualmente **`output/backtest_results.json`** na seção **Fonte dos dados**, usando **Importar backtest Python (.json)**.

Se aparecer erro de coleta, a rede ou a fonte podem estar indisponíveis. Nenhuma rentabilidade será fabricada como fallback: confira os erros e tente `python -m src.run --refresh`, ou forneça CSVs reais.

## Execução via terminal

Na pasta do projeto:

```shell
python -m pip install -r requirements.txt
python -m src.run
```

Exemplos para comparar configurações (salve cada cenário em uma pasta diferente):

```shell
python -m src.run --momentum-weight 0.75 --cost-bps 20 --output-dir output/base
python -m src.run --momentum-weight 1.00 --cost-bps 20 --output-dir output/momentum_puro
python -m src.run --momentum-weight 0.50 --cost-bps 30 --output-dir output/sensibilidade
python -m unittest discover -s tests -v
```

**Importante:** `--start` define o início da coleta (por padrão 2018-01-01). A primeira carteira surge somente depois do aquecimento de 252 pregões. `--end` é **exclusivo** e, por padrão, corresponde à data da execução; por isso o preço de um pregão em andamento não é capturado. As taxas do CDI são buscadas diretamente na série **SGS 12**, como percentual **por dia**.

## Como funciona

| Etapa | Regra v2 |
|---|---|
| Mercado | Brasil, ações e units listadas na B3 |
| Patrimônio fictício | R$ 100.000.000 |
| Universo provisório | Lista fixa e retrospectiva de 51 tickers em `config/universo_exploratorio.csv` **(contém viés de sobrevivência)** |
| Universo para estudo PIT | CSV de composição histórica do IBrX 100, campo `date` igual à **data efetiva/conhecida** da composição e `ticker` em cada linha, conforme instruções abaixo |
| Dados | Fechamento ajustado a dividendos e desdobramentos (Yahoo Finance), fechamento bruto e volume; CDI (SGS 12/BCB) |
| Momentum | `AdjClose[t-21] / AdjClose[t-252] - 1` |
| Baixa volatilidade | Desvio padrão de retornos diários dos últimos 63 pregões × √252; menores volatilidades recebem maiores percentis |
| Score | 75% percentil de Momentum + 25% percentil inverso de volatilidade |
| Elegibilidade | ADV mínimo R$ 33.333.334 (média de 21 dias de `close × volume`), preço e dados válidos |
| Seleção | Até 20 nomes por score, limite de 30% por setor, 5% por emissor no momento da seleção |
| Ponderação | Equal weight, 5% por ação; se faltarem elegíveis, restante permanece em caixa remunerado pelo CDI |
| Datas | Calcula ranking **no último fechamento do mês** e executa **no fechamento do pregão seguinte** |
| Custos | 20 bps por real negociado (entrada e saída), debitados na carteira na execução |
| Referências | CDI acumulado e Ibovespa (`^BVSP`); o último é índice B3 de retorno total em BRL |
| Riscos | CAGR, vol., Sharpe acima do CDI, drawdown, VaR/ES diário histórico a 95%, turnover |

**Atenção:** apesar do nome original proposto *Found*, o projeto permanece um **fundo fictício de pesquisa**, não um produto constituído. Os limites de setor, emissor e liquidez são aplicados no momento do rebalanceamento; a deriva dos preços pode alterar pesos até a execução seguinte.

### Importante sobre o universo: não confundir backtest com evidência validada

A lista inicial de 51 ações serve como **primeiro experimento reproduzível**, não como amostra historicamente neutra. A seleção retrospectiva de papéis ainda negociados exclui muitos ativos que deixaram de existir, inflando potencialmente os resultados. Portanto:

- **Sem `--membership-csv`:** os resultados são **exploratórios e sujeitos a viés de sobrevivência**; NÃO devem ser utilizados publicamente como evidência de alpha.
- **Com `--membership-csv`:** é possível restringir por composição histórica do IBrX 100. Entretanto é **obrigatório** adicionar à configuração de ativos os tickers de todas as carteiras históricas (inclusive companhias deslistadas) e obter preços/proventos completos desses ativos. Só o arquivo de composição **não** elimina o viés.
- A coluna `date` da composição deve indicar o momento em que o conjunto era **conhecido e aplicável**, não data de download atual. O motor usa o último snapshot cuja data seja anterior/igual à formação, rejeitando snapshots com defasagem superior a 145 dias.
- O programa não reconstrói mudanças de ticker, spin-offs, fechamento de capital, fusões ou casos de suspensão com valorização/recovery. Interrompe a execução se faltar preço de posição aberta, em vez de imputar um preço que favoreça a estratégia.
- O controle de liquidez usa uma aproximação de ADV de 21 dias e **não** substitui estudo de impacto para ordens de R$ 5 milhões.

Exemplo de chamada **somente após** preencher corretamente o CSV com snapshots históricos completos:

```shell
python -m src.run --membership-csv config/ibrx100_historico.csv --refresh --output-dir output/pit
```

Formato `config/ibrx100_historico.csv`:

```csv
date,ticker
2022-01-03,TICKER_VALIDO_DE_2022
2022-01-03,OUTRO_TICKER_DE_2022
2022-05-02,TICKER_VALIDO_DE_2022
```

**As linhas acima apenas exemplificam formato, não reproduzem o índice verdadeiro.** O template no projeto contém **somente cabeçalho** para evitar que uma composição inventada seja usada como dado real.

## Usar fontes de dados próprias

Se o Yahoo Finance ou BCB não estiverem disponíveis, é possível importar CSVs que você tenha **validado**:

```shell
python -m src.run --market-csv minha_base/acoes.csv --cdi-csv minha_base/cdi.csv --benchmark-csv minha_base/ibov.csv
```

`acoes.csv` (formato longo):

```
date,ticker,adj_close,close,volume
2021-01-04,PETR4,PRECO_AJUSTADO_REAL,FECHAMENTO_BRUTO_REAL,VOLUME_ACOES_REAL
```

`cdi.csv`:

```
date,rate_pct_daily
2021-01-04,TAXA_CDI_REAL_EM_PERCENTUAL_AO_DIA
```

`ibov.csv`:

```
date,adj_close
2021-01-04,NIVEL_REAL_DO_INDICE
```

Esses exemplos são **esquemas de colunas, não dados reais**. O campo `adj_close` não pode ser substituído pelo fechamento bruto sem perder o ajuste de proventos. As datas precisam ser `AAAA-MM-DD`.

## Arquivos gerados pelo Python

`output/` é preenchido **somente depois** de executar o backtest:

- `cache_precos_yahoo.csv`: fechamentos ajustados/brutos e volume coletados, para replicabilidade.
- `cache_cdi_sgs12.csv`: histórico bruto diário do CDI da série SGS 12, em percentual.
- `cache_ibov_yahoo.csv`: níveis do Ibovespa, referência acionária.
- `patrimonio_diario.csv`: patrimônio líquido hipotético diário, retorno do fundo e benchmarks.
- `carteiras_por_rebalanceamento.csv`: ticker, setor, emissor, fatores, score, peso-alvo e notional na execução.
- `ordens_e_custos.csv`: compras, vendas, turnover e custos por ordem.
- `metricas.json`: sumário, parâmetros e alertas de qualidade.
- `backtest_results.json`: base consumida pelo site.
- `dashboard_com_resultados.html`: **dashboard visual v4 com os dados históricos embutidos**, funciona sem internet.

O dashboard padrão `dashboard/index.html` contém gráficos **sintéticos para demonstração didática**, rotulados como tais. Somente depois de importar o JSON do Python (ou abrir o HTML gerado com ele embutido) os gráficos exibem um backtest histórico. Dados históricos continuam sendo uma **simulação de estratégia**, nunca rentabilidade de um fundo em operação.

## Definições das métricas

- **Retorno acumulado:** PL final / R$ 100 milhões − 1, com custos lineares de negociação.
- **CDI acumulado:** capitalização diária das taxas BCB nas datas de negociação do backtest.
- **Excesso em p.p.:** retorno acumulado − CDI acumulado, em pontos percentuais (não é alfa estatístico).
- **Volatilidade anualizada:** desvio padrão de retornos diários × √252.
- **Sharpe:** média do excesso diário sobre CDI dividida pela volatilidade diária do fundo × √252; é estimativa amostral.
- **VaR 95% e ES 95%:** quantil inferior de 5% e média da cauda, em retornos diários históricos; não projetam perdas máximas futuras.
- **Turnover one-way:** 1/2 × soma dos nocionais absolutos transacionados / PL pré-operação, acumulado ao longo dos rebalanceamentos.
- **Ibovespa:** usado somente se a fonte tiver série com cobertura suficiente; sua ausência é explicitada.

## Limitações e próximos marcos do projeto Impact

1. **Corrigir viés de sobrevivência** com constituintes históricos do IBrX 100, tickers inativos e proventos completos.
2. **Realizar treinamento/validação/teste fora da amostra**, sem escolher parâmetros com base no retorno do teste final.
3. **Implementar capacidade** com restrições de execução por percentual de volume diário, slippage variável e impacto.
4. **Adicionar comparativos e ablação:** Momentum puro, baixa volatilidade pura, Equal Weight aleatório repetido e IBrX 100 real.
5. **Registrar relatórios de governança** e as versões imutáveis das bases, inclusive os snapshots do universo.
6. **Não usar o dashboard como material de oferta de investimento** antes de estruturação jurídica, supervisão e compliance aplicáveis.

### Fontes e referências

- B3 — IBrX 100 (índice e composição): https://b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/indice-brasil-100-ibrx-100-b3.htm
- B3 — Ibovespa (índice de retorno total): https://b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa-b3.htm
- Banco Central — SGS 12 (CDI, % por dia): https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?hdOidSeriesSelecionadas=12&method=consultarGraficoPorId
- Banco Central — API SGS: https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json
- Yahoo Finance — adjusted close: https://sg.help.yahoo.com/kb/finance-for-web/adjusted-close-sln28256.html
- Yahoo Finance — yfinance: https://github.com/ranaroussi/yfinance

## Testes verificados nesta versão

`python -m unittest discover -s tests -v` executa testes de seleção, combinação dos fatores, restrição setorial, ausência de vazamento futuro no sinal, execução defasada, efeito de custos, snapshot PIT vencido e exportação. **Todos os testes usam dados artificiais somente para verificação do programa**; isso não configura desempenho de investimento.

## Material didático para membros da Impact

O arquivo **`notebooks/guia_didatico.ipynb`** explica os fatores, suas fórmulas e como estudar os indicadores no Python. Pode ser aberto pelo VS Code com extensão Jupyter ou pelo Jupyter Notebook. Ele **não inclui rentabilidades inventadas** e só desenha o gráfico após a coleta e a execução do motor. Para a visualização do notebook, instale também `matplotlib` se necessário (`python -m pip install matplotlib`).


## Dashboard visual v3.0 (base enviada pela Impact)

O dashboard conserva a arquitetura visual do HTML fornecido: hero com cota, indicadores, curvas e CDI, mapa mensal, carteira, riscos, metodologia, calculadora de sinal e laboratório. A identidade visual foi adaptada para bordô/vinho e vermelho, sem depender de imagens externas. O nome **ImpactUFSCar Found** foi mantido conforme escolhido para o projeto.

**Dois modos visivelmente separados:**

- **Demonstração sintética:** 60 empresas/códigos inventados, dados de mercado gerados artificialmente e comparação aproximada. Parâmetros podem ser ajustados livremente. O resultado **não** representa histórico real de negociação e não pode ser divulgado como performance do fundo.
- **Backtest histórico exploratório:** ao importar `output/backtest_results.json`, exibe as séries históricas calculadas pelo motor Python, ordens, carteira, patrimônio e comparação diária com CDI e Ibovespa (quando disponível). Não há taxas de administração/performance, tributação ou hedge na v2 do motor. O universo padrão é retrospectivo e contém viés de sobrevivência.

### Mandato-base de pesquisa (sem alterar a possibilidade de cenários no laboratório)

- Patrimônio inicial fictício: R$ 100 milhões; público-alvo pretendido: médio/grande investidor.
- Brasil, ações da B3; benchmark aspiracional CDI, Ibovespa como comparativo acionário.
- Momentum 12–1 (75%) + percentil de baixa volatilidade (25%).
- Até 20 ativos, nominalmente 5% por ação, máximo 30% por setor; filtro de liquidez.
- Rebalanceamento mensal; execução simulada após geração dos sinais; sem vendas a descoberto, futuros ou alavancagem.
- Custo de negociação de 0,20% do nocional transacionado no motor Python.

O percentual de pesos iguais de 5% é um alvo no momento da formação, e pode derivar por variação de preços. A taxa de administração e a taxa de performance aparecem no laboratório demonstrativo, mas o padrão é zero e a versão Python ainda não as simula.

### Como disponibilizar resultados diretamente no novo layout

Executar `rodar_windows.bat` ou `python -m src.run` agora **injeta o JSON** no próprio `dashboard/index.html` (sem alterar o template), produzindo `output/dashboard_com_resultados.html` com a interface v3 e resultado histórico incorporado. A alternativa é importar o JSON no site de demonstração.

**Atenção à divulgação futura:** a interface é material de pesquisa/educação da entidade, não um fundo real. A divulgação pública de retornos de estratégias exige revisão de dados, documentação, auditoria de metodologia e cuidados jurídicos/compliance próprios.
