"""Funções puras para interpretar a saída do ALSA (sem efeitos colaterais)."""
import re
from typing import List, Optional

from .models import Direction, MixerControl, SoundCard

_CARD_RE = re.compile(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(.*?)\s+-\s+(.*)$")
_CONTROL_RE = re.compile(r"^Simple mixer control '(.*)',(\d+)$")
_SEGMENT_RE = re.compile(r"\b(Playback|Capture)\b")
_PERCENT_RE = re.compile(r"\[(\d+)%\]")
_SWITCH_RE = re.compile(r"\[(on|off)\]")
_QUOTED_RE = re.compile(r"'((?:[^'\\]|\\.)*)'")

# Linhas de cabeçalho que não descrevem um canal
_HEADER_KEYS = ("Capabilities", "Playback channels", "Capture channels", "Limits", "Items")

# Palavras que indicam que um controle genérico ('volume'/'switch') pertence à captura
_CAPTURE_HINTS = ("mic", "capture", "boost", "input", "adc", "digital in")


def parse_cards(text: str) -> List[SoundCard]:
    """Interpreta o conteúdo de /proc/asound/cards."""
    cards = []
    for line in text.splitlines():
        match = _CARD_RE.match(line)
        if match:
            index, card_id, _driver, name = match.groups()
            cards.append(SoundCard(index=int(index), id=card_id, name=name.strip()))
    return cards


def _generic_direction(name: str) -> Direction:
    lowered = name.lower()
    if any(hint in lowered for hint in _CAPTURE_HINTS):
        return Direction.CAPTURE
    return Direction.PLAYBACK


def _average(values: List[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None


def _finalize(control: MixerControl, volumes: dict, switches: dict) -> MixerControl:
    caps = set(control.capabilities)
    generic = _generic_direction(control.name)

    # Controles genéricos ('volume'/'switch') são atribuídos a uma direção por heurística
    if "volume" in caps or "volume-joined" in caps:
        volumes[generic] += volumes.pop(None, [])
    if "switch" in caps or "switch-joined" in caps:
        switches[generic] += switches.pop(None, [])

    has_pvol = bool(caps & {"pvolume", "pvolume-joined"}) or volumes[Direction.PLAYBACK]
    has_cvol = bool(caps & {"cvolume", "cvolume-joined"}) or volumes[Direction.CAPTURE]
    has_psw = bool(caps & {"pswitch", "pswitch-joined"}) or switches[Direction.PLAYBACK]
    has_csw = bool(caps & {"cswitch", "cswitch-joined", "cswitch-exclusive"}) or switches[Direction.CAPTURE]

    if has_pvol:
        control.playback_volume = _average(volumes[Direction.PLAYBACK]) or 0
    if has_cvol:
        control.capture_volume = _average(volumes[Direction.CAPTURE]) or 0
    if has_psw:
        # Considera ligado se qualquer canal estiver ligado
        control.playback_switch = any(switches[Direction.PLAYBACK]) if switches[Direction.PLAYBACK] else True
    if has_csw:
        control.capture_switch = any(switches[Direction.CAPTURE]) if switches[Direction.CAPTURE] else True
    return control


def _parse_channel_values(value: str, volumes: dict, switches: dict) -> None:
    """Interpreta 'Playback 86 [97%] [-0.75dB] [on]' (pode conter Playback e Capture)."""
    parts = _SEGMENT_RE.split(value)
    # parts = [prefixo, 'Playback', resto, 'Capture', resto, ...]
    segments = [(None, parts[0])]
    for i in range(1, len(parts) - 1, 2):
        segments.append((Direction(parts[i].lower()), parts[i + 1]))

    for direction, segment in segments:
        for pct in _PERCENT_RE.findall(segment):
            volumes[direction].append(int(pct))
        for state in _SWITCH_RE.findall(segment):
            switches[direction].append(state == "on")


def parse_scontents(text: str) -> List[MixerControl]:
    """Interpreta a saída de `amixer -c N [-M] scontents`."""
    controls: List[MixerControl] = []
    current: Optional[MixerControl] = None
    volumes: dict = {}
    switches: dict = {}

    def new_buckets():
        return {Direction.PLAYBACK: [], Direction.CAPTURE: [], None: []}

    for raw in text.splitlines():
        header = _CONTROL_RE.match(raw)
        if header:
            if current is not None:
                controls.append(_finalize(current, volumes, switches))
            current = MixerControl(name=header.group(1), index=int(header.group(2)))
            volumes, switches = new_buckets(), new_buckets()
            continue
        if current is None or ":" not in raw:
            continue

        key, _, value = raw.strip().partition(":")
        value = value.strip()

        if key == "Capabilities":
            current.capabilities = value.split()
        elif key == "Items":
            current.enum_items = [item.replace("\\'", "'") for item in _QUOTED_RE.findall(value)]
        elif re.fullmatch(r"Item\d+", key):
            if current.enum_value is None:
                found = _QUOTED_RE.findall(value)
                current.enum_value = found[0].replace("\\'", "'") if found else value
        elif key in _HEADER_KEYS:
            continue
        else:
            _parse_channel_values(value, volumes, switches)

    if current is not None:
        controls.append(_finalize(current, volumes, switches))
    return controls

