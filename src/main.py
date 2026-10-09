import sys
import os
import argparse
import time
import traceback

# Adiciona o diretório raiz ao PATH do Python para evitar problemas de importação
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.autostart import AutostartManager
from src.core.linux_mixer import AlsaMixerController
from src.core.mixer_state import JsonMixerStateRepository, MixerStateStore
from src.core.settings import JsonSettingsRepository
from src.core.state_keeper import StateKeeper

# Ao aplicar sem interface, continua conferindo por um tempo: o PipeWire/WirePlumber
# pode terminar de iniciar (e desligar o S/PDIF) depois deste comando
APPLY_STATE_WINDOW_S = 30
APPLY_STATE_INTERVAL_S = 2


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="GUI para o mixer ALSA")
    parser.add_argument("--autostart", action="store_true",
                        help="iniciado com o sistema: abre só com o ícone na bandeja (se ativa)")
    parser.add_argument("--apply-state", action="store_true",
                        help="aplica os estados de mudo salvos, sem interface, e encerra")
    return parser.parse_args(argv)


def apply_state_headless() -> int:
    keeper = StateKeeper(AlsaMixerController(), MixerStateStore(JsonMixerStateRepository()))
    deadline = time.monotonic() + APPLY_STATE_WINDOW_S
    while True:
        result = keeper.enforce()
        for state in result.corrected:
            print(f"Reaplicado: {state.card} {state.control} {state.direction.value} -> "
                  f"{'ligado' if state.enabled else 'mudo'}")
        for error in result.errors:
            print(f"Erro: {error}", file=sys.stderr)
        if time.monotonic() >= deadline:
            return 0
        time.sleep(APPLY_STATE_INTERVAL_S)


def main(argv=None):
    args = parse_args(argv)
    if args.apply_state:
        return apply_state_headless()

    import customtkinter as ctk
    from src.gui.main_window import AlsamixerGUI
    from src.gui.single_instance import SingleInstance

    # 1. Uma única instância: se já houver uma (ex.: escondida na bandeja), ela é exibida
    #    (exceto no início automático, que não deve abrir a janela)
    instance = SingleInstance()
    if not instance.acquire(show_existing=not args.autostart):
        print("O Alsamixer GUI já está em execução.")
        return 0

    ctk.set_default_color_theme("blue")

    # 2. Instancia a lógica de controle (Core), as configurações e o estado salvo do mixer
    mixer_service = AlsaMixerController()
    settings_repository = JsonSettingsRepository()
    state_store = MixerStateStore(JsonMixerStateRepository())

    # 3. Injeta as dependências na Interface Gráfica (DIP do SOLID)
    app = AlsamixerGUI(audio_controller=mixer_service, settings_repository=settings_repository,
                       mixer_state_store=state_store, autostart=AutostartManager(),
                       start_in_tray=args.autostart)
    instance.on_message = lambda message: app.dispatcher.post(app.show_window) if message == b"show" else None
    try:
        app.mainloop()
    finally:
        instance.release()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        exit()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
