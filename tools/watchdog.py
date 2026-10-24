"""Independent periodic process: detect stale services even if server has died."""
import argparse
import json
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runtime_ops


def check():
    runtime_ops.heartbeat('independent-watchdog',{'status':'running'})
    state=runtime_ops.status()
    if not state['healthy']:runtime_ops.event('watchdog_stale','Niezależny watchdog wykrył brak aktualnych cykli serwera.')
    try:runtime_ops.notify_pending()
    except Exception:pass
    print(json.dumps({'healthy':state['healthy'],'heartbeats':state['heartbeats'],'notificationConfigured':state['notificationConfigured']}),flush=True)
    return 0 if state['healthy'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    if args.once:raise SystemExit(check())
    while True:
        check();time.sleep(30)
