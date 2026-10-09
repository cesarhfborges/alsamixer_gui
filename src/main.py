import sys
import os

# Adiciona o diretório raiz ao PATH do Python para evitar problemas de importação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from src.core.linux_mixer import AlsaMixerController
from src.core.settings import JsonSettingsRepository
from src.gui.main_window import AlsamixerGUI


def main():
    ctk.set_default_color_theme("blue")

    # 1. Instancia a lógica de controle (Core) e o armazenamento das configurações
    mixer_service = AlsaMixerController()
    settings_repository = JsonSettingsRepository()

    # 2. Injeta as dependências na Interface Gráfica (DIP do SOLID);
    #    tema, escala e placa inicial vêm das configurações salvas
    app = AlsamixerGUI(audio_controller=mixer_service, settings_repository=settings_repository)
    app.mainloop()


if __name__ == "__main__":
    main()
