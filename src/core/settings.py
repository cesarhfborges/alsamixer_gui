"""Configurações e estado do aplicativo, persistidos em JSON.

Arquivo: $XDG_CONFIG_HOME/alsamixer-gui/settings.json (padrão ~/.config/alsamixer-gui/settings.json)

- Preferências: editadas pelo usuário na tela de Configurações.
- Estado: gravado automaticamente (última placa/aba, tamanho da janela).
"""
import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields, replace
from typing import List, Optional

from .layout import Section
from .models import SoundCard

SETTINGS_VERSION = 1
LAST_USED = ""  # valor de default_card/default_tab que significa "última utilizada"

THEMES = ("System", "Dark", "Light")
UI_SCALES = (0.9, 1.0, 1.1, 1.25, 1.5)
POLL_INTERVALS_MS = (0, 1000, 2000, 5000)
WHEEL_STEPS = (1, 3, 5, 10)


@dataclass
class AppSettings:
    # --- Preferências ---------------------------------------------------
    theme: str = "System"
    ui_scale: float = 1.0
    default_card: str = LAST_USED   # id da placa (ex.: "PCH") ou LAST_USED
    default_tab: str = LAST_USED    # nome da aba (Section.value) ou LAST_USED
    poll_interval_ms: int = 2000    # 0 = atualização automática desligada
    wheel_step: int = 3             # % por passo da roda do mouse sobre o slider
    remember_window: bool = True    # restaura tamanho/posição da janela

    # --- Estado (automático) --------------------------------------------
    last_card: Optional[str] = None
    last_tab: Optional[str] = None
    window_geometry: Optional[str] = None

    def validated(self) -> "AppSettings":
        """Substitui valores inválidos (arquivo editado à mão, versão antiga) pelos padrões."""
        default = AppSettings()
        tabs = {s.value for s in Section}
        checks = {
            "theme": self.theme in THEMES,
            "ui_scale": self.ui_scale in UI_SCALES,
            "default_card": isinstance(self.default_card, str),
            "default_tab": self.default_tab == LAST_USED or self.default_tab in tabs,
            "poll_interval_ms": self.poll_interval_ms in POLL_INTERVALS_MS,
            "wheel_step": self.wheel_step in WHEEL_STEPS,
            "remember_window": isinstance(self.remember_window, bool),
            "last_card": self.last_card is None or isinstance(self.last_card, str),
            "last_tab": self.last_tab is None or self.last_tab in tabs,
            "window_geometry": self.window_geometry is None or isinstance(self.window_geometry, str),
        }
        invalid = {name: getattr(default, name) for name, ok in checks.items() if not ok}
        return replace(self, **invalid)

    def to_dict(self) -> dict:
        return {"version": SETTINGS_VERSION, "settings": asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        values = data.get("settings", {}) if isinstance(data, dict) else {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in known}).validated()

    # --- Regras derivadas -----------------------------------------------
    def initial_card(self, cards: List[SoundCard]) -> Optional[SoundCard]:
        """Placa exibida ao abrir: a padrão configurada, senão a última usada, senão a primeira."""
        if not cards:
            return None
        by_id = {c.id: c for c in cards}
        for card_id in (self.default_card, self.last_card):
            if card_id and card_id in by_id:
                return by_id[card_id]
        return cards[0]

    def initial_tab(self) -> str:
        return self.default_tab or self.last_tab or Section.OUTPUT.value


class SettingsRepository(ABC):
    @abstractmethod
    def load(self) -> AppSettings:
        pass

    @abstractmethod
    def save(self, settings: AppSettings) -> None:
        pass

    @property
    def location(self) -> str:
        return ""


class InMemorySettingsRepository(SettingsRepository):
    """Usado em testes e quando não se deseja persistir nada."""

    def __init__(self, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.saves = 0

    def load(self) -> AppSettings:
        return replace(self.settings)

    def save(self, settings: AppSettings) -> None:
        self.settings = replace(settings)
        self.saves += 1


def default_settings_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "alsamixer-gui", "settings.json")


class JsonSettingsRepository(SettingsRepository):
    def __init__(self, path: Optional[str] = None):
        self.path = path or default_settings_path()

    @property
    def location(self) -> str:
        return self.path

    def load(self) -> AppSettings:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return AppSettings.from_dict(json.load(fh))
        except (OSError, ValueError, TypeError):
            # Arquivo ausente ou corrompido: usa os padrões (será regravado ao salvar)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        # Escrita atômica: grava em arquivo temporário e substitui
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".settings-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(settings.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
