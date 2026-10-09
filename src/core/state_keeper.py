from dataclasses import dataclass, field
from typing import Dict, List

from .interfaces import AudioController, MixerError
from .mixer_state import MixerStateStore, SwitchState


@dataclass
class EnforceResult:
    corrected: List[SwitchState] = field(default_factory=list)   # reaplicados (hardware estava diferente)
    errors: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.corrected)


class StateKeeper:
    """Compara os estados salvos com o hardware e reaplica os que divergirem.

    Lê apenas as placas que têm estado salvo; placas ausentes (ex.: USB
    desconectado) são ignoradas e tratadas quando reaparecerem.
    """

    def __init__(self, controller: AudioController, store: MixerStateStore):
        self._controller = controller
        self._store = store

    def enforce(self) -> EnforceResult:
        result = EnforceResult()
        if not len(self._store):
            return result
        try:
            cards = {card.id: card for card in self._controller.list_cards()}
        except MixerError as exc:
            result.errors.append(str(exc))
            return result

        by_card: Dict[str, List[SwitchState]] = {}
        for state in self._store.states():
            by_card.setdefault(state.card, []).append(state)

        for card_id, states in by_card.items():
            card = cards.get(card_id)
            if card is None:
                continue
            try:
                controls = {c.key: c for c in self._controller.get_controls(card.index)}
                for state in states:
                    control = controls.get(state.control)
                    current = control.switch(state.direction) if control else None
                    if current is None or current == state.enabled:
                        continue
                    self._controller.set_switch(card.index, control, state.direction, state.enabled)
                    result.corrected.append(state)
            except MixerError as exc:
                result.errors.append(f"{card.name}: {exc}")
        return result
