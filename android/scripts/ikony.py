"""Ikony aplikacji Android z ikon PWA (frontend/public/icons).

Tworzy mipmapy ``ic_launcher.png`` i ``ic_launcher_round.png`` (ikona zwykła) we wszystkich
gęstościach. Ikona adaptacyjna (Android 8+) jest wektorowa (``drawable/ic_launcher_*.xml``)
i odtwarza ten sam rysunek. Uruchomienie z katalogu repozytorium:

    python android/scripts/ikony.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "frontend" / "public" / "icons" / "icon-512.png"
RES = REPO / "android" / "android" / "app" / "src" / "main" / "res"
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    for density, size in DENSITIES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        icon = source.resize((size, size), Image.Resampling.LANCZOS)
        icon.save(folder / "ic_launcher.png", optimize=True)
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
        round_icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        round_icon.paste(icon, (0, 0), mask.resize((size, size), Image.Resampling.LANCZOS))
        round_icon.save(folder / "ic_launcher_round.png", optimize=True)
        stale = folder / "ic_launcher_foreground.png"
        if stale.exists():
            stale.unlink()
    print(f"Zapisano ikony w {RES}")


if __name__ == "__main__":
    main()
