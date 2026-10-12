"""Ícone do app a partir de src/assets/audio-wave.svg.

O SVG usa só caminhos retos (M/H/V/h/v/z); são convertidos em polígonos e
desenhados com o Pillow — sem depender de bibliotecas de SVG.
"""
import os
import re
import sys
from typing import List, Tuple

ICON_COLOR = (31, 106, 165, 255)  # azul do tema
_TOKEN_RE = re.compile(r"[MmHhVvZzLl]|-?\d*\.?\d+")


def asset_path(name: str) -> str:
    """Caminho de um asset, no código-fonte ou no binário do PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "assets", name)


def parse_svg(path: str) -> Tuple[float, List[List[Tuple[float, float]]]]:
    """Retorna (tamanho do viewBox, polígonos)."""
    with open(path, encoding="utf-8") as fh:
        svg = fh.read()
    view_box = float(re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+)', svg).group(1))
    polygons, current, x, y = [], [], 0.0, 0.0
    tokens = _TOKEN_RE.findall(" ".join(re.findall(r' d="([^"]+)"', svg)))
    i = 0
    while i < len(tokens):
        cmd = tokens[i]; i += 1
        if cmd in "Mm":
            if current:
                polygons.append(current)
            nx, ny = float(tokens[i]), float(tokens[i + 1]); i += 2
            x, y = (x + nx, y + ny) if cmd == "m" else (nx, ny)
            current = [(x, y)]
        elif cmd in "Ll":
            nx, ny = float(tokens[i]), float(tokens[i + 1]); i += 2
            x, y = (x + nx, y + ny) if cmd == "l" else (nx, ny)
            current.append((x, y))
        elif cmd in "Hh":
            v = float(tokens[i]); i += 1
            x = x + v if cmd == "h" else v
            current.append((x, y))
        elif cmd in "Vv":
            v = float(tokens[i]); i += 1
            y = y + v if cmd == "v" else v
            current.append((x, y))
        elif cmd in "Zz":
            if current:
                polygons.append(current)
                x, y = current[0]
            current = []
    if current:
        polygons.append(current)
    return view_box, polygons


def render_icon(size: int = 64, fg=(255, 255, 255, 255), bg=ICON_COLOR, padding: float = 0.14):
    """Desenha o ícone: SVG em `fg` sobre um quadrado `bg` (opaco: bom para a bandeja XEmbed)."""
    from PIL import Image, ImageDraw

    scale_up = 4  # desenha maior e reduz: bordas suaves
    big = size * scale_up
    image = Image.new("RGBA", (big, big), bg or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    view_box, polygons = parse_svg(asset_path("audio-wave.svg"))
    pad = big * padding
    k = (big - 2 * pad) / view_box
    for polygon in polygons:
        draw.polygon([(pad + px * k, pad + py * k) for px, py in polygon], fill=fg)
    return image.resize((size, size), Image.LANCZOS)
