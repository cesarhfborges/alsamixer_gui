import queue
from typing import Callable


class UiDispatcher:
    """Executa na thread do Tk funções enviadas por outras threads (bandeja, socket).

    O Tkinter não é thread-safe: outras threads só enfileiram; o Tk consome via `after`.
    """

    INTERVAL_MS = 100

    def __init__(self, root):
        self._root = root
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._job = root.after(self.INTERVAL_MS, self._drain)

    def post(self, func: Callable[[], None]) -> None:
        self._queue.put(func)

    def _drain(self) -> None:
        while True:
            try:
                func = self._queue.get_nowait()
            except queue.Empty:
                break
            func()
        self._job = self._root.after(self.INTERVAL_MS, self._drain)

    def stop(self) -> None:
        if self._job is not None:
            self._root.after_cancel(self._job)
            self._job = None
