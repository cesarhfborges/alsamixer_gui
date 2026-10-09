import sys
from typing import Dict, List, Tuple

import customtkinter as ctk

from src.core.interfaces import ControlActions
from src.core.layout import ControlSpec
from src.core.models import MixerControl
from .control_widgets import ControlView, ControlViewFactory
from .theme_manager import ThemeManager

EMPTY_TEXT = "Nenhum controle disponível nesta categoria."


class ControlPanel(ctk.CTkScrollableFrame):
    """Faixas de controles lado a lado com rolagem horizontal. Igual para Saída, Entrada e Opções."""

    def __init__(self, master, factory: ControlViewFactory, actions: ControlActions):
        # Cor explícita (par claro/escuro): "transparent" não acompanha a troca de tema
        super().__init__(master, orientation="horizontal",
                         fg_color=ThemeManager.color("CTkFrame", "fg_color"))
        self.grid_rowconfigure(0, weight=1)
        self._factory = factory
        self._actions = actions
        self.views: Dict[Tuple[str, str, str], ControlView] = {}

    def populate(self, specs: List[ControlSpec]) -> None:
        self.clear()
        if not specs:
            ctk.CTkLabel(self, text=EMPTY_TEXT, text_color="gray50").grid(row=0, column=0, padx=20)
            return
        for column, spec in enumerate(specs):
            view = self._factory.create(self, spec, self._actions)
            view.grid(row=0, column=column, sticky="ns", padx=3, pady=4)
            self.views[spec.key] = view
        self._parent_canvas.xview_moveto(0)

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.views.clear()

    def update_states(self, controls_by_key: Dict[str, MixerControl]) -> None:
        for view in self.views.values():
            control = controls_by_key.get(view.control.key)
            if control is not None:
                view.update_state(control)

    def reset_interactions(self) -> None:
        for view in self.views.values():
            view.reset_interaction()

    def _mouse_wheel_all(self, event):
        """Roda do mouse rola na horizontal sem precisar de Shift (sobre um slider, ajusta o volume)."""
        if not self.winfo_ismapped() or not self._check_if_valid_scroll(event.widget):
            return
        if self._parent_canvas.xview() == (0.0, 1.0):
            return
        if sys.platform.startswith("linux"):
            step = -1 if event.num == 4 else 1
        else:
            step = -1 if event.delta > 0 else 1
        self._parent_canvas.xview_scroll(step * 3, "units")
