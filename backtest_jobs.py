"""One durable historical simulation at a time; never dispatches exchange orders."""
from datetime import datetime, timezone
import json
import threading
import uuid
import execution_context
from user_data import database, data_dir, now_iso

LOCK=threading.RLock()
WORKERS={}
ACTIVE=('queued','running','cancelling')


def schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS backtest_jobs(id TEXT PRIMARY KEY,created_at TEXT,updated_at TEXT,state TEXT,phase TEXT,config TEXT,report_id TEXT,error TEXT)')


def records(identifier=None):
    with database() as conn:
        schema(conn)
        rows=conn.execute('SELECT * FROM backtest_jobs WHERE id=?',(identifier,)).fetchall() if identifier else conn.execute('SELECT * FROM backtest_jobs ORDER BY created_at DESC LIMIT 10').fetchall()
    result=[{**dict(row),'config':json.loads(row['config'])} for row in rows]
    if identifier:
        if not result:raise ValueError('Nie znaleziono testu.')
        return result[0]
    return result


def change(identifier,**values):
    allowed={'state','phase','report_id','error'}
    if not set(values)<=allowed:raise ValueError('Niedozwolone pole zadania.')
    values['updated_at']=now_iso()
    with database() as conn:
        schema(conn)
        conn.execute('UPDATE backtest_jobs SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),identifier))


def recover():
    with database() as conn:
        schema(conn)
        conn.execute("UPDATE backtest_jobs SET state='interrupted',phase='Przerwane przez restart',error='Uruchom test ponownie. Nie wznowiono go automatycznie.',updated_at=? WHERE state IN ('queued','running','cancelling')",(now_iso(),))


def submit(config,callback):
    """config must already be normalized by the same validator as legacy replay."""
    root=data_dir().resolve();identifier=uuid.uuid4().hex;now=now_iso();event=threading.Event()
    with LOCK:
        with database() as conn:
            schema(conn);conn.execute('BEGIN IMMEDIATE')
            active=conn.execute("SELECT id FROM backtest_jobs WHERE state IN ('queued','running','cancelling') LIMIT 1").fetchone()
            if active:raise ValueError('Trwa już test historyczny. Poczekaj na wynik albo anuluj go w panelu.')
            conn.execute('INSERT INTO backtest_jobs VALUES(?,?,?,?,?,?,?,?)',(identifier,now,now,'queued','Oczekuje na obliczenia',json.dumps(config),None,None))
        def run():
            token=execution_context.root.set(root);cancel_token=execution_context.cancellation.set(event)
            try:
                def phase(value):
                    execution_context.check_cancelled();change(identifier,state='running',phase=value)
                phase('Pobieranie zamkniętych świec')
                report=callback(config,phase)
                change(identifier,state='completed',phase='Raport zapisany',report_id=report['id'])
            except execution_context.Cancelled:
                change(identifier,state='cancelled',phase='Test anulowany')
            except ValueError as error:
                change(identifier,state='failed',phase='Test nieukończony',error=str(error)[:700])
            except Exception:
                change(identifier,state='failed',phase='Test nieukończony',error='Nie potwierdzono wyniku. Sprawdź dane i ponów test. Konto bota nie zostało zmienione.')
            finally:
                execution_context.cancellation.reset(cancel_token);execution_context.root.reset(token)
                with LOCK:WORKERS.pop(identifier,None)
        thread=threading.Thread(target=run,daemon=True,name='historical-backtest')
        WORKERS[identifier]=(event,thread,root)
        thread.start()
    return records(identifier)


def cancel(identifier):
    with LOCK:
        job=records(identifier)
        worker=WORKERS.get(identifier)
        if job['state'] in ACTIVE and worker and worker[2]==data_dir().resolve():
            worker[0].set();change(identifier,state='cancelling',phase='Anulowanie po bieżącej operacji')
    return records(identifier)


def shutdown():
    with LOCK:workers=list(WORKERS.values())
    for event,_,_ in workers:event.set()
    for _,thread,_ in workers:thread.join(timeout=1)
