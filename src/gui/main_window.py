import customtkinter as ctk
from src.core.interfaces import AudioController
from .theme_manager import ThemeManager


class AlsamixerGUI(ctk.CTk):
    def __init__(self, audio_controller: AudioController):
        super().__init__()
        self.audio_controller = audio_controller

        self.title("Python Alsamixer GUI")
        self.geometry("400x500")

        # --- Componentes Visuais ---
        self.title_label = ctk.CTkLabel(self, text="Alsamixer Control", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=20)

        # Seletor de Tema
        self.theme_frame = ctk.CTkFrame(self)
        self.theme_frame.pack(pady=10, fill="x", padx=20)

        self.theme_switch = ctk.CTkOptionMenu(
            self.theme_frame,
            values=["System", "Dark", "Light"],
            command=ThemeManager.apply_theme
        )
        self.theme_switch.pack(side="right", padx=10, pady=10)

        # Slider de Volume
        self.volume_frame = ctk.CTkFrame(self)
        self.volume_frame.pack(pady=20, fill="both", expand=True, padx=20)

        initial_vol = self.audio_controller.get_volume()
        self.vol_label = ctk.CTkLabel(self.volume_frame, text=f"Master Volume: {initial_vol}%")
        self.vol_label.pack(pady=10)

        self.slider = ctk.CTkSlider(self.volume_frame, from_=0, to=100, orientation="vertical",
                                    command=self._on_slider_move)
        self.slider.set(initial_vol)
        self.slider.pack(pady=20, expand=True, fill="y")

        self.mute_button = ctk.CTkButton(self.volume_frame, text="Mute", fg_color="red", command=self._on_mute_click)
        self.mute_button.pack(pady=15)

    def _on_slider_move(self, value):
        volume = int(value)
        self.vol_label.configure(text=f"Master Volume: {volume}%")
        self.audio_controller.set_volume(volume)  # Comunicação via Interface

    def _on_mute_click(self):
        self.audio_controller.toggle_mute()
