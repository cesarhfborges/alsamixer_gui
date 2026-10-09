"""Controles visuais do mixer, no formato de colunas (faixas) como no alsamixer.

Todos os controles seguem o mesmo contrato (`ControlView`):
  - construtor idêntico: (master, spec, actions, options)
  - grade comum de 4 linhas: cabeçalho, corpo (expande), rodapé e nome
  - `_build_widgets()` preenche cabeçalho/corpo/rodapé
  - `_render(control)` reflete o estado do hardware na tela
  - `update_state(control)` atualiza, salvo se o usuário estiver interagindo

A criação é centralizada em `ControlViewFactory.create(...)`, que escolhe a
classe pelo `ControlKind`. Novos tipos são adicionados via `register(...)`
sem alterar a janela (Open/Closed).
"""
import time
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Type

import customtkinter as ctk

from src.core.interfaces import ControlActions
from src.core.layout import ControlKind, ControlSpec
from src.core.models import Direction, MixerControl
from .theme_manager import ThemeManager

DEBOUNCE_MS = 60
# Após uma interação do usuário, ignora atualizações vindas do polling por este período
INTERACTION_GRACE_S = 1.0

ROW_HEADER, ROW_BODY, ROW_FOOTER, ROW_NAME = range(4)


@dataclass
class ViewOptions:
    """Preferências compartilhadas por todos os controles (alteradas pela tela de Configurações)."""
    wheel_step: int = 3


class ControlView(ctk.CTkFrame, metaclass=ABCMeta):
    """Base de todos os controles: uma coluna com cabeçalho, corpo, rodapé e nome."""

    WIDTH = 96

    def __init__(self, master, spec: ControlSpec, actions: ControlActions, options: ViewOptions):
        # Cor explícita (par claro/escuro): "transparent" não acompanha a troca de tema
        super().__init__(master, fg_color=ThemeManager.color("CTkFrame", "top_fg_color"), corner_radius=8)
        self.spec = spec
        self.actions = actions
        self.options = options
        self._last_interaction = 0.0
        self._stale = False  # widgets alterados pelo usuário desde o último render

        self.grid_columnconfigure(0, minsize=self.WIDTH, weight=1)
        self.grid_rowconfigure(ROW_HEADER, minsize=30)
        self.grid_rowconfigure(ROW_BODY, weight=1)
        self.grid_rowconfigure(ROW_FOOTER, minsize=40)
        self.grid_rowconfigure(ROW_NAME, minsize=44)

        self.name_label = ctk.CTkLabel(self, text=self.control.display_name, wraplength=self.WIDTH - 8,
                                       font=ctk.CTkFont(size=12, weight="bold"))
        self.name_label.grid(row=ROW_NAME, column=0, padx=4, pady=(0, 6), sticky="n")

        self._build_widgets()
        self.render(spec.control)

    # --- contrato --------------------------------------------------------
    @abstractmethod
    def _build_widgets(self) -> None:
        """Cria os widgets específicos do controle nas linhas cabeçalho/corpo/rodapé."""

    @abstractmethod
    def _render(self, control: MixerControl) -> None:
        """Aplica o estado do controle aos widgets."""

    # --- comportamento comum ---------------------------------------------
    @property
    def control(self) -> MixerControl:
        return self.spec.control

    @property
    def direction(self) -> Optional[Direction]:
        return self.spec.direction

    def render(self, control: MixerControl) -> None:
        self.spec.control = control
        self._stale = False
        self._render(control)

    def update_state(self, control: MixerControl) -> None:
        """Atualiza a partir do polling; só redesenha se algo mudou."""
        if self.is_busy:
            return
        if self._stale or control != self.control:
            self.render(control)

    @property
    def is_busy(self) -> bool:
        return time.monotonic() - self._last_interaction < INTERACTION_GRACE_S

    def _touch(self) -> None:
        self._last_interaction = time.monotonic()
        self._stale = True

    def reset_interaction(self) -> None:
        self._last_interaction = 0.0


class VolumeControlView(ControlView):
    """Faixa de canal: porcentagem, slider vertical e checkbox de mudo (quando suportados).

    Controles só com chave (ex.: S/PDIF) exibem ON/OFF no lugar do slider.
    """

    def _build_widgets(self) -> None:
        self._pending_job: Optional[str] = None
        self.slider: Optional[ctk.CTkSlider] = None
        self.state_label: Optional[ctk.CTkLabel] = None
        self.mute_checkbox: Optional[ctk.CTkCheckBox] = None

        self.value_label = ctk.CTkLabel(self, text="")
        self.value_label.grid(row=ROW_HEADER, column=0, pady=(6, 0))

        if self.control.has_volume(self.direction):
            self.slider = ctk.CTkSlider(self, orientation="vertical", from_=0, to=100, number_of_steps=100,
                                        command=self._on_slider_move)
            self.slider.grid(row=ROW_BODY, column=0, pady=6, sticky="ns")
            self.slider.bind("<Button-4>", lambda e: self._on_wheel(+self.options.wheel_step))
            self.slider.bind("<Button-5>", lambda e: self._on_wheel(-self.options.wheel_step))
        else:
            self.state_label = ctk.CTkLabel(self, font=ctk.CTkFont(size=16, weight="bold"))
            self.state_label.grid(row=ROW_BODY, column=0)

        if self.control.has_switch(self.direction):
            self.mute_checkbox = ctk.CTkCheckBox(self, text="Mudo", width=70, command=self._on_mute_toggle)
            self.mute_checkbox.grid(row=ROW_FOOTER, column=0)

    def _render(self, control: MixerControl) -> None:
        volume = control.volume(self.direction)
        if self.slider is not None and volume is not None:
            self.slider.set(volume)
            self.value_label.configure(text=f"{volume}%")
        if self.mute_checkbox is not None:
            self.mute_checkbox.set(control.is_muted(self.direction))
        self._refresh_muted_look()

    @property
    def is_busy(self) -> bool:
        return super().is_busy or self._pending_job is not None

    @property
    def _is_muted_on_screen(self) -> bool:
        return self.mute_checkbox is not None and bool(self.mute_checkbox.get())

    def _refresh_muted_look(self) -> None:
        muted = self._is_muted_on_screen
        self.value_label.configure(text_color="gray50" if muted else ThemeManager.color("CTkLabel", "text_color"))
        if self.state_label is not None:
            self.state_label.configure(text="OFF" if muted else "ON",
                                       text_color="gray50" if muted else ThemeManager.color("CTkButton", "fg_color"))

    def _on_slider_move(self, value: float) -> None:
        self._touch()
        self.value_label.configure(text=f"{int(value)}%")
        if self._pending_job is not None:
            self.after_cancel(self._pending_job)
        self._pending_job = self.after(DEBOUNCE_MS, self._flush_volume)

    def _on_wheel(self, delta: int) -> str:
        value = max(0, min(100, int(self.slider.get()) + delta))
        self.slider.set(value)
        self._on_slider_move(value)
        return "break"  # não repassa a rolagem para o painel

    def _flush_volume(self) -> None:
        self._pending_job = None
        self._touch()
        self.actions.set_volume(self.control, self.direction, int(self.slider.get()))

    def _on_mute_toggle(self) -> None:
        self._touch()
        self._refresh_muted_look()
        self.actions.set_switch(self.control, self.direction, not self._is_muted_on_screen)

    def destroy(self) -> None:
        if self._pending_job is not None:
            self.after_cancel(self._pending_job)
            self._pending_job = None
        super().destroy()


class EnumControlView(ControlView):
    """Seleção de opção para enumerações (ex.: Input Source, Auto-Mute Mode)."""

    WIDTH = 150

    def _build_widgets(self) -> None:
        self.menu = ctk.CTkOptionMenu(self, values=self.control.enum_items or [""], width=self.WIDTH - 12,
                                      height=36, font=ctk.CTkFont(size=14),
                                      dropdown_font=ctk.CTkFont(size=14),
                                      dynamic_resizing=False, command=self._on_select)
        self.menu.grid(row=ROW_BODY, column=0, padx=6)

    def _render(self, control: MixerControl) -> None:
        if control.enum_value is not None:
            self.menu.set(control.enum_value)

    def _on_select(self, value: str) -> None:
        self._touch()
        self.actions.set_enum(self.control, value)


class ControlViewFactory:
    """Ponto único de criação dos controles visuais."""

    def __init__(self, registry: Optional[Dict[ControlKind, Type[ControlView]]] = None,
                 options: Optional[ViewOptions] = None):
        self._registry: Dict[ControlKind, Type[ControlView]] = dict(registry or {})
        self.options = options or ViewOptions()

    def register(self, kind: ControlKind, view_class: Type[ControlView]) -> None:
        self._registry[kind] = view_class

    def create(self, master, spec: ControlSpec, actions: ControlActions) -> ControlView:
        try:
            view_class = self._registry[spec.kind]
        except KeyError:
            raise ValueError(f"Nenhuma visualização registrada para {spec.kind!r}") from None
        return view_class(master, spec, actions, self.options)

    @classmethod
    def default(cls) -> "ControlViewFactory":
        return cls({
            ControlKind.VOLUME: VolumeControlView,
            ControlKind.ENUM: EnumControlView,
        })
