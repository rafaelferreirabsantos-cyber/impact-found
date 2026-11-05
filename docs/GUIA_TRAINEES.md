# Guia dos trainees

## Primeiro contato

O ImpactUFSCar Found é uma plataforma de pesquisa de fatores em ações brasileiras.
O trabalho começa pela qualidade do dado e da pergunta. Uma curva crescente não
comprova alpha, capacidade operacional ou desempenho de fundo em operação.

Leia, nesta ordem:

1. [README](../README.md), para executar e entender o status atual.
2. [Metodologia](METODOLOGIA.md), para entender o sinal, os pesos e a execução.
3. [Relatório da etapa 2](../output/validacao_etapa2/RELATORIO_TECNICO.md), incluindo
   as seções de limitações e conclusões.
4. [Arquitetura](ARQUITETURA.md) e [reprodução](REPRODUCAO.md).
5. [CONTRIBUTING](../CONTRIBUTING.md), antes do primeiro PR.

## Trilha prática sugerida

| Etapa | Atividade | Evidência esperada |
|---|---|---|
| Ambiente | Clonar, criar `.venv`, instalar e rodar testes | Comando e saída dos testes |
| Interface | Abrir o dashboard e comparar estratégias/referências | Explicação das versões e do status condicional |
| Dados | Identificar fonte, unidade, ajuste e hash de uma série | Pequena ficha de proveniência |
| Sinal | Recalcular Momentum e percentis em uma formação | Conferência independente com data de corte |
| Execução | Explicar por que a compra não recebe retorno anterior à ordem | Exemplo com sinal e execução no calendário |
| Pesquisa | Reproduzir a etapa 2 usando caches | Comparação do cálculo com a referência |
| Contribuição | Resolver tarefa pequena do backlog | PR com teste e limitações |

## Exercícios iniciais

- Explique a diferença entre retorno do fundo fictício e do CDI.
- Recalcule o score de um ativo em uma formação, incluindo a regra de empates.
- Investigue uma linha do CSV de ordens: custo, ADV e data do sinal.
- Encontre uma exposição setorial que derivou acima de 30% entre formações e
  explique por que isso não significa que o teto da formação foi ignorado.
- Explique por que a série bruta de um código antigo não pode ser usada como
  retorno total sem proventos e eventos de conversão.
- Compare as hipóteses de custos fixos, slippage e taxas do relatório.

## Como escolher a primeira tarefa

Comece por documentação, verificação de uma fonte ou teste de um problema
concreto. Evite mudar janelas e pesos apenas para aumentar o resultado histórico.
O [backlog](BACKLOG.md) separa pendências de dados, execução e validação.

Use uma branch por tarefa. Sem permissão direta de escrita, use um fork e abra
PR para este repositório. Não é necessário acesso a contas de corretora ou a
credenciais de terceiros para estudar o material publicado.

## Perguntas que todo relatório deve responder

Qual a pergunta? Que dado era conhecido na decisão? Qual sua fonte/unidade?
Quais as limitações? O que foi testado? O que não pode ser concluído? A hipótese
foi definida antes do resultado? Outra pessoa consegue reproduzir os passos?
