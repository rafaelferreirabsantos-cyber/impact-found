# ImpactUFSCar Found — primeiro backtest histórico exploratório

Executado em 05/11/2026. Pesquisa com patrimônio fictício; não é rentabilidade de fundo em operação.
Nenhum preço sintético, retorno fabricado ou preenchimento de lacuna foi usado no histórico entregue.

## Período e cobertura

- Coleta solicitada: 01/01/2018 a 05/11/2026, com o fim exclusivo.
- Preços efetivamente disponíveis: 2018-01-02 a 2026-11-04.
- Histórico de patrimônio: 2019-01-31 a 2026-11-04: 1932 fechamentos e 1931 intervalos de retorno.
- Base de R$ 100 milhões no fechamento de 31/01/2019; primeira execução: 2019-02-01.
- 94 rebalanceamentos, 1880 registros de posições mensais, 47 ativos distintos selecionados no período.
- 47 dos 51 códigos configurados retornaram preços. Ausentes: BRFS3, CPLE6, JBSS3, MRFG3.
- Foram selecionadas 20 ações em todos os rebalanceamentos; peso-alvo de 5% por ação. A primeira data contém apenas o caixa inicial.
- O último rebalanceamento é de 2026-11-03; novembro de 2026 está parcial, até 04/11.
- IPOs não receberam histórico retroativo: só entram no ranking após janela completa de 253 fechamentos.

## Mandato e cálculos

Momentum = AdjClose[t−21] / AdjClose[t−252] − 1. Baixa volatilidade = percentil inverso do desvio padrão amostral de 63 retornos diários, anualizado por √252. Score = 75% percentil de Momentum + 25% percentil de baixa volatilidade, entre os ativos elegíveis naquela formação.

Até 20 ativos, pesos nominais iguais de 5%, máximo de 30% por setor e 5% por emissor na formação. Filtro mantido do projeto: ADV financeiro de 21 sessões ≥ R$ 33.333.334/dia. Quantias não investidas rendem CDI. Sem posições vendidas, futuros ou alavancagem.

Sinal no último fechamento confirmado pela B3 em cada mês. Execução no fechamento do pregão imediatamente seguinte. A carteira anterior recebe o retorno até esse fechamento; as novas posições começam a render a partir do próximo intervalo. Não se aplica às compras o retorno ocorrido antes de sua execução. Custos de 0,20% do nocional em cada compra e venda, com a base pós-custo resolvida pelo motor.

CDI em % a.d. da SGS 12, dividido por 100 antes da capitalização. Foram incluídas todas as taxas em (fechamento anterior, fechamento atual], inclusive 17 datas bancárias sem pregão. Não houve taxa ausente em pregão do cálculo. CDI não foi substituído por zero.

## Métricas obtidas

| Métrica | Resultado |
|---|---:|
| Patrimônio inicial fictício | R$ 100.000.000,00 |
| Patrimônio final fictício | R$ 257.249.164,28 |
| Retorno acumulado após custos | 157,25% |
| CDI acumulado | 103,61% |
| Patrimônio equivalente no CDI | R$ 203.610.295,93 |
| Diferença acumulada contra CDI | 53,64 p.p. |
| Ibovespa acumulado | 72,05% |
| Retorno anualizado (252 sessões) | 13,12% |
| Volatilidade anualizada | 22,91% |
| Sharpe sobre CDI | 0,2497 |
| Máximo drawdown | -43,78% |
| VaR histórico diário 95% | 1,95% |
| Expected Shortfall diário 95% | 3,39% |
| Custos de negociação acumulados | R$ 12.492.470,36 |
| Turnover one-way acumulado | 16,76 vezes |

O excesso em pontos percentuais é a subtração dos retornos acumulados, não alpha estatístico. CAGR e volatilidade usam 252 sessões/ano. Sharpe = √252 × média(retorno diário − CDI do intervalo) / desvio padrão do retorno diário da carteira. VaR é o negativo do quantil de 5% e ES é a perda média na cauda inferior a esse quantil; ambos são estimativas históricas de um intervalo diário, sem garantia de perda máxima. Não houve liquidação forçada da carteira no fim da amostra: os custos de uma venda final não foram cobrados.

## Fontes e ajustes corporativos

1. [Yahoo Finance via yfinance — documentação de ajustes](https://ranaroussi.github.io/yfinance/advanced/price_adjustment.html): coleta com `auto_adjust=False`, `actions=True`, `repair=False`. Close já está na base de splits da fonte; Adj Close incorpora também proventos. Não se ajustou a série duas vezes e não se adicionaram dividendos novamente ao PL. Dividendos e splits recebidos estão em `eventos_corporativos_yahoo.csv`.
2. [Banco Central, API oficial SGS 12](https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial=01/01/2018&dataFinal=04/11/2026): CDI diário oficial. As requisições foram feitas em janelas de até dois anos, com tentativas e cache.
3. [B3 COTAHIST, exemplo do arquivo oficial de 2021](https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A2021.ZIP): foram baixados os nove arquivos anuais, de 2018 a 2026; URL e SHA-256 de cada ZIP constam em `auditoria_fontes.json`. Filtrados registros tipo 01 e mercado à vista 010 para os tickers configurados. O CSV extraído contém preço bruto, quantidade, volume financeiro e ISIN.
4. Ibovespa: símbolo `^BVSP` do Yahoo, usado somente como comparativo adicional e com cobertura completa do período efetivo.

Foram conferidos 97344 dos 100929 registros de mercado com correspondência exata de ticker/data na B3. O filtro de liquidez usa o volume financeiro oficial nessas linhas; nas 3585 restantes (3,55%), usa a aproximação Close × Volume do Yahoo. Mudanças de ticker explicam parte da falta de correspondência; não houve ligação manual de séries sem cadeia validada de eventos.

**Correção UGPA3:** a série original exibia retorno de cerca de +119% em 28/06/2021. Os preços oficiais B3 de 25 e 28/06/2021 foram R$ 18,99 e R$ 19,19. A base anterior da fonte estava dividida indevidamente por aproximadamente 2,17049. Em 860 registros anteriores a 28/06/2021, o fechamento na base de splits foi restaurado a partir da B3, preservando o fator de dividendos AdjClose/Close do Yahoo. As quantidades da fonte também foram conferidas e a liquidez passou a usar o volume financeiro oficial. A série original foi preservada, e cada alteração está em `correcoes_precos_b3.csv`. O [histórico societário da Ultrapar](https://ri.ultra.com.br/governanca/participacao-societaria/) registra o split 2:1 de abril de 2019; direitos relativos à Extrafarma exigem análise econômica própria e não foram convertidos em recebimentos inventados.

**Calendário:** 43 linhas Yahoo de 25/01/2018, sem pregão confirmado no COTAHIST, foram descartadas e preservadas separadamente em `registros_fora_calendario_b3.csv`. Não foi criado pregão nem preço para preencher calendário.

**Reconciliação pendente:** 2507 comparações diferem mais de 3% entre Close Yahoo e preço B3 ajustado apenas por splits. Destas, 2.486 pertencem a BRAP4/MGLU3, cujas bases envolvem eventos além de splits; outras 21 são de demais datas/ativos. Uma diferença de base não prova erro. Esses preços foram preservados, registrados em `divergencias_yahoo_b3.csv` e **não foram integralmente reconciliados com avisos de proventos, direitos e operações societárias de cada emissor**. A correção de UGPA3 não transforma o conjunto em uma base corporativa auditada.

## Verificações executadas

- 14 testes unitários passaram. As séries artificiais desses testes existem apenas nas fixtures em memória/arquivos temporários e não alimentam o dashboard histórico.
- Testados: sinais sem efeito de preços futuros; PL e ordens anteriores imutáveis quando preços futuros são alterados; ordem no fechamento seguinte sem retorno retroativo; custos; limites por setor/emissor; rejeição de preço faltante; janela completa; snapshots PIT vencidos; ausência de CDI; dias bancários sem pregão e serialização JSON de ordens sem score.
- Conferência adicional de todos os 1880 registros reais: fórmula do Momentum, volatilidade, sinal mensal, execução no pregão seguinte, pesos, limites e custos.
- Reconstrução independente de toda a trajetória do PL: diferença máxima R$ 0,002807. O CDI foi recomposto diretamente de todas as taxas oficiais do intervalo e coincidiu com a série exportada.
- HTML aberto no navegador: modo histórico ativo, gráficos e filtros funcionando, sem erros de JavaScript observados; template/CSS/layout preservados. O arquivo gerado contém o JSON embutido e o servidor redireciona a página inicial para ele.
- O monitor intradiário é separado do backtest. Sem token brapi, tem cobertura de apenas 2 das 20 posições atuais; o PL indicativo continua bloqueado. Essa limitação não preenche nem altera os resultados históricos.

## Limitações relevantes

**Viés de sobrevivência e seleção retrospectiva:** lista fixa de 51 códigos, reduzida pela disponibilidade de 47 séries da fonte atual. Não é o universo histórico completo da B3/IBrX 100. As quatro séries ausentes não foram consideradas carteiras em caixa nem substituídas por tickers sucessores. A disponibilidade atual, a classificação setorial atual, revisões de dados e cadeias de ticker da fonte podem introduzir vieses. Dados ajustados hoje não equivalem a um arquivo point-in-time conhecido em cada data. Os testes afastam antecipação algorítmica de sinais/ordens, não esses vieses da amostra e da fonte.

Não há reconciliação corporativa integral, estudo fora da amostra, modelo de impacto/slippage variável, book, lotes, impostos, taxas de administração/performance, aportes ou resgates. A série ajustada é uma aproximação de retorno total da fonte, com reinvestimento implícito; não representa o fluxo efetivo por data de pagamento de cada provento. O ADV mínimo é fixo e não cresce com o PL; não demonstra capacidade para negociar os valores finais. Limites de setor/emissor são de formação: os pesos podem derivar entre rebalanceamentos. Não se escolheu o mandato com base nos resultados aqui obtidos.

## Última carteira — pesos-alvo em 2026-11-03

| Ativo | Setor | Peso-alvo | Momentum 12–1 | Volatilidade anual |
|---|---|---:|---:|---:|
| UGPA3 | Petróleo e gás | 5,00% | 91,80% | 36,23% |
| PETR3 | Petróleo e gás | 5,00% | 84,67% | 35,82% |
| VBBR3 | Petróleo e gás | 5,00% | 76,82% | 34,93% |
| PRIO3 | Petróleo e gás | 5,00% | 64,37% | 35,59% |
| BBSE3 | Financeiro | 5,00% | 37,86% | 24,90% |
| ENEV3 | Utilidades | 5,00% | 60,08% | 40,76% |
| FLRY3 | Saúde | 5,00% | 70,72% | 56,73% |
| ITSA4 | Financeiro | 5,00% | 44,89% | 42,38% |
| ABEV3 | Consumo | 5,00% | 34,85% | 27,36% |
| GGBR4 | Materiais básicos | 5,00% | 38,42% | 37,29% |
| CPLE3 | Utilidades | 5,00% | 35,03% | 33,33% |
| USIM5 | Materiais básicos | 5,00% | 41,90% | 52,22% |
| BRAP4 | Materiais básicos | 5,00% | 29,01% | 28,74% |
| VALE3 | Materiais básicos | 5,00% | 22,52% | 27,36% |
| B3SA3 | Financeiro | 5,00% | 55,64% | 92,86% |
| WEGE3 | Indústria | 5,00% | 24,67% | 30,28% |
| BPAC11 | Financeiro | 5,00% | 38,17% | 76,79% |
| ITUB4 | Financeiro | 5,00% | 29,60% | 43,31% |
| CMIG4 | Utilidades | 5,00% | 15,05% | 33,90% |
| CPFE3 | Utilidades | 5,00% | 20,42% | 39,74% |

Os nocionais de cada formação estão no CSV de carteiras. A tabela do dashboard informa pesos-alvo e valores aproximados sobre o PL final; pesos correntes podem divergir por preços. O monitor reconstrói esses pesos, mas só calcula PL indicativo se houver cobertura integral de cotações.

## Arquivos e reprodução

O pacote contém o código corrigido, testes, configuração do universo, dados originais e conferidos, eventos, correções, divergências, hashes, relatório, logs de execução e o dashboard autônomo. Não inclui os ZIPs completos da B3, preservados no projeto em `work/b3_raw/`; os URLs/hashes e o CSV extraído permitem auditar a origem.

Na raiz do projeto, com Python 3.11+ e dependências instaladas:

```shell
python -m src.run --start 2018-01-01 --end 2026-11-05 --market-csv output/cache_precos_auditados.csv --cdi-csv output/cache_cdi_sgs12.csv --benchmark-csv output/cache_ibov_yahoo.csv --audit-json output/auditoria_fontes.json --momentum-weight 0.75 --n-assets 20 --cost-bps 20
python -m unittest discover -s tests -v
python tests/validate_real_run.py
python -m src.market_server --provider brapi --refresh-min 30
```

Para baixar uma base nova, execute `python -m src.run --start 2018-01-01 --end DATA_FIM_EXCLUSIVA --refresh`. O pipeline padrão executa a conferência B3; não foi usada a opção `--skip-b3-audit`.

Dependências desta execução: numpy 2.4.6, pandas 2.3.3, yfinance 1.4.0, requests 2.34.2. Os hashes dos arquivos de entrada e do código estão em `manifesto_execucao.json`. Alterações nos fornecedores podem mudar resultados de um novo download; o cache entregue preserva esta amostra.
