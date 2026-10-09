"""Tela de Configurações do aplicativo.

Os campos são declarativos (`SettingField`) e todos são criados pelo mesmo
método (`_add_field`): para uma nova configuração basta adicionar um campo em
`build_fields()` e o atributo correspondente em `AppSettings`.
"""
import tkinter
from dataclasses import dataclass, fields, replace
from typing import Any, Callable, Dict, List, Sequence, Tuple

import customtkinter as ctk

from src.core.layout import Section
from src.core.models import SoundCard
from src.core.settings import (LAST_USED, POLL_INTERVALS_MS, THEMES, UI_SCALES, WHEEL_STEPS,
                               AppSettings)
from .theme_manager import ThemeManager

Choices = Sequence[Tuple[str, Any]]  # (rótulo exibido, valor salvo)

THEME_LABELS = {"System": "Seguir o sistema", "Dark": "Escuro", "Light": "Claro"}
# Atributos de AppSettings que são estado automático (não aparecem na tela)
STATE_ATTRS = ("last_card", "last_tab", "window_geometry")


@dataclass(frozen=True)
class SettingField:
    attr: str          # atributo de AppSettings
    group: str
    label: str
    description: str
    choices: Choices


def build_fields(cards: List[SoundCard]) -> List[SettingField]:
    return [
        SettingField("theme", "Aparência", "Tema",
                     "Cores da interface. \"Seguir o sistema\" detecta o modo escuro do desktop.",
                     [(THEME_LABELS[t], t) for t in THEMES]),
        SettingField("ui_scale", "Aparência", "Escala da interface",
                     "Aumenta ou reduz textos, selects e controles.",
                     [(f"{int(s * 100)}%", s) for s in UI_SCALES]),
        SettingField("default_card", "Inicialização", "Placa de som padrão",
                     "Dispositivo exibido ao abrir o aplicativo.",
                     [("Última utilizada", LAST_USED)] + [(c.name, c.id) for c in cards]),
        SettingField("default_tab", "Inicialização", "Aba inicial",
                     "Aba selecionada ao abrir o aplicativo.",
                     [("Última utilizada", LAST_USED)] + [(s.value, s.value) for s in Section]),
        SettingField("remember_window", "Inicialização", "Lembrar tamanho da janela",
                     "Restaura o tamanho da janela da última sessão.",
                     [("Sim", True), ("Não", False)]),
        SettingField("poll_interval_ms", "Comportamento", "Atualização automática",
                     "Frequência de leitura do mixer para refletir mudanças externas (teclas de volume, outros apps).",
                     [("Desligada" if ms == 0 else f"A cada {ms // 1000} s", ms) for ms in POLL_INTERVALS_MS]),
        SettingField("wheel_step", "Comportamento", "Passo da roda do mouse",
                     "Quanto o volume muda a cada giro da roda sobre um slider.",
                     [(f"{step}%", step) for step in WHEEL_STEPS]),
    ]


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: AppSettings, cards: List[SoundCard],
                 on_save: Callable[[AppSettings], None], location: str = ""):
        super().__init__(master)
        self.title("Configurações")
        self.geometry("680x600")
        self.minsize(520, 420)
        self.transient(master)

        self._settings = settings
        self._on_save = on_save
        self._selectors: Dict[str, Tuple[ctk.CTkOptionMenu, Dict[str, Any]]] = {}
        self._label_font = ctk.CTkFont(size=14, weight="bold")
        self._select_font = ctk.CTkFont(size=14)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkScrollableFrame(self, fg_color=ThemeManager.color("CTkFrame", "fg_color"))
        self.body.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        self.body.grid_columnconfigure(0, weight=1)

        group = None
        for field in build_fields(cards):
            if field.group != group:
                group = field.group
                self._add_group_title(group)
            self._add_field(field)

        self._build_footer(location)
        self.after(100, self._make_modal)

    # --- construção --------------------------------------------------------
    def _next_row(self) -> int:
        return len(self.body.grid_slaves(column=0))

    def _add_group_title(self, title: str) -> None:
        ctk.CTkLabel(self.body, text=title, font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=ThemeManager.color("CTkButton", "fg_color")).grid(
            row=self._next_row(), column=0, columnspan=2, sticky="w", padx=8, pady=(14, 2))

    def _add_field(self, field: SettingField) -> None:
        """Cria uma linha de configuração: rótulo + descrição à esquerda, select à direita."""
        choices = list(field.choices)
        current = getattr(self._settings, field.attr)
        if current not in [value for _, value in choices]:
            # Ex.: placa padrão desconectada — mantém o valor salvo visível
            choices.append((f"{current} (indisponível)", current))
        label_to_value = {label: value for label, value in choices}

        row = ctk.CTkFrame(self.body, fg_color=ThemeManager.color("CTkFrame", "top_fg_color"), corner_radius=8)
        row.grid(row=self._next_row(), column=0, sticky="ew", padx=4, pady=3)
        row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(row, text=field.label, font=self._label_font, anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(row, text=field.description, text_color="gray55", anchor="w", justify="left",
                     wraplength=300).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        selector = ctk.CTkOptionMenu(row, values=list(label_to_value), width=230, height=38,
                                     font=self._select_font, dropdown_font=self._select_font,
                                     dynamic_resizing=False)
        selector.set(next(label for label, value in choices if value == current))
        selector.grid(row=0, column=1, rowspan=2, padx=12, pady=10)
        self._selectors[field.attr] = (selector, label_to_value)

    def _build_footer(self, location: str) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        footer.grid_columnconfigure(1, weight=1)
        if location:
            ctk.CTkLabel(footer, text=f"Arquivo: {location}", text_color="gray55", anchor="w").grid(
                row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 6))
        ctk.CTkButton(footer, text="Restaurar padrões", width=150, height=36, fg_color="transparent",
                      border_width=1, text_color=("gray10", "gray90"), command=self.restore_defaults).grid(
            row=1, column=0, sticky="w")
        ctk.CTkButton(footer, text="Cancelar", width=110, height=36, fg_color="gray45",
                      hover_color="gray35", command=self.destroy).grid(row=1, column=2, padx=6)
        ctk.CTkButton(footer, text="Salvar", width=110, height=36, command=self.save).grid(row=1, column=3)

    def _make_modal(self) -> None:
        try:
            self.grab_set()
            self.focus_set()
        except tkinter.TclError:
            pass  # janela ainda não visível; segue não-modal

    # --- ações -------------------------------------------------------------
    def selected_settings(self) -> AppSettings:
        """Preferências escolhidas na tela; o estado automático é preservado."""
        values = {attr: mapping[selector.get()] for attr, (selector, mapping) in self._selectors.items()}
        return replace(self._settings, **values)

    def restore_defaults(self) -> None:
        defaults = AppSettings()
        for attr, (selector, mapping) in self._selectors.items():
            default = getattr(defaults, attr)
            selector.set(next(label for label, value in mapping.items() if value == default))

    def save(self) -> None:
        settings = self.selected_settings()
        self.destroy()
        self._on_save(settings)


def preference_attrs() -> List[str]:
    """Atributos editáveis na tela (todos os de AppSettings, menos o estado automático)."""
    return [f.name for f in fields(AppSettings) if f.name not in STATE_ATTRS]
