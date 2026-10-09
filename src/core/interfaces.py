from abc import ABC, abstractmethod
from typing import List

from .models import Direction, MixerControl, SoundCard


class MixerError(Exception):
    """Falha ao consultar ou alterar o mixer."""


class AudioController(ABC):
    @abstractmethod
    def list_cards(self) -> List[SoundCard]:
        pass

    @abstractmethod
    def get_controls(self, card: int) -> List[MixerControl]:
        pass

    @abstractmethod
    def set_volume(self, card: int, control: MixerControl, direction: Direction, percent: int) -> None:
        pass

    @abstractmethod
    def set_switch(self, card: int, control: MixerControl, direction: Direction, enabled: bool) -> None:
        """enabled=True liga o canal (sem mudo); False coloca em mudo."""
        pass

    @abstractmethod
    def set_enum(self, card: int, control: MixerControl, value: str) -> None:
        pass


class ControlActions(ABC):
    """Ações disparadas pelos controles visuais, já vinculadas à placa selecionada."""

    @abstractmethod
    def set_volume(self, control: MixerControl, direction: Direction, percent: int) -> None:
        pass

    @abstractmethod
    def set_switch(self, control: MixerControl, direction: Direction, enabled: bool) -> None:
        pass

    @abstractmethod
    def set_enum(self, control: MixerControl, value: str) -> None:
        pass
