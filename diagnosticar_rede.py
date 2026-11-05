"""Diagnóstico de rede para coleta de dados do ImpactUFSCar Found.

Execute no computador que rodará o backtest: python diagnosticar_rede.py
Nenhum token de API é exibido. Teste apenas de conectividade, não de licenciamento.
"""
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import socket
import ssl

TESTS = [
    ('Banco Central / CDI', 'api.bcb.gov.br', 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/10?formato=json'),
    ('brapi / Petrobras', 'brapi.dev', 'https://brapi.dev/api/quote/PETR4'),
    ('Yahoo / Petrobras', 'query1.finance.yahoo.com', 'https://query1.finance.yahoo.com/v8/finance/chart/PETR4.SA?range=5d&interval=1d'),
]

lines = ['ImpactUFSCar Found — diagnóstico de conectividade',
         'Horário UTC: ' + datetime.now(timezone.utc).isoformat(timespec='seconds'),
         'Observação: conexão ativa NÃO garante direito de redistribuir dados ou receber ticks em tempo real.\n']
for label, host, url in TESTS:
    print(f'\n=== {label} ===')
    try:
        addresses=socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addrs=sorted({x[4][0] for x in addresses})
        msg=f'DNS OK: {", ".join(addrs[:3])}'
        print(msg); lines.append(label+': '+msg)
    except Exception as exc:
        msg=f'Falha DNS: {exc}'
        print(msg); lines.append(label+': '+msg)
        continue
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 ImpactUFSCarResearch/1.0','Accept':'application/json'})
        with urlopen(req,timeout=12,context=ssl.create_default_context()) as r:
            blob=r.read(200)
            msg=f'HTTPS OK: status {r.status}, início da resposta {blob[:65]!r}'
    except HTTPError as exc:
        msg=f'HTTPS respondeu com status {exc.code}: acesso/rate limit/API; rede pode estar funcionando'
    except (URLError, OSError, TimeoutError) as exc:
        msg=f'Falha de conexão: {str(exc)[:260]}'
    print(msg); lines.append(label+': '+msg)
path=Path(__file__).resolve().parent/'diagnostico_rede.txt'
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\nRelatório salvo em:',path)
