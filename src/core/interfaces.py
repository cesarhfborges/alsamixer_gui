from abc import ABC, abstractmethod

class AudioController(ABC):
    @abstractmethod
    def get_volume(self) -> int:
        pass

    @abstractmethod
    def set_volume(self, value: int) -> None:
        pass

    @abstractmethod
    def toggle_mute(self) -> bool:
        pass

    @abstractmethod
    def is_muted(self) -> bool:
        pass
