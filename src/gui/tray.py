"""Ícone na bandeja do sistema (system tray).

`TrayIcon` é o contrato usado pela janela; `PystrayTrayIcon` usa o pystray
(backend X11/XEmbed ou AppIndicator) e `NullTrayIcon` é usado quando não há
suporte — nesse caso fechar a janela encerra o app normalmente, para nunca
deixar o app escondido sem ícone para reabri-lo.
"""
import threading
from abc import ABC, abstractmethod
from typing import Callable, Optional

APP_ID = "alsamixer-gui"
APP_TITLE = "Alsamixer Control"


class TrayIcon(ABC):
    @property
    @abstractmethod
    def available(self) -> bool:
        """Há suporte a bandeja neste ambiente."""

    @property
    @abstractmethod
    def running(self) -> bool:
        """O ícone está visível na bandeja."""

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass


class NullTrayIcon(TrayIcon):
    def __init__(self, reason: str = ""):
        self.reason = reason

    @property
    def available(self) -> bool:
        return False

    @property
    def running(self) -> bool:
        return False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def create_icon_image(size: int = 64):
    """Desenha o ícone (alto-falante com ondas) com o Pillow."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = size / 64
    # Fundo quadrado e opaco: o painel reduz o ícone (ex.: 24 px) e cantos arredondados/transparentes
    # viram pixels soltos na bandeja XEmbed, que não tem transparência parcial
    draw.rectangle((0, 0, size, size), fill=(31, 106, 165, 255))
    white = (255, 255, 255, 255)
    draw.polygon([(12 * s, 25 * s), (21 * s, 25 * s), (32 * s, 14 * s), (32 * s, 50 * s),
                  (21 * s, 39 * s), (12 * s, 39 * s)], fill=white)
    for radius in (9, 17):
        box = (32 * s - radius * s, 32 * s - radius * s, 32 * s + radius * s, 32 * s + radius * s)
        draw.arc((box[0] + 6 * s, box[1], box[2] + 6 * s, box[3]), start=-50, end=50, fill=white, width=int(4 * s))
    return image


class PystrayTrayIcon(TrayIcon):
    """Ícone com menu: Mostrar/Ocultar (ação padrão do clique) e Sair.

    Os callbacks rodam na thread do pystray; `post` deve repassá-los à thread do Tk.
    """

    def __init__(self, pystray_module, on_toggle: Callable[[], None], on_quit: Callable[[], None],
                 post: Callable[[Callable[[], None]], None]):
        self._pystray = pystray_module
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._post = post
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return True

    @property
    def running(self) -> bool:
        return self._icon is not None

    def start(self) -> None:
        if self._icon is not None:
            return
        pystray = self._pystray
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar / Ocultar", lambda icon, item: self._post(self._on_toggle), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda icon, item: self._post(self._on_quit)),
        )
        self._icon = pystray.Icon(APP_ID, create_icon_image(), APP_TITLE, menu)
        self._thread = threading.Thread(target=self._icon.run, name="tray-icon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            pass
        self._icon = None
        self._thread = None


def create_tray_icon(on_toggle, on_quit, post) -> TrayIcon:
    try:
        import pystray  # escolhe o backend (appindicator, gtk ou xorg) na importação
        create_icon_image(16)
    except Exception as exc:  # pystray/Pillow ausentes ou sem backend gráfico
        return NullTrayIcon(reason=str(exc) or exc.__class__.__name__)
    return PystrayTrayIcon(pystray, on_toggle, on_quit, post)
