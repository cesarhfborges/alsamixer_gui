from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

from src.core.interfaces import AudioController, MixerError
from src.core.layout import Section, build_layout
from src.core.models import MixerControl, SoundCard
from src.core.settings import AppSettings, InMemorySettingsRepository, SettingsRepository
from .actions import CardActions
from .control_panel import ControlPanel
from .control_widgets import ControlViewFactory
from .settings_dialog import SettingsDialog
from .theme_manager import ThemeManager

NO_CARD = "(nenhuma)"
DEFAULT_GEOMETRY = "960x620"


class AlsamixerGUI(ctk.CTk):
    def __init__(self, audio_controller: AudioController,
                 settings_repository: Optional[SettingsRepository] = None,
                 view_factory: Optional[ControlViewFactory] = None):
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
        )

        self.cards: List[SoundCard] = []
        self.current_card: Optional[SoundCard] = None
        self.settings_dialog: Optional[SettingsDialog] = None
        self._layout_signature: Tuple = ()
        self._poll_job: Optional[str] = None

        self.title("Python Alsamixer GUI")
        self.minsize(560, 480)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.apply_settings(self.settings)
        self._restore_geometry()

        self._build_header()
        self._build_card_selector()
        self._build_tabs()
        self.status_label = ctk.CTkLabel(self, text="", anchor="w")
        self.status_label.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.reload_cards(initial=True)
        self.tabview.set(self.settings.initial_tab())

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
        font = ctk.CTkFont(size=15)
        ctk.CTkLabel(toolbar, text="Placa de som:", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, padx=(12, 8), pady=10)
        self.card_select = ctk.CTkOptionMenu(toolbar, values=[NO_CARD], height=40, font=font,
                                             dropdown_font=font, dynamic_resizing=False,
                                             command=self._on_card_selected)
        self.card_select.grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        self.reload_button = ctk.CTkButton(toolbar, text="Recarregar", width=120, height=40, font=font,
                                           command=self.reload_cards)
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

    # ----------------------------------------------------------- configurações
    def apply_settings(self, settings: AppSettings) -> None:
        """Aplica as preferências em tempo de execução."""
        self.settings = settings
        ThemeManager.apply_theme(settings.theme)
        ctk.set_widget_scaling(settings.ui_scale)
        self.view_factory.options.wheel_step = settings.wheel_step
        self._restart_polling()

    def open_settings(self) -> None:
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.focus()
            return
        self.settings_dialog = SettingsDialog(self, self.settings, self.cards, on_save=self._on_settings_saved,
                                              location=self.settings_repository.location)

    def _on_settings_saved(self, settings: AppSettings) -> None:
        self.apply_settings(settings)
        self._save_settings()
        self._set_status("Configurações salvas.")

    def _update_state(self, **state) -> None:
        self.settings = replace(self.settings, **state)
        self._save_settings()

    def _save_settings(self) -> None:
        try:
            self.settings_repository.save(self.settings)
        except OSError as exc:
            self._set_status(f"Não foi possível salvar as configurações: {exc}", error=True)

    def _restore_geometry(self) -> None:
        geometry = self.settings.window_geometry if self.settings.remember_window else None
        try:
            self.geometry(geometry or DEFAULT_GEOMETRY)
        except Exception:
            self.geometry(DEFAULT_GEOMETRY)

    def close(self) -> None:
        if self.settings.remember_window:
            # Só o tamanho: a posição informada pelo gerenciador de janelas não é confiável
            self._update_state(window_geometry=self.geometry().split("+")[0].split("-")[0])
        self.destroy()

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
        self.refresh_controls()
        self._poll_job = self.after(self.settings.poll_interval_ms, self._poll)

    def destroy(self) -> None:
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        super().destroy()

    # ------------------------------------------------------------------ status
    def _on_action_error(self, control: MixerControl, error: MixerError) -> None:
        self._set_status(f"{control.display_name}: {error}", error=True)
        # Restaura a interface com o estado real do hardware
        for panel in self.panels.values():
            panel.reset_interactions()
        self.refresh_controls()

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.configure(text=text, text_color="#d9534f" if error else ("gray30", "gray70"))
