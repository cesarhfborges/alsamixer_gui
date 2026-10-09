"""Estado desejado dos controles do mixer (por enquanto: mudo/ligado).

Arquivo: $XDG_CONFIG_HOME/alsamixer-gui/mixer-state.json

Por que existe: o ALSA salva o estado no desligamento (alsactl store), mas após o
login o PipeWire/WirePlumber reaplica o perfil da placa — e o perfil analógico
desliga o S/PDIF ("[Element IEC958] switch = off"). O app guarda o que o usuário
escolheu e o reaplica depois que o sistema terminou de iniciar.
"""
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .models import Direction
from .storage import atomic_write_json, config_dir

MIXER_STATE_VERSION = 1
StateKey = Tuple[str, str, str]


@dataclass(frozen=True)
class SwitchState:
    card: str            # id da placa em /proc/asound/cards (ex.: "PCH") — estável, ao contrário do índice
    control: str         # chave do controle no amixer (ex.: "IEC958,0")
    direction: Direction
    enabled: bool        # True = ligado (sem mudo)

    @property
    def key(self) -> StateKey:
        return self.card, self.control, self.direction.value

    def to_dict(self) -> dict:
        return {"card": self.card, "control": self.control, "direction": self.direction.value,
                "enabled": self.enabled}

    @classmethod
    def from_dict(cls, data: dict) -> Optional["SwitchState"]:
        try:
            card, control, enabled = data["card"], data["control"], data["enabled"]
            direction = Direction(data["direction"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (isinstance(card, str) and isinstance(control, str) and isinstance(enabled, bool)):
            return None
        return cls(card, control, direction, enabled)


class MixerStateRepository(ABC):
    @abstractmethod
    def load(self) -> List[SwitchState]:
        pass

    @abstractmethod
    def save(self, states: List[SwitchState]) -> None:
        pass


class InMemoryMixerStateRepository(MixerStateRepository):
    def __init__(self, states: Optional[List[SwitchState]] = None):
        self.states = list(states or [])
        self.saves = 0

    def load(self) -> List[SwitchState]:
        return list(self.states)

    def save(self, states: List[SwitchState]) -> None:
        self.states = list(states)
        self.saves += 1


def default_mixer_state_path() -> str:
    return os.path.join(config_dir(), "mixer-state.json")


class JsonMixerStateRepository(MixerStateRepository):
    def __init__(self, path: Optional[str] = None):
        self.path = path or default_mixer_state_path()

    def load(self) -> List[SwitchState]:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return []
        items = data.get("switches", []) if isinstance(data, dict) else []
        return [s for s in (SwitchState.from_dict(i) for i in items if isinstance(i, dict)) if s]

    def save(self, states: List[SwitchState]) -> None:
        atomic_write_json(self.path, {"version": MIXER_STATE_VERSION,
                                      "switches": [s.to_dict() for s in states]})


class MixerStateStore:
    """Estados salvos em memória + persistência a cada alteração."""

    def __init__(self, repository: MixerStateRepository):
        self._repository = repository
        self._states: Dict[StateKey, SwitchState] = {s.key: s for s in repository.load()}

    def remember(self, card: str, control: str, direction: Direction, enabled: bool) -> None:
        state = SwitchState(card, control, direction, enabled)
        if self._states.get(state.key) != state:
            self._states[state.key] = state
            self._repository.save(self.states())

    def get(self, card: str, control: str, direction: Direction) -> Optional[SwitchState]:
        return self._states.get((card, control, direction.value))

    def states(self) -> List[SwitchState]:
        return list(self._states.values())

    def for_card(self, card: str) -> List[SwitchState]:
        return [s for s in self._states.values() if s.card == card]

    def clear(self) -> None:
        self._states.clear()
        self._repository.save([])

    def __len__(self) -> int:
        return len(self._states)
