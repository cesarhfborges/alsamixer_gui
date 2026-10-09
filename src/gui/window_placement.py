"""Posicionamento de janelas em ambientes com vários monitores.

Por que existe: quando o gerenciador de janelas (ex.: Muffin/Cinnamon) escolhe a
posição, o Tk continua achando que a janela está em +0+0. Qualquer reaplicação de
geometria pelo CustomTkinter (ex.: mudança de escala) move a janela para lá — o
monitor mais à esquerda. Definindo sempre uma posição explícita, o Tk conhece a
posição real e a janela fica estável.
"""
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

_MONITOR_RE = re.compile(r"^\s*\d+:\s+\+?(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)")
_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)(?:([+-]-?\d+)([+-]-?\d+))?$")


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


def parse_xrandr_monitors(text: str) -> List[Monitor]:
    """Interpreta `xrandr --listmonitors` (ex.: ' 0: +*DP-0 1920/527x1080/296+1920+0  DP-0')."""
    monitors = []
    for line in text.splitlines():
        match = _MONITOR_RE.match(line)
        if match:
            star, name, width, height, x, y = match.groups()
            monitors.append(Monitor(name, int(x), int(y), int(width), int(height), primary=bool(star)))
    return monitors


def detect_monitors() -> List[Monitor]:
    try:
        output = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_xrandr_monitors(output)


def parse_geometry(geometry: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """'WxH+X+Y' → (w, h, x, y); partes ausentes ou inválidas → None."""
    match = _GEOMETRY_RE.match(geometry or "")
    if not match:
        return None, None, None, None
    w, h, x, y = match.groups()
    to_int = lambda v: int(v.replace("+-", "-")) if v is not None else None
    return int(w), int(h), to_int(x), to_int(y)


def monitor_at(monitors: List[Monitor], px: int, py: int) -> Optional[Monitor]:
    return next((m for m in monitors if m.contains(px, py)), None)


def primary_monitor(monitors: List[Monitor]) -> Optional[Monitor]:
    return next((m for m in monitors if m.primary), monitors[0] if monitors else None)


def center_on(monitor: Monitor, width: int, height: int) -> Tuple[int, int]:
    x = monitor.x + max(0, (monitor.width - width) // 2)
    y = monitor.y + max(0, (monitor.height - height) // 2)
    return x, y


def choose_position(width: int, height: int, saved: Optional[Tuple[Optional[int], Optional[int]]],
                    monitors: List[Monitor]) -> Optional[Tuple[int, int]]:
    """Posição da janela: a salva, se ainda visível em algum monitor; senão centralizada no principal.

    Retorna None quando não há informação de monitores (o gerenciador de janelas decide).
    """
    if saved and saved[0] is not None and saved[1] is not None:
        x, y = saved
        # A barra de título precisa estar em um monitor existente (ex.: monitor desconectado)
        if monitor_at(monitors, x + min(width, 200) // 2, y + 10):
            return x, y
    monitor = primary_monitor(monitors)
    return center_on(monitor, width, height) if monitor else None
