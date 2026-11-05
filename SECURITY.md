# Segurança

O servidor de pesquisa foi projetado para uso local em `127.0.0.1`. Ele não é um
serviço autenticado para exposição pública. Não transforme a porta local em um
endpoint público sem projeto específico de autenticação e operação.

Credenciais do provedor, quando necessárias, devem ser fornecidas ao processo
por variável de ambiente. `.env.example` não contém segredo e `.env` é ignorado
pelo Git. O projeto não carrega `.env` automaticamente.

Se encontrar uma credencial ou vulnerabilidade, não copie o segredo para issue,
PR, notebook ou captura de tela. Comunique o mantenedor por um canal privado;
se o GitHub disponibilizar relato privado de vulnerabilidade para este
repositório, use esse recurso. Revogue credenciais expostas antes de apenas
remover o arquivo de uma branch.

Issues públicas são adequadas para erros reproduzíveis sem informação sensível.
Não envie ordens reais, dados de investidores ou acesso a contas financeiras:
o projeto é de pesquisa e não executa operações na bolsa.
