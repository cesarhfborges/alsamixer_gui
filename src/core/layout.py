"""Classificação dos controles do mixer em seções (Saída / Entrada / Opções).

Independente da GUI: descreve *o que* exibir, não *como* exibir.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .models import Direction, MixerControl


class ControlKind(str, Enum):
    VOLUME = "volume"  # faixa de canal: slider de volume e/ou mudo
    ENUM = "enum"      # lista de opções


class Section(str, Enum):
    OUTPUT = "Saída"
    INPUT = "Entrada"
    OPTIONS = "Opções"


@dataclass
class ControlSpec:
    """Descreve um controle a ser exibido: o estado, o tipo de visualização e a direção."""
    control: MixerControl
    kind: ControlKind
    direction: Optional[Direction] = None

    @property
    def key(self) -> Tuple[str, str, str]:
        return self.control.key, self.kind.value, self.direction.value if self.direction else ""


def _channel_specs(controls: List[MixerControl], direction: Direction) -> List[ControlSpec]:
    """Faixas da direção: controles com volume e/ou chave (mudo) nela — inclui S/PDIF."""
    return [
        ControlSpec(c, ControlKind.VOLUME, direction)
        for c in controls
        if not c.is_enum and (c.has_volume(direction) or c.has_switch(direction))
    ]


def _option_specs(controls: List[MixerControl]) -> List[ControlSpec]:
    """Opções do sistema: enumerações (ex.: Auto-Mute Mode, Input Source)."""
    return [ControlSpec(c, ControlKind.ENUM) for c in controls if c.is_enum]


def build_layout(controls: List[MixerControl]) -> Dict[Section, List[ControlSpec]]:
    return {
        Section.OUTPUT: _channel_specs(controls, Direction.PLAYBACK),
        Section.INPUT: _channel_specs(controls, Direction.CAPTURE),
        Section.OPTIONS: _option_specs(controls),
    }
