"""Inicialização com o sistema via XDG Autostart (Cinnamon, GNOME, MATE, XFCE, KDE).

Cria/remove ~/.config/autostart/alsamixer-gui.desktop. O comando usa caminhos
absolutos do Python do venv e do main.py; se o projeto mudar de pasta, `sync()`
regrava o arquivo na próxima vez que o app abrir.
"""
import os
import sys
from typing import List, Optional

from .storage import atomic_write_text

DESKTOP_FILE = "alsamixer-gui.desktop"
AUTOSTART_DELAY_S = 5
PROJECT_MAIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
INSTALLED_BIN = "/usr/bin/alsamixer-gui"  # link criado pelo pacote .deb
MINIMIZED_FLAG = "--minimized"  # o app abre só com o ícone na bandeja
DISABLED_LINE = "X-GNOME-Autostart-enabled=false"  # gravado pelo "Aplicativos de inicialização" do Mint


def default_autostart_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "autostart", DESKTOP_FILE)


def default_command() -> List[str]:
    if getattr(sys, "frozen", False):  # binário do PyInstaller (.deb)
        binary = INSTALLED_BIN if os.path.exists(INSTALLED_BIN) else sys.executable
        return [binary, MINIMIZED_FLAG]
    # sys.executable sem resolver links: mantém o Python do .venv (e suas dependências)
    return [sys.executable, PROJECT_MAIN, MINIMIZED_FLAG]


def _quote(arg: str) -> str:
    """Aspas conforme a especificação Desktop Entry (Exec)."""
    if not any(ch in arg for ch in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return f'"{escaped}"'


def build_desktop_entry(command: List[str]) -> str:
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Alsamixer Control",
        "Comment=Restaura o estado do mixer (ex.: S/PDIF) e fica na bandeja do sistema",
        f"Exec={' '.join(_quote(a) for a in command)}",
        f"TryExec={_quote(command[0])}",  # app desinstalado: o Cinnamon ignora a entrada
        "Icon=alsamixer-gui",
        "Terminal=false",
        "Categories=AudioVideo;Audio;Mixer;",
        "X-GNOME-Autostart-enabled=true",
        f"X-GNOME-Autostart-Delay={AUTOSTART_DELAY_S}",
        "",
    ])


class AutostartManager:
    def __init__(self, path: Optional[str] = None, command: Optional[List[str]] = None):
        self.path = path or default_autostart_path()
        self.command = command or default_command()

    @property
    def expected_content(self) -> str:
        return build_desktop_entry(self.command)

    def is_enabled(self) -> bool:
        return os.path.exists(self.path)

    def disabled_by_user(self) -> bool:
        """Entrada desligada pelo "Aplicativos de inicialização" do Mint (não deve ser regravada)."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                return DISABLED_LINE in fh.read()
        except OSError:
            return False

    def is_current(self) -> bool:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return fh.read() == self.expected_content
        except OSError:
            return False

    def enable(self) -> None:
        atomic_write_text(self.path, self.expected_content)

    def disable(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)

    def sync(self, enabled: bool) -> None:
        """Deixa o arquivo de acordo com a configuração (e com o caminho atual do projeto)."""
        if enabled and self.disabled_by_user():
            return
        if enabled and not self.is_current():
            self.enable()
        elif not enabled:
            self.disable()
