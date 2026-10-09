from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# Nomes exibidos como no alsamixer (ex.: IEC958 é a saída digital S/PDIF)
_NAME_MAPPINGS = (
    ("IEC958", "S/PDIF"),
)


class Direction(str, Enum):
    PLAYBACK = "playback"
    CAPTURE = "capture"


@dataclass(frozen=True)
class SoundCard:
    index: int
    id: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.index}: {self.name}"


@dataclass
class MixerControl:
    """Estado de um 'simple mixer control' do ALSA."""
    name: str
    index: int = 0
    capabilities: List[str] = field(default_factory=list)
    playback_volume: Optional[int] = None   # 0-100 (média dos canais)
    capture_volume: Optional[int] = None
    playback_switch: Optional[bool] = None  # True = ligado (sem mudo)
    capture_switch: Optional[bool] = None
    enum_items: List[str] = field(default_factory=list)
    enum_value: Optional[str] = None

    @property
    def key(self) -> str:
        """Identificador aceito pelo amixer: 'Nome',indice."""
        return f"{self.name},{self.index}"

    @property
    def display_name(self) -> str:
        name = self.name
        for alsa_name, friendly in _NAME_MAPPINGS:
            name = name.replace(alsa_name, friendly)
        return name if self.index == 0 else f"{name} {self.index}"

    @property
    def is_enum(self) -> bool:
        return self.enum_value is not None

    def volume(self, direction: Direction) -> Optional[int]:
        return self.playback_volume if direction is Direction.PLAYBACK else self.capture_volume

    def switch(self, direction: Direction) -> Optional[bool]:
        return self.playback_switch if direction is Direction.PLAYBACK else self.capture_switch

    def has_volume(self, direction: Direction) -> bool:
        return self.volume(direction) is not None

    def has_switch(self, direction: Direction) -> bool:
        return self.switch(direction) is not None

    def is_muted(self, direction: Direction) -> bool:
        return self.switch(direction) is False
