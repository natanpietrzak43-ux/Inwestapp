"""Single-worker lease, durable operational events, heartbeats and backups."""
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import urllib.request
import urllib.parse
import uuid
from contextlib import closing
import notification_channel
from user_data import database,data_dir,now_iso


class WorkerLease:
    def __init__(self,directory=None):self.directory=Path(directory or data_dir());self.file=None
    def acquire(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        f=open(self.directory/'worker.lock','a+b')
        if f.tell()==0:f.write(b'0');f.flush()
        try:
            if os.name=='nt':
                import msvcrt
                f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:f.close();raise ValueError('Inny wykonawca korzysta z tej samej bazy. Zatrzymaj jego serwer przed uruchomieniem kolejnego.') from None
        self.file=f;return self
    def close(self):
        if self.file:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            self.file.close();self.file=None
    def __enter__(self):return self.acquire()
    def __exit__(self,*args):self.close()


def schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS ops_events(id TEXT PRIMARY KEY,created_at TEXT,kind TEXT,scope TEXT,data TEXT,delivered INTEGER DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS runtime_heartbeats(name TEXT PRIMARY KEY,updated REAL,data TEXT)')


def event(kind,detail,scope='system'):
    # Callers supply fixed explanations, not raw transport errors or credentials.
    with database() as conn:
        schema(conn)
        last=conn.execute('SELECT created_at FROM ops_events WHERE kind=? AND scope=? ORDER BY created_at DESC LIMIT 1',(kind,scope)).fetchone()
        if last:
            from datetime import datetime
            if time.time()-datetime.fromisoformat(last['created_at']).timestamp()<60:return
        conn.execute('INSERT INTO ops_events VALUES(?,?,?,?,?,0)',(str(uuid.uuid4()),now_iso(),kind,scope,json.dumps({'detail':str(detail)[:1500]})))


def heartbeat(name,detail):
    with database() as conn:
        schema(conn);conn.execute('INSERT INTO runtime_heartbeats VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET updated=excluded.updated,data=excluded.data',(name,time.time(),json.dumps(detail)))


def status():
    with database() as conn:
        schema(conn)
        beats=[{'name':r['name'],'ageSeconds':max(0,time.time()-r['updated']),**json.loads(r['data'])} for r in conn.execute('SELECT * FROM runtime_heartbeats')]
        events=[dict(r) for r in conn.execute('SELECT * FROM ops_events ORDER BY created_at DESC LIMIT 50')]
    required={'paper-worker','demo-worker','supervisor'}
    return {'heartbeats':beats,'events':events,'notificationConfigured':bool(os.environ.get('INWESTAPP_ALERT_WEBHOOK')) or notification_channel.configured(),
            'healthy':required.issubset({b['name'] for b in beats}) and all(b['ageSeconds']<90 for b in beats if b['name']!='demo-stream'),'backupFiles':sorted(p.name for p in (data_dir()/'backups').glob('*.sqlite3'))[-20:]}


def backup():
    folder=data_dir()/'backups';folder.mkdir(parents=True,exist_ok=True)
    name=time.strftime('%Y%m%dT%H%M%S',time.gmtime())+'-'+uuid.uuid4().hex[:8]+'.sqlite3'
    path=folder/name
    with database() as source,closing(sqlite3.connect(path)) as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Niepoprawna kopia bazy danych.')
    if os.name!='nt':path.chmod(0o600)
    return {'file':name,'bytes':path.stat().st_size,'verified':True}


def notify_pending():
    url=os.environ.get('INWESTAPP_ALERT_WEBHOOK','')
    if not url and not notification_channel.configured():return
    if url:
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Webhook wymaga HTTPS bez danych logowania w adresie.')
    with database() as conn:
        schema(conn);rows=list(conn.execute('SELECT * FROM ops_events WHERE delivered=0 ORDER BY created_at LIMIT 3'))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    for row in rows:
        payload={'app':'Inwestapp','eventId':row['id'],'at':row['created_at'],'kind':row['kind'],'scope':row['scope'],'message':json.loads(row['data'])['detail']}
        try:
            if url:
                req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.build_opener(NoRedirect()).open(req,timeout=5) as response:
                    if not 200<=response.status<300:raise ValueError()
            else:notification_channel.send(payload)
        except Exception:raise ValueError('Kanał alarmowy nie potwierdził odbioru. Sprawdź prywatną konfigurację; zdarzenie pozostaje do ponowienia.') from None
        with database() as conn:conn.execute('UPDATE ops_events SET delivered=1 WHERE id=?',(row['id'],))


class Supervisor:
    def __init__(self):self.shutdown=threading.Event();self.thread=None;self.last_backup=0
    def pulse(self):
        heartbeat('supervisor',{'status':'running'})
        for beat in status()['heartbeats']:
            if beat['name'] not in ('supervisor','demo-stream') and beat['ageSeconds']>90:event('worker_stale','Brak aktualnego cyklu wykonawcy; sprawdź usługę.',beat['name'])
        if time.time()-self.last_backup>86400:
            backup();self.last_backup=time.time()
        notify_pending()
    def run(self):
        while not self.shutdown.is_set():
            try:self.pulse()
            except Exception:pass  # failures never expose configured webhook credentials
            self.shutdown.wait(30)
    def start(self):self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def stop(self):
        self.shutdown.set()
        if self.thread:self.thread.join(timeout=6)
