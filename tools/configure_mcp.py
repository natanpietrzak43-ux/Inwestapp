"""Register a per-user global Codex MCP server. Never prints the credential."""
import argparse
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys


def configure(key,root=None):
    if not isinstance(key,str) or not 10<=len(key.strip())<=500 or any(c.isspace() for c in key.strip()):
        raise ValueError('Nieprawidłowy format klucza.')
    if not shutil.which('codex') or not shutil.which('node') or not shutil.which('npx'):
        raise ValueError('Wymagane są Codex CLI, Node.js i npx.')
    root=Path(root) if root else Path.home()/'.codex'
    destination=root/'trader-dev';destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(destination,0o700)
    key_file=destination/'api-key'
    fd=os.open(key_file,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(key.strip())
    os.chmod(key_file,0o600)
    bridge=destination/'bridge.cjs';bridge.write_bytes(Path(__file__).with_name('trader_mcp_bridge.cjs').read_bytes())
    config=root/'config.toml'
    if config.exists():
        backup=destination/'config.before-trader-dev.toml'
        if not backup.exists():backup.write_bytes(config.read_bytes());os.chmod(backup,0o600)
    process=subprocess.run(['codex','mcp','add','trader-dev','--','node',str(bridge)],capture_output=True,text=True)
    if process.returncode:raise RuntimeError('Codex nie zapisał globalnego wpisu MCP. Sprawdź uprawnienia do ~/.codex.')
    print('Zapisano globalny MCP trader-dev dla tego użytkownika Codexa. Klucz pozostał poza repozytorium.')
    print('Nowe sesje Codexa odczytają konfigurację po ponownym uruchomieniu. Rejestracja nie potwierdza połączenia z usługą.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stdin-key',action='store_true');args=parser.parse_args()
    try:configure(sys.stdin.readline().strip() if args.stdin_key else os.environ.get('TRADER_DEV_API_KEY') or getpass.getpass('Klucz API trader.dev (ukryty): '))
    except (OSError,ValueError,RuntimeError):
        print('Konfiguracja nie powiodła się. Wymagane są działające Codex/Node/npx i zapis do katalogu ~/.codex.',file=sys.stderr);sys.exit(1)
