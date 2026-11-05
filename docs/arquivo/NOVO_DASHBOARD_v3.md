# ImpactUFSCar Found — atualização visual e funcional v3.0

## Preservado do arquivo original
- Layout de página única, seções e navegação responsiva.
- Hero, gráfico da cota, KPIs, mapa de retornos mensais, carteira, risco e metodologia.
- Laboratório interativo com ajuste de parâmetros e calculadora de sinal.
- Gráficos SVG próprios, sem frameworks externos de visualização.

## Ajustado
- Paleta adaptada ao padrão bordô/vinho, vermelho e neutros da Impact.
- Mandato-base: R$ 100 milhões fictícios; 75% Momentum 12–1 + 25% baixa volatilidade; até 20 ações igualmente ponderadas; 30% por setor; Brasil; meta CDI.
- Hedge e controle automático de volatilidade desligados no cenário-base, mas preservados como experiências opcionais no modo sintético.
- Integração com `src.run`: JSON gerado pelo motor Python pode ser importado pelo navegador ou embutido automaticamente no HTML final.
- Avisos claros separando série sintética e backtest com preços históricos.

## Limites
- Arquivo de demonstração mantém séries e empresas inventadas; o histórico não vem incluído no pacote.
- Modo histórico tem universo retrospectivo por padrão e pode conter vieses importantes.
- Motor Python não inclui taxas de administração e performance, hedge real, impostos e slippage dinâmico.
- Modo histórico não atualiza o backtest ao mover sliders: nova combinação exige reexecutar o Python.

## Sequência sugerida para pesquisa
1. Executar o Python e inspecionar erros das fontes e a qualidade dos dados.
2. Fazer o backtest com universo point-in-time e deslistagens.
3. Comparar parâmetros pré-definidos e fazer testes fora da amostra.
4. Validar liquidez / execução para R$ 100 milhões e custos reais.
5. Preparar relatório metodológico e auditoria antes de divulgação pública.

- Validação do arquivo JSON verifica sua estrutura, não a procedência/autenticidade dos dados.
