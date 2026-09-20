"""Buduje dist/tokens.css ze źródłowych plików tokenów (format W3C Design Tokens).

Pliki *.json w tym katalogu są jedynym źródłem prawdy; tokens.css jest wynikiem
i nie podlega ręcznej edycji. Motyw ciemny (domyślny w aplikacji) włącza klasa .dark
na <html>, zgodnie z frontend/src/theme.ts. Uruchomienie: python3 design-tokens/build.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
SOURCES = ["colors", "typography", "spacing", "radius", "shadows", "animation", "icons", "layout", "effects"]
REF = re.compile(r"\{([^}]+)\}")


def load() -> dict:
    merged: dict = {}
    for name in SOURCES:
        data = json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
        for key, value in data.items():
            if not key.startswith("$"):
                merged[key] = value
    return merged


def flatten(node: dict, path: tuple = ()) -> dict:
    out = {}
    if "$value" in node:
        out[path] = node
        return out
    for key, value in node.items():
        if not key.startswith("$") and isinstance(value, dict):
            out.update(flatten(value, path + (key,)))
    return out


def var_name(path: tuple) -> str:
    return "--" + "-".join(path).replace(".", "-")


def css_value(token: dict, tokens: dict) -> str:
    value, kind = token["$value"], token["$type"]

    def resolve(ref: str) -> str:
        return f"var({var_name(tuple(ref.split('.')))})"

    if isinstance(value, str) and REF.fullmatch(value):
        return resolve(REF.fullmatch(value).group(1))
    if kind == "fontFamily":
        return ", ".join(f'"{f}"' if " " in f else f for f in value)
    if kind == "cubicBezier":
        return "cubic-bezier({})".format(", ".join(str(v) for v in value))
    if kind == "shadow":
        layers = []
        for layer in value:
            inset = "inset " if layer.get("inset") else ""
            layers.append(f"{inset}{layer['offsetX']} {layer['offsetY']} {layer['blur']} {layer['spread']} {layer['color']}")
        return ", ".join(layers)
    if kind == "gradient":
        stops = ", ".join(f"{resolve(REF.fullmatch(s['color']).group(1))} {s['position'] * 100:g}%" for s in value)
        return f"linear-gradient(135deg, {stops})"
    if kind == "typography":
        v = {k: resolve(REF.fullmatch(x).group(1)) for k, x in value.items()}
        return f"{v['fontWeight']} {v['fontSize']}/{v['lineHeight']} {v['fontFamily']}"
    return str(value)


def build() -> str:
    tokens = flatten(load())
    base, dark, light, shadow_dark, shadow_light, type_styles = [], [], [], [], [], []
    for path, token in sorted(tokens.items()):
        if token["$type"] == "object":
            base.extend(f"  {var_name(path + (k,))}: {v};" for k, v in token["$value"].items())
            continue
        value = css_value(token, tokens)
        if path[:2] == ("color", "dark"):
            dark.append(f"  --{path[2]}: {value};")
        elif path[:2] == ("color", "light"):
            light.append(f"  --{path[2]}: {value};")
        elif path[:2] == ("shadow", "dark"):
            shadow_dark.append(f"  --shadow-{path[2]}: {value};")
        elif path[:2] == ("shadow", "light"):
            shadow_light.append(f"  --shadow-{path[2]}: {value};")
        elif path[0] == "typography":
            type_styles.append(f"  --text-style-{path[1]}: {value};")
            spacing = token["$value"]["letterSpacing"]
            type_styles.append(f"  --text-style-{path[1]}-tracking: var({var_name(tuple(REF.fullmatch(spacing).group(1).split('.')))});")
        else:
            base.append(f"  {var_name(path)}: {value};")
    head = "/* Wygenerowano z design-tokens/*.json poleceniem python3 design-tokens/build.py. Nie edytować ręcznie. */\n"
    return (
        head
        + ":root {\n" + "\n".join(base + type_styles) + "\n}\n\n"
        + ":root {\n  color-scheme: light;\n" + "\n".join(light + shadow_light) + "\n}\n\n"
        + ".dark {\n  color-scheme: dark;\n" + "\n".join(dark + shadow_dark) + "\n}\n"
    )


if __name__ == "__main__":
    out = ROOT / "dist" / "tokens.css"
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"{out} ({out.stat().st_size} B)")
