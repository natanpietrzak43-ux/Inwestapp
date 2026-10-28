"""Fixed HTTPS egress for public data. Redirects cannot select another host."""
import ipaddress
import json
import urllib.parse
import urllib.request

HOSTS = frozenset({'www.okx.com', 'api.exchange.coinbase.com', 'query1.finance.yahoo.com',
                  'www.coindesk.com', 'cointelegraph.com', 'www.eia.gov', 'news.google.com',
                  'raw.githubusercontent.com'})


def validate(url, hosts=HOSTS):
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or parsed.fragment or '\\' in url or any(ord(c) < 33 for c in url)):
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise ValueError('Niedozwolony adres źródła danych. Wymagany zatwierdzony host HTTPS.') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def open_url(request, timeout=12):
    validate(request.full_url if isinstance(request, urllib.request.Request) else request)
    # Preserve TLS certificate checks; never install a process-wide URL opener.
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)


def read(request, limit=2_000_000, timeout=12):
    with open_url(request, timeout=timeout) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Odpowiedź źródła danych przekracza bezpieczny limit.')
    return raw


def read_json(request, limit=2_000_000, timeout=12):
    return json.loads(read(request, limit, timeout))


def validate_webhook(url):
    """A private operator setting may choose a public host, never a local target."""
    parsed = urllib.parse.urlsplit(url)
    validate(url, {parsed.hostname})
    host = parsed.hostname or ''
    if '.' not in host or host.endswith(('.local', '.localhost', '.internal')) or host == 'localhost':
        raise ValueError('Webhook wymaga publicznego adresu HTTPS.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError('Webhook nie może wskazywać adresu lokalnego ani prywatnego.')
