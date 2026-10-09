import os
import subprocess
from typing import Optional, Sequence, Tuple, Union

import customtkinter as ctk

Color = Union[str, Tuple[str, str]]

# Esquemas consultados (o primeiro que responder vence)
_COLOR_SCHEME_KEYS = (
    ("org.gnome.desktop.interface", "color-scheme"),
    ("org.freedesktop.appearance", "color-scheme"),
)
_GTK_THEME_KEYS = (
    ("org.cinnamon.desktop.interface", "gtk-theme"),  # Linux Mint (Cinnamon)
    ("org.gnome.desktop.interface", "gtk-theme"),
    ("org.mate.interface", "gtk-theme"),
)


class ThemeManager:
    @staticmethod
    def _gsettings(schema: str, key: str) -> Optional[str]:
        try:
            output = subprocess.check_output(["gsettings", "get", schema, key],
                                             stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            return None
        return output.decode("utf-8").strip().strip("'\"")

    @staticmethod
    def mode_from_settings(color_schemes: Sequence[Optional[str]], gtk_themes: Sequence[Optional[str]]) -> Optional[str]:
        """Decide o modo a partir dos valores lidos; None se nada for conclusivo."""
        for scheme in color_schemes:
            if scheme == "prefer-dark":
                return "Dark"
            if scheme == "prefer-light":
                return "Light"
        # 'default' não é conclusivo: o Mint indica o modo escuro pelo nome do tema (ex.: Mint-L-Dark-Blue)
        for theme in gtk_themes:
            if theme:
                return "Dark" if "dark" in theme.lower() else "Light"
        return None

    @classmethod
    def detect_system_mode(cls) -> str:
        """Detecta se o desktop (Mint/Cinnamon, GNOME, MATE) está em modo escuro ou claro."""
        env_theme = os.environ.get("GTK_THEME")
        mode = cls.mode_from_settings(
            [cls._gsettings(*k) for k in _COLOR_SCHEME_KEYS],
            [env_theme] + [cls._gsettings(*k) for k in _GTK_THEME_KEYS],
        )
        if mode is None:
            try:
                import darkdetect
                mode = "Dark" if darkdetect.isDark() else "Light"
            except Exception:
                mode = "Light"
        return mode

    @classmethod
    def apply_theme(cls, mode: str) -> None:
        if mode == "System":
            ctk.set_appearance_mode(cls.detect_system_mode())
        else:
            ctk.set_appearance_mode(mode)

    @staticmethod
    def color(widget: str, key: str) -> Color:
        """Cor (clara, escura) do tema ativo do CustomTkinter — acompanha a troca de modo."""
        value = ctk.ThemeManager.theme[widget][key]
        return tuple(value) if isinstance(value, list) else value
