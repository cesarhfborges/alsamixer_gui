import subprocess
from typing import Callable, List, Sequence

from .amixer_parser import parse_cards, parse_scontents
from .interfaces import AudioController, MixerError
from .models import Direction, MixerControl, SoundCard

Runner = Callable[[Sequence[str]], str]


def _run_command(args: Sequence[str]) -> str:
    try:
        result = subprocess.run(list(args), capture_output=True, text=True, timeout=5, check=False)
    except FileNotFoundError as exc:
        raise MixerError("Comando 'amixer' não encontrado. Instale o pacote alsa-utils.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MixerError(f"Tempo esgotado executando: {' '.join(args)}") from exc
    if result.returncode != 0:
        raise MixerError(result.stderr.strip() or f"Falha ao executar: {' '.join(args)}")
    return result.stdout


class AlsaMixerController(AudioController):
    """Implementação real que controla o ALSA via comandos amixer."""

    def __init__(self, runner: Runner = _run_command, cards_path: str = "/proc/asound/cards"):
        self._run = runner
        self._cards_path = cards_path

    def list_cards(self) -> List[SoundCard]:
        try:
            with open(self._cards_path, encoding="utf-8") as fh:
                return parse_cards(fh.read())
        except OSError as exc:
            raise MixerError(f"Não foi possível ler {self._cards_path}: {exc}") from exc

    def get_controls(self, card: int) -> List[MixerControl]:
        # -M: escala mapeada (perceptual), a mesma usada pelo alsamixer
        return parse_scontents(self._run(["amixer", "-c", str(card), "-M", "scontents"]))

    def _sset(self, card: int, control: MixerControl, *values: str) -> None:
        self._run(["amixer", "-q", "-c", str(card), "-M", "sset", control.key, *values])

    def set_volume(self, card: int, control: MixerControl, direction: Direction, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        if self._is_generic(control, "volume"):
            self._sset(card, control, f"{percent}%")
        else:
            self._sset(card, control, direction.value, f"{percent}%")

    def set_switch(self, card: int, control: MixerControl, direction: Direction, enabled: bool) -> None:
        if direction is Direction.CAPTURE:
            state = "cap" if enabled else "nocap"
        else:
            state = "unmute" if enabled else "mute"
        if self._is_generic(control, "switch"):
            self._sset(card, control, state)
        else:
            self._sset(card, control, direction.value, state)

    def set_enum(self, card: int, control: MixerControl, value: str) -> None:
        if value not in control.enum_items:
            raise MixerError(f"Valor inválido para {control.display_name}: {value}")
        self._sset(card, control, value)

    @staticmethod
    def _is_generic(control: MixerControl, kind: str) -> bool:
        """Controles 'volume'/'switch' sem direção não aceitam o prefixo playback/capture."""
        caps = set(control.capabilities)
        return bool({kind, f"{kind}-joined"} & caps)
