"""Entry point: serve the dashboard on a private unix socket (and optionally a TCP address)."""
import os
import socketserver
import threading

from .config import RUN, SOCK, TCP
from .routes import Handler


class UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


class TCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    os.chmod(RUN, 0o700)
    if SOCK.exists():
        SOCK.unlink()
    if TCP:
        host, _, port = TCP.rpartition(":")
        tcp = TCPServer((host or "127.0.0.1", int(port)), Handler)
        threading.Thread(target=tcp.serve_forever, daemon=True).start()
    with UnixServer(str(SOCK), Handler) as server:
        os.chmod(SOCK, 0o600)
        server.serve_forever()


if __name__ == "__main__":
    main()
