ImpactUFSCar Found — Evolução v1.0 → v2.0
==========================================
V1: site com séries de rentabilidade sintéticas e carteira meramente ilustrativa.
V2: site com área vazia até carregar dados de backtest e motor Python determinístico.

ENTREGUE:
- Script Python para baixar Adj Close/Close/Volume de ações B3 do Yahoo Finance.
- CDI diário por BCB SGS 12; benchmark Ibovespa.
- Signals 12–1, baixa volatilidade 63 dias, percentis 75/25.
- Filtro de liquidez, setor, emissor, equal weight até 20 ações.
- Rebalanceamento no pregão seguinte (fechamento), custos 20bps/nocional.
- Série diária de PL, custos, carteiras, ordens, VaR/ES, Sharpe, drawdown.
- JSON auditável, dashboard responsivo com importação de resultados históricos.
- Testes unitários e fluxo Windows, Linux e Mac.

AINDA NÃO ENTREGUE:
- Retornos históricos de verdade calculados e verificados no ambiente desta sessão:
  as APIs de preços/CDI não puderam ser alcançadas durante esta execução.
- Carteiras históricas completas do IBrX 100 e ativos deslistados.
- Execução realista intradiária com volume e impacto, impostos/taxas de fundo.
- Validação robusta out-of-sample ou evidência de superação do CDI.

Uma vez baixadas as séries no computador do usuário, o programa as processa
sem precisar preencher manualmente rentabilidades. Nunca serão criadas
métricas fictícias para suprir falhas de uma fonte.
