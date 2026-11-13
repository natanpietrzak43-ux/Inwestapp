"""Public OKX maintenance notice check, separate from strategy/history signals."""
import threading
import time
from datetime import datetime,timezone
import okx_data

LOCK=threading.Lock()
CACHE=None


def snapshot():
    global CACHE
    with LOCK:
        now=time.time()
        if CACHE and 0<=now-CACHE['timestamp']<60:return dict(CACHE)
        try:
            rows=okx_data.request('/api/v5/system/status',{'state':'ongoing'})
            if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):raise ValueError()
            result={'verified':True,'entryAllowed':not rows,'ongoingNotices':len(rows),
                    'reason':'Brak zgłoszonej trwającej przerwy w publicznym statusie OKX.' if not rows else 'OKX zgłasza trwającą przerwę. Nowe wejścia Demo są wstrzymane.'}
        except (OSError,ValueError,TypeError,KeyError):
            result={'verified':False,'entryAllowed':False,'ongoingNotices':None,
                    'reason':'Nie potwierdzono publicznego statusu OKX. Nowe wejścia Demo czekają na kolejny poprawny odczyt.'}
        CACHE={**result,'timestamp':now,'checkedAt':datetime.fromtimestamp(now,timezone.utc).isoformat(),
               'notice':'Brak komunikatu nie gwarantuje dostępności giełdy. Kontrola dotyczy nowych wejść Demo; nie wyłącza ochrony i zamykania pozycji.'}
        return dict(CACHE)
