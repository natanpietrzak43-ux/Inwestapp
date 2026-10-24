"""Offline verified restore, retaining a recoverable copy of previous database."""
import argparse
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from user_data import data_dir
from runtime_ops import WorkerLease


def restore(source,apply=False):
    source=Path(source).resolve(strict=True)
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as old:
        if old.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Kopia jest uszkodzona.')
        if not apply:return {'verified':True,'applied':False}
        with WorkerLease():
            root=data_dir();target=root/'inwestapp.sqlite3'
            if source==target.resolve():raise ValueError('Źródło nie może być bieżącą bazą.')
            if target.exists():
                archive=root/'backups'/('before-restore-'+uuid.uuid4().hex+'.sqlite3');archive.parent.mkdir(parents=True,exist_ok=True)
                with closing(sqlite3.connect(target)) as current,closing(sqlite3.connect(archive)) as backup:current.backup(backup)
                if os.name!='nt':archive.chmod(0o600)
            temp=root/('restore-'+uuid.uuid4().hex+'.sqlite3')
            with closing(sqlite3.connect(temp)) as new:old.backup(new)
            if os.name!='nt':temp.chmod(0o600)
            for suffix in ('-wal','-shm'):
                path=Path(str(target)+suffix)
                if path.exists():path.unlink()
            temp.replace(target)
    return {'verified':True,'applied':True,'previousPreserved':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file');parser.add_argument('--apply',action='store_true',help='Odtwórz dopiero po zatrzymaniu wszystkich serwerów.');args=parser.parse_args()
    print(restore(args.file,args.apply))
