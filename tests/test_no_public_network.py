"""Los tests jamás contactan Mastodon u otra red externa aunque exista .env.

La barrera se instala en conftest.py antes de la colección y no sustituye
socket.socket: localhost / sockets UNIX de las fixtures siguen operativos.
"""
import socket
import unittest


class OfflineSocketTests(unittest.TestCase):
    def test_dns_externo_se_bloquea_antes_de_resolver(self):
        with self.assertRaisesRegex(RuntimeError, "RRSS_TEST_RED_EXTERNA_BLOQUEADA:dns"):
            socket.getaddrinfo("mastodon.social", 443)

    def test_ipv4_publica_no_se_conecta(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            with self.assertRaisesRegex(RuntimeError, "RRSS_TEST_RED_EXTERNA_BLOQUEADA:conexion"):
                client.connect(("203.0.113.17", 443))
            with self.assertRaisesRegex(RuntimeError, "RRSS_TEST_RED_EXTERNA_BLOQUEADA:conexion"):
                client.connect_ex(("198.51.100.21", 443))

    def test_udp_externo_tampoco_envia(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            with self.assertRaisesRegex(RuntimeError, "RRSS_TEST_RED_EXTERNA_BLOQUEADA:conexion"):
                sender.sendto(b"fixture", ("192.0.2.8", 53))

    def test_loopback_tcp_real_funciona_y_no_usa_internet(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(("127.0.0.1", listener.getsockname()[1]))
                with listener.accept()[0] as accepted:
                    client.sendall(b"test")
                    self.assertEqual(accepted.recv(4), b"test")

    def test_resolucion_loopback_permitida(self):
        result = socket.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
        self.assertTrue(result)
        result = socket.getaddrinfo("127.0.0.1", 80, type=socket.SOCK_STREAM)
        self.assertTrue(result)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets no disponibles")
    def test_socketpair_local_no_bloqueado(self):
        a, b = socket.socketpair()
        with a, b:
            a.sendall(b"ok")
            self.assertEqual(b.recv(2), b"ok")


if __name__ == "__main__":
    unittest.main()
