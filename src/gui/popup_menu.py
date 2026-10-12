"""Menu popup estilizado (usado no clique direito do ícone da bandeja).

O backend X11 do pystray não suporta menus (HAS_MENU = False); este menu é
desenhado com widgets do CustomTkinter, no mesmo estilo da lista dos selects.
"""
import tkinter
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from .theme_manager import ThemeManager
from .window_placement import detect_monitors, monitor_at

MenuItem = Optional[Tuple[str, Callable[[], None]]]  # None = separador
ITEM_HEIGHT = 36
WIDTH = 210


class PopupMenu(tkinter.Toplevel):
    def __init__(self, master, items: List[MenuItem], x: int, y: int):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self._closed = False
        self.buttons: List[ctk.CTkButton] = []

        frame = ctk.CTkFrame(self, fg_color=ThemeManager.color("CTkFrame", "fg_color"), corner_radius=0,
                             border_width=1, border_color=ThemeManager.color("CTkFrame", "border_color"))
        frame.pack(fill="both", expand=True)
        font = ctk.CTkFont(size=14)
        for item in items:
            if item is None:
                ctk.CTkFrame(frame, height=1, fg_color=("gray70", "gray35")).pack(fill="x", padx=10, pady=4)
                continue
            label, action = item
            button = ctk.CTkButton(frame, text=label, anchor="w", height=ITEM_HEIGHT, width=WIDTH - 12,
                                   corner_radius=6, font=font, border_spacing=10,
                                   fg_color=ThemeManager.color("CTkFrame", "fg_color"),
                                   hover_color=("gray78", "gray28"),
                                   text_color=ThemeManager.color("CTkLabel", "text_color"),
                                   command=lambda a=action: self._run(a))
            button.pack(fill="x", padx=6, pady=(6 if not self.buttons else 1, 1))
            self.buttons.append(button)
        ctk.CTkFrame(frame, height=5, fg_color="transparent").pack()

        self._place(x, y)
        self.deiconify()
        self.lift()
        self.after(10, self._grab)
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<ButtonPress>", self._on_click, add=True)

    def _place(self, x: int, y: int) -> None:
        """Abre no ponteiro, sem sair do monitor (painel embaixo → menu abre para cima)."""
        self.update_idletasks()
        width, height = max(WIDTH, self.winfo_reqwidth()), self.winfo_reqheight()
        monitor = monitor_at(detect_monitors(), x, y)
        if monitor is not None:
            x = min(x, monitor.x + monitor.width - width)
            if y + height > monitor.y + monitor.height:
                y = max(monitor.y, y - height)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _grab(self) -> None:
        if self._closed:
            return
        try:
            self.grab_set()
            self.focus_force()
        except tkinter.TclError:
            pass

    def _on_click(self, event) -> None:
        inside = (self.winfo_rootx() <= event.x_root < self.winfo_rootx() + self.winfo_width()
                  and self.winfo_rooty() <= event.y_root < self.winfo_rooty() + self.winfo_height())
        if not inside:
            self.close()

    def _run(self, action: Callable[[], None]) -> None:
        self.close()
        action()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()
