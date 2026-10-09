import time
from dataclasses import replace
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from src.core.interfaces import AudioController, MixerError
from src.core.layout import Section, build_layout
from src.core.autostart import AutostartManager
from src.core.mixer_state import InMemoryMixerStateRepository, MixerStateStore, SwitchState
from src.core.models import Direction, MixerControl, SoundCard
from src.core.settings import AppSettings, InMemorySettingsRepository, SettingsRepository
from src.core.state_keeper import StateKeeper
from .actions import CardActions
from .control_panel import ControlPanel
from .control_widgets import ControlViewFactory
from .dispatcher import UiDispatcher
from .select import Select
from .settings_dialog import SettingsDialog
from .theme_manager import ThemeManager
from .tray import TrayIcon, create_tray_icon
from .window_placement import choose_position, detect_monitors, parse_geometry

NO_CARD = "(nenhuma)"
DEFAULT_SIZE = (960, 620)

TrayFactory = Callable[..., TrayIcon]

KEEP_STATE_INTERVAL_MS = 2000
# Sem "Manter estado", ainda vigia por um tempo após abrir: o WirePlumber pode iniciar depois do app
STARTUP_RESTORE_WINDOW_S = 60


class AlsamixerGUI(ctk.CTk):
    def __init__(self, audio_controller: AudioController,
                 settings_repository: Optional[SettingsRepository] = None,
                 view_factory: Optional[ControlViewFactory] = None,
                 tray_factory: TrayFactory = create_tray_icon,
                 mixer_state_store: Optional[MixerStateStore] = None,
                 autostart: Optional[AutostartManager] = None,
                 start_in_tray: bool = False):
        """`autostart=None` não mexe em ~/.config/autostart (testes); `start_in_tray` vem do --autostart."""
        super().__init__()
        self.audio_controller = audio_controller
        self.settings_repository = settings_repository or InMemorySettingsRepository()
        self.settings: AppSettings = self.settings_repository.load()
        self.view_factory = view_factory or ControlViewFactory.default()
        self.actions = CardActions(
            audio_controller,
            card_provider=lambda: self.current_card.index if self.current_card else None,
            on_error=self._on_action_error,
            on_success=lambda: self._set_status(""),
            on_switch=self._remember_switch,
        )
        # "is None" e não "or": um store vazio tem len() == 0 e seria considerado falso
        self.state_store = (mixer_state_store if mixer_state_store is not None
                            else MixerStateStore(InMemoryMixerStateRepository()))
        self.state_keeper = StateKeeper(audio_controller, self.state_store)
        self.autostart = autostart
        self.view_factory.options.is_saved = self._is_switch_saved
        self.dispatcher = UiDispatcher(self)
        self.tray = tray_factory(on_toggle=self.toggle_window, on_quit=self.quit_app, post=self.dispatcher.post)

        self.cards: List[SoundCard] = []
        self.current_card: Optional[SoundCard] = None
        self.settings_dialog: Optional[SettingsDialog] = None
        self._layout_signature: Tuple = ()
        self._poll_job: Optional[str] = None
        self._applied_scale: Optional[float] = None
        self._explicit_position = False
        self._frame_offset: Optional[Tuple[int, int]] = None  # (borda, barra de título) do gerenciador de janelas
        self._keeper_job: Optional[str] = None
        self._keeper_deadline = time.monotonic() + STARTUP_RESTORE_WINDOW_S

        self.title("Python Alsamixer GUI")
        self.minsize(560, 480)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._restore_geometry()
        self.apply_settings(self.settings)

        self._build_header()
        self._build_card_selector()
        self._build_tabs()
        self.status_label = ctk.CTkLabel(self, text="", anchor="w")
        self.status_label.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self.close)
        if self._explicit_position:
            self.after(300, self._measure_frame_offset)
        self.reload_cards(initial=True)
        self.tabview.set(self.settings.initial_tab())
        if self.settings.restore_state:
            self.enforce_saved_state()  # reaplica e atualiza a tela, avisando na barra de status

        if (self.settings.start_hidden or start_in_tray) and self.tray.running:
            self.withdraw()

    # ------------------------------------------------------------------ layout
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(header, text="Alsamixer Control", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.settings_button = ctk.CTkButton(header, text="⚙  Configurações", width=150, height=36,
                                             font=ctk.CTkFont(size=14), command=self.open_settings)
        self.settings_button.grid(row=0, column=1)

    def _build_card_selector(self) -> None:
        toolbar = ctk.CTkFrame(self)
        toolbar.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(toolbar, text="Placa de som:", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=(12, 8), pady=10)
        self.card_select = Select(toolbar, font_size=15, values=[NO_CARD], height=40,
                                  command=self._on_card_selected)
        self.card_select.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        self.reload_button = ctk.CTkButton(toolbar, text="Recarregar", width=120, height=40,
                                           font=ctk.CTkFont(size=15), command=self.reload_cards)
        self.reload_button.grid(row=0, column=2, padx=(6, 12), pady=10)

    def _build_tabs(self) -> None:
        self.tabview = ctk.CTkTabview(self, command=self._on_tab_changed,
                                      segmented_button_font=ctk.CTkFont(size=15, weight="bold"))
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=16, pady=6)
        self.panels: Dict[Section, ControlPanel] = {}
        for section in Section:
            tab = self.tabview.add(section.value)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            panel = ControlPanel(tab, self.view_factory, self.actions)
            panel.grid(row=0, column=0, sticky="nsew")
            self.panels[section] = panel

    # ------------------------------------------------------- posição da janela
    def _restore_geometry(self) -> None:
        """Tamanho/posição salvos; sem posição válida, centraliza no monitor principal.

        A posição é sempre explícita: se o gerenciador de janelas escolher, o Tk fica
        achando que a janela está em +0+0 e ela "pula" de monitor ao reaplicar a geometria.
        """
        saved = self.settings.window_geometry if self.settings.remember_window else None
        width, height, x, y = parse_geometry(saved)
        width, height = width or DEFAULT_SIZE[0], height or DEFAULT_SIZE[1]
        position = choose_position(width, height, (x, y), detect_monitors())
        if position is None:
            self.geometry(f"{width}x{height}")
        else:
            self.geometry(f"{width}x{height}+{position[0]}+{position[1]}")
            self._explicit_position = True

    def _measure_frame_offset(self) -> None:
        """Mede a decoração (borda/barra de título): área interna real - posição pedida ao Tk.

        Tenta de novo enquanto a janela não estiver visível (ex.: iniciada escondida na bandeja).
        """
        if self._frame_offset is not None:
            return
        _, _, x, y = parse_geometry(self.wm_geometry())
        if x is not None and self.winfo_ismapped():
            self._frame_offset = (self.winfo_rootx() - x, self.winfo_rooty() - y)
        else:
            self.after(300, self._measure_frame_offset)

    def frame_position(self) -> Optional[Tuple[int, int]]:
        """Posição real da janela (inclusive após o usuário arrastá-la)."""
        if self._frame_offset is None or not self.winfo_ismapped():
            return None
        return self.winfo_rootx() - self._frame_offset[0], self.winfo_rooty() - self._frame_offset[1]

    def _sync_position(self) -> None:
        """Informa ao Tk a posição real antes de qualquer reaplicação de geometria."""
        position = self.frame_position()
        if position is not None:
            self.geometry(f"+{position[0]}+{position[1]}")

    def _geometry_for_saving(self) -> str:
        size = self.geometry().split("+")[0].split("-")[0]
        position = self.frame_position()
        return f"{size}+{position[0]}+{position[1]}" if position else size

    # ------------------------------------------------- mostrar/esconder e sair
    @property
    def is_hidden(self) -> bool:
        return self.state() in ("withdrawn", "iconic")

    def show_window(self) -> None:
        _, _, x, y = parse_geometry(self.settings.window_geometry)
        if self.state() == "withdrawn" and x is not None:
            self.geometry(f"+{x}+{y}")  # volta exatamente onde estava
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_window(self) -> None:
        self._save_window_state()
        self.withdraw()

    def toggle_window(self) -> None:
        if self.is_hidden:
            self.show_window()
        else:
            self.hide_window()

    def close(self) -> None:
        """Botão fechar: com a bandeja ativa só esconde; senão encerra."""
        if self.tray.running:
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self) -> None:
        if not self.is_hidden:
            self._save_window_state()
        self.tray.stop()
        self.dispatcher.stop()
        self.destroy()

    def _save_window_state(self) -> None:
        if self.settings.remember_window:
            self._update_state(window_geometry=self._geometry_for_saving())

    # ----------------------------------------------------------- configurações
    def apply_settings(self, settings: AppSettings) -> None:
        """Aplica as preferências em tempo de execução."""
        self.settings = settings
        ThemeManager.apply_theme(settings.theme)
        if settings.ui_scale != self._applied_scale:
            # Mudar a escala reaplica a geometria da janela: sincroniza a posição antes
            self._sync_position()
            ctk.set_widget_scaling(settings.ui_scale)
            self._applied_scale = settings.ui_scale
        self.view_factory.options.wheel_step = settings.wheel_step
        self._restart_polling()
        self._restart_keeper()
        if self.autostart is not None:
            try:
                self.autostart.sync(settings.autostart)
            except OSError as exc:
                self.after_idle(lambda: self._set_status(f"Não foi possível configurar o início automático: {exc}",
                                                         error=True))
        if settings.tray_enabled and self.tray.available:
            self.tray.start()
        else:
            self.tray.stop()

    def open_settings(self) -> None:
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.focus()
            return
        self.settings_dialog = SettingsDialog(self, self.settings, self.cards, on_save=self._on_settings_saved,
                                              location=self.settings_repository.location,
                                              tray_available=self.tray.available,
                                              saved_states=len(self.state_store),
                                              on_clear_states=self.clear_saved_states)

    def _on_settings_saved(self, settings: AppSettings) -> None:
        if settings.autostart and self.tray.available and not settings.tray_enabled:
            # Iniciar com o sistema = ficar na bandeja (é assim que o estado continua sendo mantido)
            settings = replace(settings, tray_enabled=True)
        self.apply_settings(settings)
        self._save_settings()
        if settings.tray_enabled and not self.tray.available:
            self._set_status("Bandeja do sistema indisponível neste ambiente.", error=True)
        else:
            self._set_status("Configurações salvas.")

    def _update_state(self, **state) -> None:
        self.settings = replace(self.settings, **state)
        self._save_settings()

    def _save_settings(self) -> None:
        try:
            self.settings_repository.save(self.settings)
        except OSError as exc:
            self._set_status(f"Não foi possível salvar as configurações: {exc}", error=True)

    # ------------------------------------------------------------------ placas
    def reload_cards(self, initial: bool = False) -> None:
        try:
            self.cards = self.audio_controller.list_cards()
        except MixerError as exc:
            self.cards = []
            self._set_status(str(exc), error=True)
        else:
            if not self.cards:
                self._set_status("Nenhuma placa de som encontrada.", error=True)

        if not self.cards:
            self.card_select.configure(values=[NO_CARD])
            self.card_select.set(NO_CARD)
            self.current_card = None
            self._layout_signature = ()
            self._populate([])
            return

        self.card_select.configure(values=[c.label for c in self.cards])
        if initial or self.current_card is None:
            selected = self.settings.initial_card(self.cards)
        else:
            selected = next((c for c in self.cards if c.id == self.current_card.id), self.cards[0])
        self.select_card(selected)

    def _on_card_selected(self, label: str) -> None:
        card = next((c for c in self.cards if c.label == label), None)
        if card is not None:
            self.select_card(card)

    def select_card(self, card: SoundCard) -> None:
        self.current_card = card
        self.card_select.set(card.label)
        self._layout_signature = ()
        self.refresh_controls()
        if self.settings.last_card != card.id:
            self._update_state(last_card=card.id)

    def _on_tab_changed(self) -> None:
        self._update_state(last_tab=self.tabview.get())

    # --------------------------------------------------------------- controles
    def refresh_controls(self) -> None:
        if self.current_card is None:
            return
        try:
            controls = self.audio_controller.get_controls(self.current_card.index)
        except MixerError as exc:
            self._set_status(str(exc), error=True)
            return

        signature = tuple((c.key, tuple(c.capabilities), tuple(c.enum_items)) for c in controls)
        if signature != self._layout_signature:
            self._layout_signature = signature
            self._populate(controls)
            self._set_status(f"{self.current_card.name}: {len(controls)} controles")
        else:
            by_key = {c.key: c for c in controls}
            for panel in self.panels.values():
                panel.update_states(by_key)

    def _populate(self, controls: List[MixerControl]) -> None:
        layout = build_layout(controls)
        for section, panel in self.panels.items():
            panel.populate(layout[section])

    def _restart_polling(self) -> None:
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self.settings.poll_interval_ms > 0:
            self._poll_job = self.after(self.settings.poll_interval_ms, self._poll)

    def _poll(self) -> None:
        if not self.is_hidden:  # escondida na bandeja: não consulta o mixer à toa
            self.refresh_controls()
        self._poll_job = self.after(self.settings.poll_interval_ms, self._poll)

    def destroy(self) -> None:
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self._keeper_job is not None:
            self.after_cancel(self._keeper_job)
            self._keeper_job = None
        self.dispatcher.stop()
        self.tray.stop()
        super().destroy()

    # ---------------------------------------------------- estado salvo do mixer
    def _remember_switch(self, control: MixerControl, direction: Direction, enabled: bool) -> None:
        """Mudo alterado pelo usuário no app: vira o estado a ser restaurado/mantido."""
        if self.current_card is not None:
            self.state_store.remember(self.current_card.id, control.key, direction, enabled)

    def _is_switch_saved(self, control: MixerControl, direction: Direction) -> bool:
        return self.current_card is not None and \
            self.state_store.get(self.current_card.id, control.key, direction) is not None

    def clear_saved_states(self) -> None:
        self.state_store.clear()
        for panel in self.panels.values():
            for view in panel.views.values():
                if hasattr(view, "refresh_saved_badge"):
                    view.refresh_saved_badge()
        self._set_status("Estados salvos removidos.")

    def _restart_keeper(self) -> None:
        if self._keeper_job is not None:
            self.after_cancel(self._keeper_job)
            self._keeper_job = None
        if self.settings.keep_state or self.settings.restore_state:
            self._keeper_job = self.after(KEEP_STATE_INTERVAL_MS, self._keeper_tick)

    def _keeper_tick(self) -> None:
        """Roda inclusive com a janela escondida na bandeja (é aí que o login/suspensão acontecem)."""
        self._keeper_job = None
        keep = self.settings.keep_state
        in_startup_window = self.settings.restore_state and time.monotonic() < self._keeper_deadline
        if not (keep or in_startup_window):
            return
        self.enforce_saved_state()
        self._keeper_job = self.after(KEEP_STATE_INTERVAL_MS, self._keeper_tick)

    def enforce_saved_state(self) -> List[SwitchState]:
        result = self.state_keeper.enforce()
        if result.changed and hasattr(self, "status_label"):
            names = ", ".join(sorted({self._state_label(s) for s in result.corrected}))
            self._set_status(f"Estado restaurado (alterado pelo sistema): {names}")
            if not self.is_hidden:
                self.refresh_controls()
        return result.corrected

    @staticmethod
    def _state_label(state: SwitchState) -> str:
        name, _, index = state.control.rpartition(",")
        display = MixerControl(name=name, index=int(index) if index.isdigit() else 0).display_name
        return f"{display} ({state.card})"

    # ------------------------------------------------------------------ status
    def _on_action_error(self, control: MixerControl, error: MixerError) -> None:
        self._set_status(f"{control.display_name}: {error}", error=True)
        # Restaura a interface com o estado real do hardware
        for panel in self.panels.values():
            panel.reset_interactions()
        self.refresh_controls()

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.configure(text=text, text_color="#d9534f" if error else ("gray30", "gray70"))
