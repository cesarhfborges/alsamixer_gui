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
    """Ícone da bandeja (src/assets/audio-wave.svg) com fundo transparente."""
    from .icon import render_icon
    return render_icon(size, bg=None, padding=0.04)


def compose_on_panel(icon, size, panel_rgb):
    """A bandeja XEmbed (pystray X11) só aceita RGB: desenha o ícone sobre a cor do painel.

    Cor do desenho com contraste: branco em painel escuro, cinza escuro em painel claro.
    """
    from PIL import Image
    r, g, b = panel_rgb
    fg = (245, 245, 245) if (0.299 * r + 0.587 * g + 0.114 * b) < 140 else (45, 45, 45)
    mask = icon.resize(size, Image.LANCZOS).getchannel("A")
    image = Image.new("RGB", size, panel_rgb)
    image.paste(fg, (0, 0, *size), mask)
    return image


def sample_panel_color(display, window, default=(32, 32, 32)):
    """Cor do fundo da bandeja logo à esquerda do ícone (lida da tela)."""
    try:
        from Xlib import X
        root = display.screen().root
        pos = window.translate_coords(root, 0, 0)
        x, y = -pos.x, -pos.y
        height = window.get_geometry().height
        data = root.get_image(max(0, x - 3), y + height // 2, 1, 1, X.ZPixmap, 0xFFFFFFFF).data
        return data[2], data[1], data[0]
    except Exception:
        return default


class PystrayTrayIcon(TrayIcon):
    """Ícone com menu: Mostrar/Ocultar (ação padrão do clique), Configurações e Encerrar.

    Os callbacks rodam na thread do pystray; `post` deve repassá-los à thread do Tk.
    """

    def __init__(self, pystray_module, on_toggle: Callable[[], None], on_quit: Callable[[], None],
                 post: Callable[[Callable[[], None]], None],
                 on_settings: Callable[[], None] = lambda: None,
                 on_menu: Callable[[int, int], None] = lambda x, y: None):
        self._pystray = pystray_module
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._on_settings = on_settings
        self._on_menu = on_menu
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
            pystray.MenuItem("Configurações", lambda icon, item: self._post(self._on_settings)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Encerrar", lambda icon, item: self._post(self._on_quit)),
        )
        self._icon = self._icon_class()(APP_ID, create_icon_image(), APP_TITLE, menu)
        self._thread = threading.Thread(target=self._icon.run, name="tray-icon", daemon=True)
        self._thread.start()

    def _icon_class(self):
        """Backend sem menu (X11/XEmbed): o clique direito abre o menu desenhado pelo app."""
        base = self._pystray.Icon
        if getattr(base, "HAS_MENU", True):
            return base
        post, on_menu = self._post, self._on_menu

        class IconWithMenu(base):
            def _assert_icon_data(self, width, height):
                # Original: cola o RGBA sobre fundo preto. Aqui: sobre a cor real do painel.
                if self._icon_data and self._icon_data.size == (width, height):
                    return
                panel = sample_panel_color(self._display, self._window)
                self._icon_data = compose_on_panel(self._icon, (width, height), panel)
                self._icon_data.tostring = self._icon_data.tobytes

            def _on_button_press(self, event):
                if event.detail == 3:  # botão direito
                    x, y = event.root_x, event.root_y
                    post(lambda: on_menu(x, y))
                else:
                    super()._on_button_press(event)

        return IconWithMenu

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            pass
        self._icon = None
        self._thread = None


def create_tray_icon(on_toggle, on_quit, post, on_settings=lambda: None, on_menu=lambda x, y: None) -> TrayIcon:
    try:
        import pystray  # escolhe o backend (appindicator, gtk ou xorg) na importação
        create_icon_image(16)
    except Exception as exc:  # pystray/Pillow ausentes ou sem backend gráfico
        return NullTrayIcon(reason=str(exc) or exc.__class__.__name__)
    return PystrayTrayIcon(pystray, on_toggle, on_quit, post, on_settings, on_menu)
