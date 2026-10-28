"""Restart a crashed local server; intentional Ctrl+C exits the supervisor."""
import argparse
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--open-browser',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];delay=1;first=True
    while True:
        started=time.monotonic();command=[sys.executable,str(root/'server.py'),'--port',str(args.port)]
        if first and args.open_browser:command.append('--open-browser')
        child=subprocess.Popen(command,cwd=root);first=False
        try:code=child.wait()
        except KeyboardInterrupt:
            try:child.wait(timeout=50)
            except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=10)
            return 0
        if code in (0,2,3,4):return code
        if time.monotonic()-started>300:delay=1
        print('Serwer zakonczyl prace z bledem; ponowne uruchomienie za '+str(delay)+' s.',flush=True)
        time.sleep(delay);delay=min(60,delay*2)


if __name__=='__main__':raise SystemExit(main())
