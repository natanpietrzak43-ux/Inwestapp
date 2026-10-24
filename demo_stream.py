"""Optional private DEMO WebSocket wakes REST reconciliation, never places orders."""
import json
import os
import threading
import time
import okx_demo
import runtime_ops

URL='wss://wspap.okx.com:8443/ws/v5/private'


def login_message(key,secret,passphrase,now):
    stamp=str(int(now))
    return {'op':'login','args':[{'apiKey':key,'passphrase':passphrase,'timestamp':stamp,
                                'sign':okx_demo.sign(secret,stamp,'GET','/users/self/verify')}]}


class Feed:
    def __init__(self,wake):self.wake=wake;self.shutdown=threading.Event();self.thread=None
    def run(self):
        try:from websockets.sync.client import connect
        except ImportError:
            runtime_ops.heartbeat('demo-stream',{'status':'REST fallback; optional websockets package missing'});return
        delay=1
        while not self.shutdown.is_set():
            if not okx_demo.configured() or os.environ.get('INWESTAPP_DEMO_WEBSOCKET','1')!='1':
                runtime_ops.heartbeat('demo-stream',{'status':'idle'});self.shutdown.wait(15);continue
            try:
                with connect(URL,open_timeout=10,close_timeout=2,max_size=2_000_000) as ws:
                    key,secret,passphrase=okx_demo.credentials()
                    clock=okx_demo.Client();clock.sync_time()
                    ws.send(json.dumps(login_message(key,secret,passphrase,time.time()+clock.offset)))
                    reply=json.loads(ws.recv(timeout=10))
                    if reply.get('event')!='login' or reply.get('code')!='0':raise ValueError('Demo login not confirmed')
                    ws.send(json.dumps({'op':'subscribe','args':[{'channel':'orders','instType':'SWAP'},{'channel':'positions','instType':'SWAP'},{'channel':'account'}]}))
                    self.wake.set();delay=1
                    while not self.shutdown.is_set():
                        try:message=ws.recv(timeout=20)
                        except TimeoutError:
                            ws.send('ping');message=ws.recv(timeout=10)
                        runtime_ops.heartbeat('demo-stream',{'status':'connected; snapshots verified by REST'})
                        if message=='pong':continue
                        payload=json.loads(message)
                        if payload.get('event')=='error':raise ValueError('Demo stream error')
                        # Never execute or trust an isolated event as account state.
                        # Duplicate, out-of-order, gap and reconnect all re-read REST.
                        if payload.get('data'):self.wake.set()
            except Exception:
                runtime_ops.heartbeat('demo-stream',{'status':'REST fallback; reconnect pending'})
                self.wake.set();self.shutdown.wait(delay);delay=min(60,delay*2)
    def start(self):self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):
        self.shutdown.set()
        if self.thread:self.thread.join(timeout=2)
