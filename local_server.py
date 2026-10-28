"""Bind-based local port checks, with exclusive listeners on Windows."""
import errno
from http.server import ThreadingHTTPServer
import socket
import sys
import threading


def configure_listener(sock):
    if sys.platform == 'win32':
        # SO_REUSEADDR on Windows can let two servers share the same address.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


class LocalHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    allow_reuse_port = False

    def __init__(self, *args, **kwargs):
        self.clients = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address

    def process_request(self, request, client_address):
        if not self.clients.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.clients.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.clients.release()

    def server_bind(self):
        configure_listener(self.socket)
        super().server_bind()


def address_in_use(error):
    return error.errno == errno.EADDRINUSE or getattr(error, 'winerror', None) == 10048


def port_busy(port):
    """Test binding, not connecting: a dropped probe is not a busy port.

    This creates no worker and does not accept connections. The real server
    binds again and must handle a process taking the port in between.
    Other failures propagate so permission errors never masquerade as busy.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            configure_listener(listener)
            listener.bind(('127.0.0.1', port))
    except OSError as error:
        if address_in_use(error):
            return True
        raise
    return False


def report_bind_error(error, port):
    print(f'Nie mozna otworzyc portu {port}.', flush=True)
    print(f'Szczegoly systemowe: {error}', flush=True)
    if address_in_use(error):
        print('Inny proces zajal ten adres. Sprawdz w CMD:', flush=True)
        print(f'netstat -ano | findstr :{port}', flush=True)
    elif error.errno in (errno.EACCES, errno.EPERM) or getattr(error, 'winerror', None) == 10013:
        print('System odmowil dostepu. Port moze byc zarezerwowany lub blokowany przez zasady systemowe.', flush=True)
        print('Ten blad nie potwierdza, ze dziala starsza aplikacja.', flush=True)
        if sys.platform == 'win32':
            print('Aby wyswietlic rezerwacje portow, wpisz w CMD:', flush=True)
            print('netsh interface ipv4 show excludedportrange protocol=tcp', flush=True)
    print('Skopiuj caly komunikat bledu do dalszej diagnostyki.', flush=True)
