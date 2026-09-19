"""Narzędzia modułu Obrazy: usuwanie tła (rembg), zmiana tła, gumka obiektów (inpainting)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import Field

from nexus.tools.base import (
    OutputFile,
    ToolContext,
    ToolError,
    ToolInput,
    ToolResult,
    image_preview,
    registry,
)
from nexus.tools.common import file_kind, open_image, unique_name, with_suffix
from nexus.tworczy.obrazy import (
    ImageOpError,
    compose_background,
    erase_with_mask,
    has_transparency,
    regions_mask,
    remove_background,
)

MAX_PIXELS = 40_000_000
JPEG_QUALITY = 92


def _load(ctx: ToolContext, file_id: str) -> tuple[str, Image.Image]:
    file = ctx.file(file_id)
    if file_kind(file) != "image":
        raise ToolError(f"{file.name} nie jest obrazem.")
    image = open_image(file.path)
    if image.width * image.height > MAX_PIXELS:
        raise ToolError(f"{file.name}: obraz jest zbyt duży ({image.width}×{image.height}).")
    return file.name, image


def cutout_of(ctx: ToolContext, name: str, image: Image.Image, fast: bool = False) -> Image.Image:
    """Wycinek obiektu: obraz z przezroczystym tłem albo wynik rembg."""
    if has_transparency(image):
        return image.convert("RGBA")
    rembg = ctx.settings.tworczy_rembg_bin
    if not Path(rembg).is_file():
        raise ToolError("Usuwanie tła jest niedostępne (brak programu rembg na serwerze).")
    staged = ctx.output_path("wejscie.png")
    image.convert("RGB").save(staged)
    ctx.progress(f"Wycinanie obiektu z tła: {name}")
    try:
        return remove_background(
            lambda command: ctx.run_command(command, timeout=900),
            rembg,
            ctx.settings.tworczy_rembg_fast_model if fast else ctx.settings.tworczy_rembg_model,
            staged,
            staged.with_name("wycinek.png"),
        )
    except ImageOpError as error:
        raise ToolError(str(error)) from error


def _save(ctx: ToolContext, image: Image.Image, name: str, used: set[str]) -> Path:
    transparent = image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255
    suffix = Path(name).suffix.lower()
    if transparent or suffix not in {".jpg", ".jpeg", ".webp"}:
        name = str(Path(name).with_suffix(".png"))
    target = ctx.output_path(unique_name(name, used))
    if target.suffix == ".png":
        image.save(target, optimize=True)
    else:
        image.convert("RGB").save(target, quality=JPEG_QUALITY, optimize=True)
    return target


def _preview(image: Image.Image) -> bytes:
    if image.mode == "RGBA":
        # Przezroczystość na szachownicy, żeby model widział krawędzie wycięcia.
        board = Image.new("RGBA", image.size, (255, 255, 255, 255))
        tile = max(8, min(image.size) // 40)
        dark = Image.new("RGBA", (tile, tile), (205, 205, 210, 255))
        for top in range(0, image.height, tile):
            for left in range((top // tile) % 2 * tile, image.width, tile * 2):
                board.paste(dark, (left, top))
        return image_preview(Image.alpha_composite(board, image))
    return image_preview(image)


class RemoveBackgroundInput(ToolInput):
    file_ids: list[str] = Field(min_length=1, max_length=20, description="Obrazy (zdjęcia produktów, osób…).")
    fast: bool = Field(False, description="Szybszy, mniej dokładny model wycinania (kilka sekund).")


@registry.register(
    "remove_background",
    """Usuwa tło ze zdjęcia (AI, rembg): wynik PNG z przezroczystym tłem – do sklepów, ogłoszeń,
grafik. Dla nowego tła (kolor, gradient, inne zdjęcie, rozmycie) użyj change_background.""",
    RemoveBackgroundInput,
)
def remove_background_tool(ctx: ToolContext, args: RemoveBackgroundInput) -> ToolResult:
    used: set[str] = set()
    outputs: list[OutputFile] = []
    previews: list[bytes] = []
    for file_id in args.file_ids:
        ctx.check_cancelled()
        name, image = _load(ctx, file_id)
        cutout = cutout_of(ctx, name, image, args.fast)
        target = _save(ctx, cutout, with_suffix(name, ".png", "_bez_tla"), used)
        outputs.append(OutputFile(target, target.name, f"{name} bez tła"))
        if len(previews) < 3:
            previews.append(_preview(cutout))
    return ToolResult(
        {"outputs": [item.name for item in outputs]},
        f"Usunięto tło: {len(outputs)} obr.",
        images=previews,
        files=outputs,
    )


class ChangeBackgroundInput(ToolInput):
    file_id: str = Field(description="Zdjęcie z obiektem (albo gotowy wycinek PNG z przezroczystością).")
    mode: Literal["color", "gradient", "image", "blur", "transparent"] = Field(
        description="Nowe tło: jednolity kolor, gradient, inne zdjęcie, rozmyty oryginał albo przezroczyste."
    )
    color: str = Field("#ffffff", description="Kolor tła albo początek gradientu (#rrggbb).")
    color2: str = Field("#e4e4e7", description="Koniec gradientu (#rrggbb).")
    angle: float = Field(90, ge=0, le=360, description="Kierunek gradientu w stopniach (90 = z góry na dół).")
    background_file_id: str | None = Field(None, description="Zdjęcie tła (mode='image').")
    original_file_id: str | None = Field(
        None, description="Oryginalne zdjęcie do rozmycia (mode='blur'), gdy file_id jest już wycinkiem."
    )
    blur_radius: float = Field(18, ge=1, le=120, description="Siła rozmycia tła (mode='blur').")
    fast: bool = Field(False, description="Szybszy, mniej dokładny model wycinania (kilka sekund).")


@registry.register(
    "change_background",
    """Zmienia tło zdjęcia: wycina obiekt (rembg) i nakłada go na jednolity kolor, gradient, inne
zdjęcie albo rozmyte oryginalne tło (efekt portretowy).""",
    ChangeBackgroundInput,
)
def change_background(ctx: ToolContext, args: ChangeBackgroundInput) -> ToolResult:
    name, image = _load(ctx, args.file_id)
    original = image
    if args.mode == "blur" and has_transparency(image):
        if not args.original_file_id:
            raise ToolError("Rozmycie tła wymaga oryginalnego zdjęcia (original_file_id).")
        original = _load(ctx, args.original_file_id)[1]
    background = (
        _load(ctx, args.background_file_id)[1] if args.mode == "image" and args.background_file_id else None
    )
    if args.mode == "image" and background is None:
        raise ToolError("Podaj background_file_id – zdjęcie nowego tła.")
    cutout = cutout_of(ctx, name, image, args.fast)
    ctx.progress("Składanie nowego tła")
    try:
        result = compose_background(
            cutout,
            args.mode,
            color=args.color,
            color2=args.color2,
            angle=args.angle,
            background=background,
            original=original,
            blur_radius=args.blur_radius,
        )
    except ImageOpError as error:
        raise ToolError(str(error)) from error
    target = _save(ctx, result, with_suffix(name, Path(name).suffix or ".png", "_nowe_tlo"), set())
    return ToolResult(
        {"output": target.name, "mode": args.mode},
        f"Nowe tło ({args.mode}): {name}",
        images=[_preview(result)],
        files=[OutputFile(target, target.name, f"{name} z nowym tłem")],
    )


class EraseInput(ToolInput):
    file_id: str = Field(description="Obraz, z którego należy usunąć obiekt.")
    mask_file_id: str | None = Field(
        None, description="Maska: biel = obszar do usunięcia, czerń = bez zmian."
    )
    regions: list[list[float]] = Field(
        default_factory=list,
        max_length=50,
        description="Albo prostokąty do usunięcia jako ułamki wymiarów [x, y, szerokość, wysokość] (0–1).",
    )
    method: Literal["telea", "ns"] = Field("telea", description="Algorytm odtwarzania (telea zwykle lepszy).")
    radius: int = Field(9, ge=1, le=50, description="Promień odtwarzania otoczenia w pikselach.")


@registry.register(
    "erase_objects",
    """Gumka: usuwa ze zdjęcia wskazane obiekty (napis, znak wodny, przewód, przypadkową osobę)
i wypełnia miejsce tłem z otoczenia (inpainting OpenCV). Obszar wskazuje maska albo prostokąty.""",
    EraseInput,
)
def erase_objects(ctx: ToolContext, args: EraseInput) -> ToolResult:
    name, image = _load(ctx, args.file_id)
    if args.mask_file_id:
        mask = _load(ctx, args.mask_file_id)[1]
    elif args.regions:
        for region in args.regions:
            if len(region) != 4 or not all(0 <= value <= 1 for value in region):
                raise ToolError("Każdy prostokąt to cztery ułamki 0–1: [x, y, szerokość, wysokość].")
        mask = regions_mask(image.size, [tuple(region) for region in args.regions])  # type: ignore[misc]
    else:
        raise ToolError("Wskaż obszar do usunięcia: mask_file_id albo regions.")
    ctx.progress(f"Usuwanie obiektów: {name}")
    try:
        result = erase_with_mask(image, mask, args.method, args.radius)
    except ImageOpError as error:
        raise ToolError(str(error)) from error
    target = _save(ctx, result, with_suffix(name, Path(name).suffix or ".png", "_gumka"), set())
    return ToolResult(
        {"output": target.name},
        f"Usunięto zaznaczone obiekty: {name}",
        images=[_preview(result)],
        files=[OutputFile(target, target.name, f"{name} po usunięciu obiektów")],
    )
