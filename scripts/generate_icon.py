"""Genera el icono de FichaManual (.png y .ico)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def make_base(size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo redondeado azul documento
    margin = size // 16
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=size // 6,
        fill=(24, 90, 140, 255),
    )

    # Página/ficha blanca
    pad = size // 5
    page = [
        pad,
        pad - size // 32,
        size - pad,
        size - pad + size // 32,
    ]
    draw.rounded_rectangle(page, radius=size // 18, fill=(245, 248, 252, 255))

    # Doblez esquina
    fold = size // 7
    x1, y1 = size - pad - fold, pad - size // 32
    draw.polygon(
        [(x1, y1), (size - pad, y1), (size - pad, y1 + fold)],
        fill=(210, 222, 235, 255),
    )

    # Líneas de texto (resumen)
    line_left = pad + size // 12
    line_right = size - pad - size // 10
    y = pad + size // 7
    gap = size // 11
    widths = (1.0, 0.92, 0.78, 0.85, 0.55)
    for i, w in enumerate(widths):
        right = int(line_left + (line_right - line_left) * w)
        color = (40, 110, 170, 255) if i == 0 else (120, 145, 170, 255)
        thickness = max(2, size // 28) if i == 0 else max(2, size // 36)
        draw.rounded_rectangle(
            (line_left, y, right, y + thickness),
            radius=thickness // 2,
            fill=color,
        )
        y += gap

    # Marca "FM"
    badge_r = size // 5
    cx, cy = size - pad // 2 - badge_r // 2, size - pad // 2 - badge_r // 2
    draw.ellipse(
        (cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r),
        fill=(232, 145, 45, 255),
    )
    font = _font(max(10, size // 4))
    text = "FM"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2, cy - th / 2 - size // 40), text, fill="white", font=font)
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    base = make_base(256)
    png_path = ASSETS / "fichamanual.png"
    ico_path = ASSETS / "fichamanual.ico"
    base.save(png_path)
    icons = [make_base(s) for s in SIZES]
    icons[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Creado: {png_path}")
    print(f"Creado: {ico_path}")


if __name__ == "__main__":
    main()
