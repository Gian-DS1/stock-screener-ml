"""Genera scripts/stock.ico (gráfico de velas verde sobre fondo oscuro) para
los accesos directos. Uso único: uv run --with pillow python scripts/_gen_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

INK = (11, 15, 20, 255)
EDGE = (28, 36, 46, 255)
GREEN = (61, 220, 151, 255)


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    pad = s * 0.06
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=s * 0.18, fill=INK, outline=EDGE,
                        width=max(1, int(s * 0.01)))

    wick = max(2, int(s * 0.05))
    # tres velas alcistas ascendentes: (centro x, mecha y0, mecha y1, cuerpo y0, cuerpo y1)
    candles = [
        (0.28, 0.30, 0.74, 0.46, 0.64),
        (0.50, 0.20, 0.68, 0.32, 0.54),
        (0.72, 0.36, 0.82, 0.50, 0.70),
    ]
    body_w = s * 0.13
    for cx, wy0, wy1, by0, by1 in candles:
        x = cx * s
        d.line([x, wy0 * s, x, wy1 * s], fill=GREEN, width=wick)
        d.rounded_rectangle(
            [x - body_w / 2, by0 * s, x + body_w / 2, by1 * s],
            radius=max(1, int(s * 0.02)), fill=GREEN,
        )
    return img


out = Path(__file__).parent / "stock.ico"
base = draw(256)
base.save(out, format="ICO", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"icono generado: {out}")
