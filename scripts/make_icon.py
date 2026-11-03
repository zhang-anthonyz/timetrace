"""Generate the 时迹 / TimeTrace .ico and a preview PNG without external assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

SIZE = 1024
BASE = 256


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def build() -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    start = (125, 150, 255)
    middle = (109, 139, 255)
    end = (142, 109, 255)
    for y in range(SIZE):
        for_x = y / (SIZE - 1)
        color = mix(start, middle, min(1.0, for_x * 2)) if for_x < 0.5 else mix(
            middle, end, (for_x - 0.5) * 2
        )
        draw.line([(0, y), (SIZE, y)], fill=color + (255,))

    # Diagonal highlight.
    highlight = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlight)
    hdraw.ellipse(
        (-SIZE * 0.25, -SIZE * 0.70, SIZE * 0.95, SIZE * 0.45),
        fill=(255, 255, 255, 22),
    )
    gradient = Image.alpha_composite(gradient, highlight)

    mask = Image.new("L", (SIZE, SIZE), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(
        (5, 5, SIZE - 6, SIZE - 6),
        radius=int(SIZE * 0.27),
        fill=255,
    )
    canvas.paste(gradient, (0, 0), mask)

    d = ImageDraw.Draw(canvas)
    margin = SIZE * 0.235
    ring_width = max(8, int(SIZE * 0.070))
    d.ellipse(
        (margin, margin, SIZE - margin, SIZE - margin),
        outline=(255, 255, 255, 240),
        width=ring_width,
    )

    cx, cy = SIZE / 2, SIZE / 2
    hand_width = max(8, int(SIZE * 0.058))
    # 12 o'clock and roughly 4 o'clock hands.
    d.line([(cx, cy), (cx, SIZE * 0.316)], fill=(255, 255, 255, 245), width=hand_width)
    d.line([(cx, cy), (SIZE * 0.663, SIZE * 0.586)], fill=(255, 255, 255, 245), width=hand_width)

    dot_r = SIZE * 0.040
    d.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=(255, 255, 255, 250))

    return canvas.resize((BASE, BASE), Image.Resampling.LANCZOS)


def main() -> None:
    image = build()
    png_path = ASSETS / "timetrace.png"
    ico_path = ASSETS / "timetrace.ico"
    image.save(png_path)
    image.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {png_path}")
    print(f"wrote {ico_path}")


if __name__ == "__main__":
    main()
