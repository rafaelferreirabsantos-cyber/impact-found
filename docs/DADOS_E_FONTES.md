# Dados, fontes e arquivos de pesquisa

## Onde está cada coisa

| Material | Destino | Motivo |
|---|---|---|
| Código, testes, configurações e notebook | Git | Revisão e colaboração |
| Dashboard, relatório e tabelas resumidas | Git | Consulta imediata, sem recalcular |
| Caches completos, cenários detalhados e logs | Pacote de pesquisa na Release | Amostra congelada reproduzível |
| Snapshot de código/resultados da etapa 1 | Dentro do pacote, `work/etapa2/` | Conferir preservação byte a byte |
| Nove ZIPs COTAHIST B3 de 2018–2026 | Assets separados na Release | Evitar inflar o histórico de commits |
| PDFs de emissores | URL e hash no manifesto CVM; original local preservado | Não republicar integralmente conteúdo de terceiros |
| Bibliotecas instaladas e ambientes | Reinstalar por `requirements*.txt` | Não versionar runtime/cache |
| Capturas transitórias de mercado | Local | Não confundir cotação atual com amostra histórica |

Veja [INVENTARIO_ORIGINAL.json](../data/INVENTARIO_ORIGINAL.json) para todos os
arquivos inventariados e o destino de cada um. Os arquivos originais não foram
apagados. A organização evita duplicar o mesmo ZIP de 2021 e caches regeneráveis.

## Manifesto e restauração

[RELEASE_MANIFEST.json](../data/RELEASE_MANIFEST.json) registra nome, tamanho,
SHA-256, URL e destino de cada asset. O pacote de pesquisa contém dados e
evidências numéricas suficientes para a reprodução principal.

```shell
python scripts/research_data.py --download-research
python scripts/research_data.py --download-b3
```

O primeiro comando restaura caches e resultados. O segundo é opcional e baixa
centenas de MB dos originais B3. Também é possível baixar arquivos pela página
de [Releases](https://github.com/rafaelferreirabsantos-cyber/impact-found/releases)
e passar o ZIP ao argumento `--restore`.

Arquivos diferentes não são sobrescritos por padrão. Use uma cópia de trabalho
ou `--backup-conflicts`, que preserva a versão local antes de restaurar.

## Fontes

- Yahoo Finance, via yfinance: fechamento ajustado, fechamento e volume; eventos
  declarados pelo provedor. Ajustes são retrospectivos e sujeitos a revisão.
- Banco Central, SGS 12: CDI em percentual por dia, convertido antes de compor.
- B3 COTAHIST: preços brutos, quantidade, volume financeiro e ISIN por sessão.
- B3, estatísticas de índices: fechamentos oficiais de Ibovespa e IBrX 100.
- Avisos originais de emissores arquivados na CVM: eventos societários revistos.

Os URLs/hashes estão em `output/auditoria_fontes.json`,
`output/validacao_etapa2/fontes_indices.json` e no
[manifesto CVM](../output/validacao_etapa2/fontes/manifesto_documentos_cvm.json).
O primeiro arquivo integra o pacote completo.

## Regras de integridade

Não fabrique histórico ausente. Não encadeie ticker antigo e novo por mera troca
de nome. Não use preços brutos como retorno total. Não credite dividendos duas
vezes. Uma revisão do fornecedor deve ser registrada como versão nova.

CPLE6, BRFS3, JBSS3 e MRFG3 possuem preços brutos recuperados na B3, mas continuam
fora das quatro comparações por falta de uma cadeia completa de retorno total
validada. A lista de 47 séries não elimina o viés de sobrevivência.

O repositório não concede direitos sobre bases de terceiros. Preserve atribuição,
consulte as condições dos provedores e não trate a licença do código como
licença dos dados. O material público continua sendo pesquisa, sem distribuição
de cotações em tempo real ou oferta de investimento.
