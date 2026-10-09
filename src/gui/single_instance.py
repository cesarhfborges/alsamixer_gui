"""Garante uma única instância do app.

Com a bandeja ativa, a janela pode estar escondida: abrir o app de novo (pelo
menu do sistema, por exemplo) deve mostrar a janela existente em vez de criar
uma segunda instância. Usa um socket Unix no namespace abstrato do Linux
(não deixa arquivo para trás se o app for encerrado à força).
"""
import os
import socket
import threading
from typing import Callable, Optional

SHOW_MESSAGE = b"show"
PING_MESSAGE = b"ping"  # só verifica se há instância, sem mostrar a janela


class SingleInstance:
    def __init__(self, name: str = "alsamixer-gui"):
        self.address = f"\0{name}-{os.getuid()}"
        self._server: Optional[socket.socket] = None
        self.on_message: Callable[[bytes], None] = lambda message: None

    def notify_running_instance(self, message: bytes = SHOW_MESSAGE) -> bool:
        """Envia `message` à instância existente. True se havia uma instância."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(1)
                client.connect(self.address)
                client.sendall(message)
            return True
        except OSError:
            return False

    def acquire(self, show_existing: bool = True) -> bool:
        """Torna esta a instância principal. False se outra já está em execução.

        Com `show_existing`, pede para a instância existente mostrar a janela.
        """
        if self.notify_running_instance(SHOW_MESSAGE if show_existing else PING_MESSAGE):
            return False
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(self.address)
        except OSError:
            server.close()
            return False
        server.listen(4)
        self._server = server
        threading.Thread(target=self._serve, name="single-instance", daemon=True).start()
        return True

    def _serve(self) -> None:
        while self._server is not None:
            try:
                connection, _ = self._server.accept()
            except OSError:
                break
            with connection:
                connection.settimeout(1)
                try:
                    message = connection.recv(64)
                except OSError:
                    continue
            if message:
                self.on_message(message)

    def release(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            try:
                server.shutdown(socket.SHUT_RDWR)  # desbloqueia o accept() da thread
            except OSError:
                pass
            server.close()
