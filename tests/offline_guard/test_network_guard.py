"""Guard de red para pytest y Python hijo. NO es un sandbox del sistema."""
import ipaddress
import socket
import sys

_INSTALLED = False


def _is_local(host, *, resolve=False):
    if host is None:
        return resolve
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    host = host.strip().lower()
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_loopback or (resolve and address.is_unspecified)


def _audit(event, args):
    if event in ("socket.connect", "socket.sendto"):
        sock, target = args[:2]
        if getattr(sock, "family", None) == getattr(socket, "AF_UNIX", None):
            return
        if getattr(sock, "family", None) not in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("RRSS_TEST_RED_EXTERNA_BLOQUEADA:familia_socket")
        if not isinstance(target, tuple) or not target or not _is_local(target[0]):
            raise RuntimeError("RRSS_TEST_RED_EXTERNA_BLOQUEADA:conexion")
    elif event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
        host = args[0] if args else None
        if not _is_local(host, resolve=(event == "socket.getaddrinfo")):
            raise RuntimeError("RRSS_TEST_RED_EXTERNA_BLOQUEADA:dns")
    elif event == "socket.getnameinfo":
        target = args[0] if args else None
        if not isinstance(target, tuple) or not target or not _is_local(target[0]):
            raise RuntimeError("RRSS_TEST_RED_EXTERNA_BLOQUEADA:dns_inverso")


def install():
    global _INSTALLED
    if not _INSTALLED:
        sys.addaudithook(_audit)
        _INSTALLED = True
