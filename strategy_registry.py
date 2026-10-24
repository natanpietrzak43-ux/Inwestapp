"""Frozen versions, walk-forward evidence and explicit demo-only approval."""
import hashlib
import json
import uuid
import decision_engine
from user_data import database,now_iso


def schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS strategy_versions(id TEXT PRIMARY KEY,created_at TEXT,fingerprint TEXT,data TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS strategy_validations(id TEXT PRIMARY KEY,created_at TEXT,fingerprint TEXT,data TEXT)')


def register(cfg):
    item={'id':str(uuid.uuid4()),'created_at':now_iso(),'fingerprint':decision_engine.fingerprint(cfg),'config':cfg,'approved':False,'environment':'demo'}
    with database() as conn:schema(conn);conn.execute('INSERT INTO strategy_versions VALUES(?,?,?,?)',(item['id'],item['created_at'],item['fingerprint'],json.dumps(item)))
    return item


def save_validation(report):
    item={**report,'id':str(uuid.uuid4()),'created_at':now_iso()}
    with database() as conn:schema(conn);conn.execute('INSERT INTO strategy_validations VALUES(?,?,?,?)',(item['id'],item['created_at'],item['fingerprint'],json.dumps(item)))
    return item


def approve(identifier,validation_id,acknowledged):
    if acknowledged is not True:raise ValueError('Wymagane świadome zatwierdzenie wersji dla OKX Demo.')
    with database() as conn:
        schema(conn);conn.execute('BEGIN IMMEDIATE')
        version=conn.execute('SELECT data FROM strategy_versions WHERE id=?',(identifier,)).fetchone()
        validation=conn.execute('SELECT data FROM strategy_validations WHERE id=?',(validation_id,)).fetchone()
        if not version or not validation:raise ValueError('Brak wersji lub walidacji.')
        item=json.loads(version['data']);report=json.loads(validation['data'])
        if item['fingerprint']!=report['fingerprint'] or item['fingerprint']!=decision_engine.fingerprint(item['config']):raise ValueError('Konfiguracja lub kod zmieniły się od walidacji.')
        if not report.get('eligible'):raise ValueError('Walidacja nie spełnia kryteriów dopuszczenia; brak obejścia filtra.')
        item.update(approved=True,approvedAt=now_iso(),validationId=validation_id)
        conn.execute('UPDATE strategy_versions SET data=? WHERE id=?',(json.dumps(item),identifier))
    return item


def get(identifier,require_approved=False):
    with database() as conn:
        schema(conn);row=conn.execute('SELECT data FROM strategy_versions WHERE id=?',(identifier,)).fetchone()
    if not row:raise ValueError('Nie znaleziono wersji strategii.')
    item=json.loads(row['data'])
    if require_approved:
        from datetime import datetime,timezone
        if not item.get('approved') or item['fingerprint']!=decision_engine.fingerprint(item['config']):raise ValueError('Wersja niezatwierdzona albo kod/konfiguracja zmienione.')
        if (datetime.now(timezone.utc)-datetime.fromisoformat(item['approvedAt'])).total_seconds()>30*86400:raise ValueError('Dopuszczenie wygasło po 30 dniach; ponów walidację.')
    return item


def revoke(identifier):
    item=get(identifier);item.update(approved=False,revokedAt=now_iso())
    with database() as conn:conn.execute('UPDATE strategy_versions SET data=? WHERE id=?',(json.dumps(item),identifier))
    return item


def records():
    with database() as conn:
        schema(conn)
        return {'versions':[json.loads(r['data']) for r in conn.execute('SELECT data FROM strategy_versions ORDER BY created_at DESC LIMIT 30')],
                'validations':[{k:v for k,v in json.loads(r['data']).items() if k!='reports'} for r in conn.execute('SELECT data FROM strategy_validations ORDER BY created_at DESC LIMIT 30')]}
