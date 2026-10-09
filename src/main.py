import sys
import os

# Adiciona o diretório raiz ao PATH do Python para evitar problemas de importação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from src.core.linux_mixer import AlsaMixerController
from src.core.settings import JsonSettingsRepository
from src.gui.main_window import AlsamixerGUI
from src.gui.single_instance import SingleInstance


def main():
    # 1. Uma única instância: se já houver uma (ex.: escondida na bandeja), ela é exibida
    instance = SingleInstance()
    if not instance.acquire():
        print("O Alsamixer GUI já está em execução; exibindo a janela existente.")
        return

    ctk.set_default_color_theme("blue")

    # 2. Instancia a lógica de controle (Core) e o armazenamento das configurações
    mixer_service = AlsaMixerController()
    settings_repository = JsonSettingsRepository()

    # 3. Injeta as dependências na Interface Gráfica (DIP do SOLID);
    #    tema, escala, placa inicial e bandeja vêm das configurações salvas
    app = AlsamixerGUI(audio_controller=mixer_service, settings_repository=settings_repository)
    instance.on_message = lambda message: app.dispatcher.post(app.show_window)
    try:
        app.mainloop()
    finally:
        instance.release()


if __name__ == "__main__":
    main()
