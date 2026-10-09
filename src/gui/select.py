"""Select com lista suspensa própria.

O CTkOptionMenu usa um `tkinter.Menu` nativo como lista suspensa: no Linux ele é
pequeno, sem padding interno e não acompanha o tema. `Select` mantém a API do
CTkOptionMenu (values, command, set/get) e troca apenas a lista por um popup
desenhado com widgets do CustomTkinter.
"""
import tkinter
from typing import List, Optional

import customtkinter as ctk

from .theme_manager import ThemeManager
from .window_placement import detect_monitors, monitor_at

ITEM_HEIGHT = 38
MAX_VISIBLE_ITEMS = 8
POPUP_PADDING = 6


class Select(ctk.CTkOptionMenu):
    """CTkOptionMenu com tamanho confortável e lista suspensa estilizada."""

    def __init__(self, master, font_size: int = 14, **kwargs):
        kwargs.setdefault("height", 38)
        kwargs.setdefault("dynamic_resizing", False)
        kwargs.setdefault("font", ctk.CTkFont(size=font_size))
        super().__init__(master, **kwargs)
        self._font_size = font_size
        self.popup: Optional["DropdownPopup"] = None

    def _clicked(self, event=0):
        if self.popup is not None:
            self.close_popup()
        elif self._state != tkinter.DISABLED and self._values:
            self.open_popup()

    def open_popup(self) -> None:
        self.popup = DropdownPopup(self, list(self._values), self.get(), self._on_popup_select,
                                   on_close=self._on_popup_closed, font_size=self._font_size)

    def close_popup(self) -> None:
        if self.popup is not None:
            self.popup.close()

    def _on_popup_select(self, value: str) -> None:
        self._dropdown_callback(value)  # mesmo fluxo do CTkOptionMenu: atualiza texto e chama command

    def _on_popup_closed(self) -> None:
        self.popup = None

    def destroy(self):
        self.close_popup()
        super().destroy()


class DropdownPopup(tkinter.Toplevel):
    """Janela sem decoração exibida abaixo (ou acima) do select."""

    def __init__(self, select: Select, values: List[str], current: str, on_select, on_close, font_size: int = 14):
        super().__init__(select)
        self._select = select
        self._values = values
        self._on_select = on_select
        self._on_close = on_close
        self._closed = False
        self._previous_grab = self.grab_current()
        self._highlight = values.index(current) if current in values else 0
        self.buttons: List[ctk.CTkButton] = []

        self.withdraw()
        self.overrideredirect(True)
        border = ThemeManager.color("CTkFrame", "border_color")
        self.configure(bg=self._mode_color(border))

        frame_kwargs = dict(fg_color=ThemeManager.color("CTkFrame", "fg_color"), corner_radius=0)
        if len(values) > MAX_VISIBLE_ITEMS:
            self.list_frame = ctk.CTkScrollableFrame(self, height=ITEM_HEIGHT * MAX_VISIBLE_ITEMS, **frame_kwargs)
        else:
            self.list_frame = ctk.CTkFrame(self, **frame_kwargs)
        self.list_frame.pack(fill="both", expand=True, padx=1, pady=1)

        font = ctk.CTkFont(size=font_size)
        for index, value in enumerate(values):
            button = ctk.CTkButton(
                self.list_frame, text=value, anchor="w", height=ITEM_HEIGHT, corner_radius=6, font=font,
                border_spacing=10,  # padding interno do item
                command=lambda v=value: self.choose(v))
            button.pack(fill="x", padx=POPUP_PADDING, pady=(POPUP_PADDING if index == 0 else 1,
                                                             POPUP_PADDING if index == len(values) - 1 else 1))
            button.bind("<Enter>", lambda e, i=index: self._set_highlight(i), add=True)
            self.buttons.append(button)
        self._paint()

        self._place()
        self.deiconify()
        self.lift()
        self.after(10, self._grab)

        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Up>", lambda e: self._move(-1))
        self.bind("<Down>", lambda e: self._move(+1))
        self.bind("<Return>", lambda e: self.choose(self._values[self._highlight]))
        self.bind("<KP_Enter>", lambda e: self.choose(self._values[self._highlight]))
        self.bind("<ButtonPress>", self._on_click, add=True)

    # --- aparência ---------------------------------------------------------
    @staticmethod
    def _mode_color(color) -> str:
        if isinstance(color, (tuple, list)):
            return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
        return color

    def _paint(self) -> None:
        selected = self._select.get()
        accent = ThemeManager.color("CTkButton", "fg_color")
        hover = ThemeManager.color("CTkButton", "hover_color")
        text = ThemeManager.color("CTkLabel", "text_color")
        for index, (button, value) in enumerate(zip(self.buttons, self._values)):
            if value == selected:
                button.configure(fg_color=accent, hover_color=hover, text_color=("white", "white"))
            elif index == self._highlight:
                button.configure(fg_color=("gray78", "gray28"), hover_color=("gray78", "gray28"), text_color=text)
            else:
                button.configure(fg_color=ThemeManager.color("CTkFrame", "fg_color"),
                                 hover_color=("gray78", "gray28"), text_color=text)

    def _set_highlight(self, index: int) -> None:
        self._highlight = index
        self._paint()

    def _move(self, delta: int) -> None:
        self._set_highlight((self._highlight + delta) % len(self._values))

    # --- posição -----------------------------------------------------------
    def _place(self) -> None:
        self.update_idletasks()
        width = max(self._select.winfo_width(), self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = self._select.winfo_rootx()
        below = self._select.winfo_rooty() + self._select.winfo_height() + 2
        y = below
        monitor = monitor_at(detect_monitors(), x + 1, below)
        if monitor is not None:
            if below + height > monitor.y + monitor.height:  # sem espaço abaixo: abre para cima
                y = max(monitor.y, self._select.winfo_rooty() - height - 2)
            x = min(x, monitor.x + monitor.width - width)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # --- foco/fechamento ---------------------------------------------------
    def _grab(self) -> None:
        if self._closed:
            return
        try:
            self.grab_set()
            self.focus_force()
        except tkinter.TclError:
            pass

    def _on_click(self, event) -> None:
        """Com o grab ativo, cliques fora do popup chegam aqui: fecham a lista."""
        inside = (self.winfo_rootx() <= event.x_root < self.winfo_rootx() + self.winfo_width()
                  and self.winfo_rooty() <= event.y_root < self.winfo_rooty() + self.winfo_height())
        if not inside:
            self.close()

    def choose(self, value: str) -> None:
        self.close()
        self._on_select(value)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()
        # Devolve o grab a um diálogo modal (ex.: Configurações), se havia um
        if self._previous_grab is not None:
            try:
                self._previous_grab.grab_set()
            except tkinter.TclError:
                pass
        self._on_close()
