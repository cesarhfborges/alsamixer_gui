from typing import Callable, Optional

from src.core.interfaces import AudioController, ControlActions, MixerError
from src.core.models import Direction, MixerControl

ErrorHandler = Callable[[MixerControl, MixerError], None]
SwitchListener = Callable[[MixerControl, Direction, bool], None]


class CardActions(ControlActions):
    """Encaminha as ações dos controles visuais ao AudioController para a placa atual.

    Erros do mixer são entregues ao `on_error`, sem propagar para os widgets.
    """

    def __init__(self, controller: AudioController, card_provider: Callable[[], Optional[int]],
                 on_error: ErrorHandler, on_success: Callable[[], None] = lambda: None,
                 on_switch: SwitchListener = lambda control, direction, enabled: None):
        self._controller = controller
        self._card_provider = card_provider
        self._on_error = on_error
        self._on_success = on_success
        self._on_switch = on_switch

    def set_volume(self, control: MixerControl, direction: Direction, percent: int) -> None:
        self._dispatch(self._controller.set_volume, control, direction, percent)

    def set_switch(self, control: MixerControl, direction: Direction, enabled: bool) -> None:
        if self._dispatch(self._controller.set_switch, control, direction, enabled):
            self._on_switch(control, direction, enabled)  # ex.: grava o estado para restaurar depois

    def set_enum(self, control: MixerControl, value: str) -> None:
        self._dispatch(self._controller.set_enum, control, value)

    def _dispatch(self, action, control: MixerControl, *args) -> bool:
        card = self._card_provider()
        if card is None:
            return False
        try:
            action(card, control, *args)
        except MixerError as exc:
            self._on_error(control, exc)
            return False
        self._on_success()
        return True
