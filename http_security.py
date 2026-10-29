"""Local-browser trust boundary. A session token is CSRF protection, not OS login."""
from collections import deque
import hmac
import ipaddress
import json
import secrets
import threading
import time
import urllib.parse

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; img-src 'self' data:; font-src 'self'; object-src 'none'; "
       "base-uri 'none'; frame-ancestors 'none'; frame-src 'none'; form-action 'self'; worker-src 'none'")
HEADERS = {
    'Content-Security-Policy': CSP,
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
}
HEAVY = {'/api/analyze', '/api/import', '/api/bot/backtest', '/api/strategies/test',
         '/api/strategies/validate', '/api/strategies/source', '/api/mcp/research', '/api/coingecko/overview'}
_LOCK = threading.Lock()


class State:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.requests = deque()
        self.heavy = threading.BoundedSemaphore(2)

    def admit(self):
        now = time.monotonic()
        with self.lock:
            while self.requests and self.requests[0] <= now - 60:
                self.requests.popleft()
            if len(self.requests) >= 600 or sum(t > now - 10 for t in self.requests) >= 160:
                return False
            self.requests.append(now)
        return True


def state(server):
    with _LOCK:
        if not hasattr(server, 'browser_security'):
            server.browser_security = State()
        return server.browser_security


def check(handler, write=False):
    """Reject foreign pages before reading a body or touching trading state."""
    def deny(message, status=403):
        handler.send_json({'error': message}, status)
        return False
    try:
        if not ipaddress.ip_address(handler.client_address[0]).is_loopback:
            return deny('Dozwolone jest wyłącznie połączenie lokalne.')
        hosts = handler.headers.get_all('Host', [])
        if len(hosts) != 1:
            return deny('Wymagany pojedynczy lokalny nagłówek Host.')
        host = hosts[0]
        port = handler.server.server_port
        valid = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if port == 80:
            valid.update(('127.0.0.1', 'localhost'))
        if host not in valid:
            return deny('Niedozwolony adres lub port serwera lokalnego.')
        if len(handler.path) > 4096 or not handler.path.startswith('/') or handler.path.startswith('//'):
            return deny('Nieprawidłowy adres żądania.', 400)
        urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query, max_num_fields=40)
        expected = 'http://' + host
        for name in ('Origin', 'Referer', 'Sec-Fetch-Site', 'X-Inwestapp-Token', 'Content-Type'):
            if len(handler.headers.get_all(name, [])) > 1:
                return deny('Powtórzony nagłówek żądania.', 400)
        origin = handler.headers.get('Origin')
        if origin is not None and origin != expected:
            return deny('Niedozwolone źródło żądania.')
        referer = handler.headers.get('Referer')
        if referer:
            parsed = urllib.parse.urlsplit(referer)
            if parsed.scheme + '://' + parsed.netloc != expected:
                return deny('Żądanie pochodzi spoza tej aplikacji.')
        site = handler.headers.get('Sec-Fetch-Site')
        if site and site not in ('same-origin', 'none'):
            return deny('Zablokowano żądanie z innej strony lub portu.')
        if handler.headers.get('Transfer-Encoding') is not None:
            return deny('Niedozwolone kodowanie żądania.', 400)
        lengths = handler.headers.get_all('Content-Length', [])
        if len(lengths) > 1 or (not write and lengths and lengths[0] != '0'):
            return deny('Nieprawidłowa długość żądania.', 400)
        if write:
            token = handler.headers.get('X-Inwestapp-Token', '')
            if not hmac.compare_digest(token.encode('utf-8'), state(handler.server).token.encode('ascii')):
                return deny('Brak lub nieaktualny token aplikacji. Odśwież stronę przez Ctrl+F5.')
        if not state(handler.server).admit():
            return deny('Zbyt wiele żądań. Poczekaj chwilę i spróbuj ponownie.', 429)
        return True
    except (ValueError, UnicodeError):
        return deny('Nieprawidłowe nagłówki lub parametry żądania.', 400)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Powtórzone pole JSON.')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('JSON nie może zawierać NaN ani Infinity.')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
