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
WATCH_INTERVAL_MS = 50
_BUTTONS_MASK = (1 << 8) | (1 << 9) | (1 << 10)  # Button1/2/3Mask do X11


class OutsideClickWatcher:
    """Fecha um popup quando o usuário clica em qualquer lugar fora dele — inclusive fora do app.

    O grab_set() do Tk é local: cliques no desktop, no painel ou em outros programas não chegam
    ao app. Aqui o estado global dos botões do mouse é consultado no X11 (sem prender o mouse).
    Só "arma" depois que todos os botões foram soltos (o clique que abriu o popup não conta).
    """

    def __init__(self, popup: tkinter.Toplevel, on_outside_click: Callable[[], None]):
        self._popup = popup
        self._on_outside_click = on_outside_click
        self._armed = False
        self._job = None
        try:
            from Xlib import display
            self._display = display.Display()
            self._root = self._display.screen().root
        except Exception:
            self._display = self._root = None  # sem Xlib: resta o fechamento por perda de foco
        popup.bind("<FocusOut>", self._on_focus_out, add=True)
        self._schedule()

    def _schedule(self) -> None:
        if self._root is not None:
            self._job = self._popup.after(WATCH_INTERVAL_MS, self._check)

    def _check(self) -> None:
        self._job = None
        try:
            pointer = self._root.query_pointer()
        except Exception:
            return
        pressed = bool(pointer.mask & _BUTTONS_MASK)
        if not pressed:
            self._armed = True
        elif self._armed and not self._inside(pointer.root_x, pointer.root_y):
            self._on_outside_click()
            return
        self._schedule()

    def _inside(self, x: int, y: int) -> bool:
        p = self._popup
        return p.winfo_rootx() <= x < p.winfo_rootx() + p.winfo_width() and \
            p.winfo_rooty() <= y < p.winfo_rooty() + p.winfo_height()

    def _on_focus_out(self, event) -> None:
        # Outro programa recebeu o foco (clique em outra janela)
        if event.widget is self._popup and self._armed:
            self._popup.after(10, self._close_if_focus_elsewhere)

    def _close_if_focus_elsewhere(self) -> None:
        try:
            if self._popup.focus_get() is None:
                self._on_outside_click()
        except (tkinter.TclError, KeyError):
            self._on_outside_click()

    def stop(self) -> None:
        if self._job is not None:
            try:
                self._popup.after_cancel(self._job)
            except tkinter.TclError:
                pass
            self._job = None
        if self._display is not None:
            self._display.close()
            self._display = self._root = None


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
        self._watcher = OutsideClickWatcher(self, self.close)

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
        self._watcher.stop()
        try:
            self.grab_release()
        except tkinter.TclError:
            pass
        self.destroy()
