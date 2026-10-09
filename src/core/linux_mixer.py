import subprocess
from .interfaces import AudioController


class AlsaMixerController(AudioController):
    """Implementação real que controla o ALSA via comandos amixer."""

    def get_volume(self) -> int:
        # Lógica real do amixer para ler volume vai aqui
        return 50  # Mock inicial

    def set_volume(self, value: int) -> None:
        # Exemplo: subprocess.run(["amixer", "set", "Master", f"{value}%"])
        print(f"[ALSA] Volume alterado para: {value}%")

    def toggle_mute(self) -> bool:
        print("[ALSA] Alternando Mute")
        return True

    def is_muted(self) -> bool:
        return False
