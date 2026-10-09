import sys
import os

# Adiciona o diretório raiz ao PATH do Python para evitar problemas de importação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from src.core.linux_mixer import AlsaMixerController
from src.gui.main_window import AlsamixerGUI
from src.gui.theme_manager import ThemeManager


def main():
    # 1. Configura o tema inicial do sistema
    initial_mode = ThemeManager.detect_system_mode()
    ctk.set_appearance_mode(initial_mode)
    ctk.set_default_color_theme("blue")

    # 2. Instancia a lógica de controle (Core)
    mixer_service = AlsaMixerController()

    # 3. Injeta o serviço do Mixer na Interface Gráfica (DIP do SOLID)
    app = AlsamixerGUI(audio_controller=mixer_service)

    # Atualiza o estado visual do menu de temas
    app.theme_switch.set(initial_mode)

    app.mainloop()


if __name__ == "__main__":
    main()
