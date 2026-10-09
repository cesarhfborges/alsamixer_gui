import subprocess
import customtkinter as ctk


class ThemeManager:
    @staticmethod
    def detect_system_mode() -> str:
        """Detecta se o Linux Mint está usando Dark ou Light Mode."""
        try:
            resultado = subprocess.check_output(
                ["gsettings", "get", "org.freedesktop.appearance", "color-scheme"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
            if "prefer-dark" in resultado:
                return "Dark"
        except Exception:
            pass
        return "Light"

    @classmethod
    def apply_theme(cls, mode: str) -> None:
        if mode == "System":
            ctk.set_appearance_mode(cls.detect_system_mode())
        else:
            ctk.set_appearance_mode(mode)
