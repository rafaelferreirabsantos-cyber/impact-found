# Como contribuir

1. Leia o [guia dos trainees](docs/GUIA_TRAINEES.md), o relatório e as limitações.
2. Escolha uma tarefa no [backlog](docs/BACKLOG.md). Registre escopo e evidência
   esperada antes de modificar regras quantitativas.
3. Crie uma branch: `git switch -c feat/descricao-curta` ou `fix/descricao-curta`.
   Sem acesso direto, use um fork.
4. Trabalhe em uma mudança por PR. Mantenha resultados experimentais em
   `experiments/<nome>/`, fora do Git por padrão.
5. Execute `python -m unittest discover -s tests -v` e
   `python scripts/check_repository.py`.
6. Para mudanças no cálculo, restaure a base congelada e execute também
   `python tests/validate_stage2_real.py`. Documente diferenças, sem reescrever a
   referência para esconder regressões.
7. Abra um pull request com problema, alteração, evidência e limitações. Aguarde
   revisão do responsável antes de integrar na `main`.

## Pesquisa e dados

- Não substitua preço ausente por dado sintético ou preenchimento implícito.
- Fixtures artificiais devem ficar nos testes, identificadas e isoladas.
- Não troque parâmetros porque melhoraram o histórico. Registre hipóteses antes
  do experimento e separe diagnóstico retrospectivo de teste prospectivo.
- Mudança de dado deve citar URL, data, hash anterior/novo e efeito no resultado.
- Não altere o protocolo congelado para fazer um teste existente passar.
- Não misture preços brutos com retorno total nem credite dividendos duas vezes.
- Preserve o template e a identidade visual; alterações de UI exigem conferência
  de gráficos, filtros, estados e legibilidade.

## Segurança e arquivos

Nunca envie `.env`, tokens, credenciais, chaves privadas, dados pessoais de
trainees ou arquivos de contas financeiras. Não adicione bibliotecas instaladas,
ambientes virtuais ou ZIPs grandes ao histórico Git. Consulte [SECURITY](SECURITY.md)
e o [catálogo de dados](docs/DADOS_E_FONTES.md).

Não há exigência de assinar um acordo de contribuição neste repositório.
Questões de licença devem ser resolvidas com o responsável antes de reutilização
externa que dependa de uma licença ainda não definida.
