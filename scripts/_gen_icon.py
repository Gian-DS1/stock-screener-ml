"""Genera scripts/sniper.ico (mira verde sobre fondo oscuro) para los accesos directos.
Uso único: uv run --with pillow python scripts/_gen_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

INK = (11, 15, 20, 255)
GREEN = (61, 220, 151, 255)


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    pad = s * 0.06
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=s * 0.18, fill=INK)
    cx = cy = s / 2
    r = s * 0.30
    w = max(2, int(s * 0.05))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GREEN, width=w)
    tick = s * 0.12
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        d.line(
            [cx + dx * (r - tick / 2), cy + dy * (r - tick / 2),
             cx + dx * (r + tick), cy + dy * (r + tick)],
            fill=GREEN, width=w,
        )
    d.ellipse([cx - s * 0.04, cy - s * 0.04, cx + s * 0.04, cy + s * 0.04], fill=GREEN)
    return img


out = Path(__file__).parent / "sniper.ico"
base = draw(256)
base.save(out, format="ICO", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"icono generado: {out}")
