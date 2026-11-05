# Instalação e reprodução

## Ambiente

Use Python 3.11+ e execute os comandos na raiz do repositório. Recomenda-se um
ambiente virtual novo para não alterar bibliotecas de outros projetos.

```shell
python -m venv .venv
```

Windows (PowerShell): `.venv\Scripts\Activate.ps1`. Alternativa sem ativação:
`.venv\Scripts\python.exe -m pip install -r requirements-validation.txt`.
Linux/macOS: `source .venv/bin/activate`.

```shell
python -m pip install -r requirements-validation.txt
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

O ambiente de referência está em [AMBIENTE_REFERENCIA](../data/AMBIENTE_REFERENCIA.json).
As faixas de versão de `requirements*.txt` permitem instalação em diferentes
versões de Python. Para comparar resultados, registre também as versões locais.

## Dashboard e monitor

O HTML de referência já está em `output/dashboard_com_resultados.html`. Abra-o
diretamente no navegador para analisar os gráficos congelados, ou execute:

```shell
python -m src.market_server --provider brapi --refresh-min 30
```

Abra http://127.0.0.1:8765/. A aba Validação mostra a segunda etapa; a primeira
curva continua identificada como etapa 1 preservada.

Sem token, o provedor limita as cotações. Para configurar, defina `BRAPI_TOKEN`
somente no ambiente do processo. `.env.example` é explicativo: não há carregador
automático de `.env`. O monitor não executa ordens e não completa cotações ausentes.

## Restaurar os dados congelados

```shell
python scripts/research_data.py --list
python scripts/research_data.py --download-research
```

O pacote da Release contém todos os caches, cenários, logs e o snapshot exigidos
pelas conferências independentes. O script verifica tamanho e SHA-256, rejeita
caminhos inseguros e não substitui arquivos diferentes por padrão.

Para usar um ZIP previamente baixado:

```shell
python scripts/research_data.py --restore caminho/impact-found-pesquisa-2026-11-05.zip
```

Se você modificou um resultado local e deseja restaurar a referência, use
`--backup-conflicts` junto do comando. As versões locais divergentes são copiadas
para `work/restore-backups/` antes da restauração.

## Reproduzir a etapa 2

```shell
python -m src.validation_audit
python -m src.validation
python tests/validate_stage2_real.py
python -m src.validation_report
```

São comandos sequenciais: interrompa se um deles falhar. Não use resultados
parciais para substituir os artefatos de referência.

`src.validation` confere o hash do protocolo congelado antes das comparações.
O arquivo de referência usa o corte exclusivo 05/11/2026. Dados futuros não são
criados pelo plano prospectivo; os registros publicados permanecem vazios.

## Fontes B3 completas e coleta nova

Para conferir os ZIPs COTAHIST usados originalmente:

```shell
python scripts/research_data.py --download-b3
python -m src.validation_data
```

O download B3 é separado e tem centenas de MB. Arquivos originais ficam em
`work/b3_raw/`, fora do Git, com SHA-256 no manifesto. Os caches da Release são
suficientes para a reprodução principal; não é obrigatório baixar os ZIPs.

Para estudar uma amostra nova, use um diretório de saída próprio:

```shell
python -m src.run --start 2018-01-01 --end AAAA-MM-DD --refresh --output-dir experiments/nova-amostra
```

Substitua a data por um fim exclusivo real. Esse comando coleta novamente os
dados e exige nova auditoria; não equivale a repetir a amostra congelada.
Revise proventos, disponibilidade, mudanças de ticker e hashes. Não altere a
referência publicada para fazê-la coincidir com uma revisão do fornecedor.

## Problemas comuns

| Sintoma | Verificação |
|---|---|
| Falta de CSV ou snapshot | Restaure o pacote de pesquisa antes dos validadores reais |
| Falha de teste unitário | Confira ambiente, versão de Python e dependências |
| Falha de rede | Execute `python diagnosticar_rede.py`; diferencie DNS, HTTP e limite de API |
| Hash divergente | Preserve o arquivo; não ignore a diferença para continuar |
| PL indicativo indisponível | Confira cobertura do monitor; ela é independente do histórico |
| CDI ou preço ausente | Corrija a fonte ou declare o período possível; não preencha com zero |

Os validadores reais não são os testes unitários e precisam dos caches completos.
Os testes automáticos de CI não baixam dados de mercado nem fabricam desempenho.
