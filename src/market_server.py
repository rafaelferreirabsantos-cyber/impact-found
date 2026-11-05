"""Servidor local de pesquisa; por padrão somente em 127.0.0.1, sem autenticação pública.

Serve v3/v4 de dentro do projeto e fornece /api/market; cotações atualizadas por
thread agendada a cada 30 minutos, com timestamp ORIGINAL do provedor.
Nunca expor na internet sem proxy autenticado e licenças de redistribuição.
"""
from __future__ import annotations
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import json
import threading
import time
from urllib.parse import urlsplit
from .market_monitor import get_market_snapshot

ROOT=Path(__file__).resolve().parents[1]

class QuoteState:
    def __init__(self, root:Path, provider:str, refresh_seconds:int):
        self.root=root;self.provider=provider;self.refresh_seconds=refresh_seconds
        self.data=None;self.error=None;self.last_refresh_utc=None
        self.lock=threading.Lock();self.stop_event=threading.Event()
        prior=root/'output'/'market_snapshot.json'
        if prior.exists():
            try: self.data=json.loads(prior.read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
    def refresh(self):
        try:
            value=get_market_snapshot(self.root,provider=self.provider)
            with self.lock:
                self.data=value;self.error=None;self.last_refresh_utc=datetime.now(timezone.utc).isoformat()
            print('[market] atualizado:',len(value.get('quotes',[])),'cotações | status',value.get('status'),flush=True)
        except Exception as exc:
            with self.lock:self.error=str(exc)[:350]
            print('[market] falha na coleta; dados anteriores preservados:',self.error,flush=True)
    def loop(self):
        while not self.stop_event.is_set():
            self.refresh()
            self.stop_event.wait(self.refresh_seconds)
    def snapshot(self):
        with self.lock:
            if self.data is None:
                return {'schema':'impact-market-snapshot/1','status':'aguardando_primeira_coleta',
                        'provider':self.provider,'quotes':[],'portfolio':None,'errors':[],
                        'server_error':self.error}
            return {**self.data,'server_error':self.error,
                    'last_successful_refresh_utc':self.last_refresh_utc}

class Handler(SimpleHTTPRequestHandler):
    quote_state=None
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/market':
            data=self.quote_state.snapshot()
            body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body);return
        if path=='/':
            target='/output/dashboard_com_resultados.html' if (ROOT/'output'/'dashboard_com_resultados.html').exists() else '/dashboard/index.html'
            self.send_response(302);self.send_header('Location',target);self.end_headers();return
        super().do_GET()


def main():
    p=argparse.ArgumentParser(description='Site local com cotações B3 em intervalos de atualização')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--provider',choices=['brapi','yahoo_eod'],default='brapi')
    p.add_argument('--refresh-min',type=int,default=30)
    args=p.parse_args()
    if args.refresh_min<5: p.error('Atualização mínima: 5 minutos (prover cotações NÃO torna dados mais recentes)')
    q=QuoteState(ROOT,args.provider,args.refresh_min*60)
    Handler.quote_state=q
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    bg=threading.Thread(target=q.loop,name='market-poll',daemon=True);bg.start()
    print(f'Abra http://127.0.0.1:{args.port}/ | fonte={args.provider}, atualização cada {args.refresh_min} min',flush=True)
    print('Uso local de pesquisa; não exponha publicamente esta porta.',flush=True)
    try: server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt: pass
    finally:q.stop_event.set();server.server_close()

if __name__=='__main__':main()
