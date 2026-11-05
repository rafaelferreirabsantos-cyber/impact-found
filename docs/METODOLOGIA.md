# Metodologia e convenções

## Formação

Na data de decisão t, após o fechamento:

```text
Momentum = AdjClose[t−21] / AdjClose[t−252] − 1
Volatilidade = desvio padrão amostral dos últimos 63 retornos × √252
Score = 0,75 × percentil Momentum + 0,25 × percentil inverso da volatilidade
```

Percentis usam `(rank médio − 1)/(N−1)`, com extremos 0 e 1 e rank médio em
empates. O conjunto de comparação é o conjunto elegível naquela formação.
O sinal exige janela completa de preços e o filtro de liquidez ADV21.

## Seleção e execução

Até 20 nomes por score, peso nominal 5%, máximo 30% por setor e 5% por emissor.
Quando faltam nomes, a parcela não investida fica em caixa CDI. Os limites são
de formação; não há recomposição diária para eliminar deriva dos preços.

O sinal nasce após o último fechamento do mês. A execução é modelada no
fechamento da próxima sessão. A posição anterior recebe o retorno até a execução;
a posição nova rende apenas a partir do intervalo posterior. Negociação ao
fechamento é proxy, sem livro de ordens, filas ou liquidação D+2 reconstruída.

Custos-base: 20 bps por nocional em compras e vendas. O PL após custos determina
os novos nocionais. Não há liquidação final forçada da carteira no fim da amostra.

## Preços e CDI

O motor usa retorno ajustado, com proventos incorporados uma única vez. Dividendos
não são creditados novamente no caixa. Isso não é reconstrução de custódia por
data de pagamento. As correções de UGPA3 e dos eventos BRAP4/MGLU3 ficam
documentadas em CSVs e relatórios, com preservação das séries originais.

A convenção CDI corrigida é início inclusivo/fim exclusivo entre dois fechamentos,
incluindo taxas de dias bancários sem pregão. A convenção antiga permanece
acessível apenas para reprodução da etapa 1. Não há substituição de taxa ausente
por zero, interpolação de preço ou saída fictícia de ativo sem dados.

## Risco e comparação

O relatório define Sharpe sobre CDI, Sortino com alvo CDI, Calmar, drawdown,
volatilidade, VaR/ES e turnover one-way. Os quatro modelos de carteira têm o
mesmo custo-base. Índices são referências teóricas sem custo de replicação.
Equal Weight de todos os elegíveis é referência de diversificação, não carteira
aderente ao limite de 20 e aos tetos de emissor/setor do mandato.

Regimes usam dados do Ibovespa até t−1, tendência de 126 sessões e volatilidade de
63 sessões, com limiar fixo de 25% a.a. Não se escolheu a mediana da amostra toda.
Drawdown em regime é o pior trecho contíguo; não se concatenam períodos separados.

## O que continua pendente

Universo point-in-time completo, deslistados, todas as cadeias de conversão e
proventos, dados de execução para calibrar impacto, participação/ordens pendentes
e observação prospectiva. Ajustes atuais e setores atuais não se tornam dados
historicamente conhecidos apenas porque o cálculo de sinais é causal.

O status é condicional. A política de pesquisa não permite escolher pesos pelo
maior retorno histórico ou apresentar resultado exploratório como performance
de fundo real.
