#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx",
# ]
# ///
"""
Generate the Seti icon assets and Swift mapping for CotEditor.

Sources (both MIT):
- https://github.com/jesseweed/seti-ui           (SVG artwork)
- https://github.com/microsoft/vscode            (extensions/theme-seti JSON mapping)

Outputs:
- CotEditor/Resources/Assets.xcassets/Icons/Seti/<name>.imageset/  (SVG template image)
- CotEditor/Sources/Models/SetiIconMap.swift                        (lookup tables + colors)

Re-run to sync with upstream; the script is idempotent.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "CotEditor/Resources/Assets.xcassets/Icons/Seti"
SWIFT_OUT = REPO_ROOT / "CotEditor/Sources/Models/SetiIconMap.swift"

THEME_JSON_URL = (
    "https://raw.githubusercontent.com/microsoft/vscode/main/"
    "extensions/theme-seti/icons/vs-seti-icon-theme.json"
)
SETI_ICONS_API = "https://api.github.com/repos/jesseweed/seti-ui/contents/icons"
SETI_ICON_RAW = "https://raw.githubusercontent.com/jesseweed/seti-ui/master/icons/{name}"


def fetch_theme() -> dict:
    r = httpx.get(THEME_JSON_URL, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_svg_inventory(client: httpx.Client) -> set[str]:
    r = client.get(SETI_ICONS_API, timeout=30)
    r.raise_for_status()
    return {e["name"] for e in r.json() if e["name"].endswith(".svg")}


# VS Code's `fileExtensions` intentionally omits extensions that its runtime
# language detection handles via `languageIds`. CotEditor has no such runtime
# detection, so we fold these common extensions into `fileExtensions` ourselves.
# Keep this list conservative — only widely-agreed-upon extension↔language pairs.
EXTRA_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    "md": "markdown",
    "markdown": "markdown",
    "mdx": "markdown",
    "py": "python",
    "pyi": "python",
    "pyw": "python",
    "js": "javascript",
    "cjs": "javascript",
    "mjs": "javascript",
    "ts": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    "jsx": "javascriptreact",
    "tsx": "typescriptreact",
    "yml": "yaml",
    "yaml": "yaml",
    "sh": "shellscript",
    "bash": "shellscript",
    "zsh": "shellscript",
    "fish": "shellscript",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "rb": "ruby",
    "rake": "ruby",
    "gemspec": "ruby",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "hh": "cpp",
    "c": "c",
    "h": "c",
    "cs": "csharp",
    "m": "objective-c",
    "mm": "objective-cpp",
    "php": "php",
    "pl": "perl",
    "pm": "perl",
    "lua": "lua",
    "jl": "julia",
    "scala": "scala",
    "sc": "scala",
    "clj": "clojure",
    "cljs": "clojure",
    "cljc": "clojure",
    "edn": "clojure",
    "dart": "dart",
    "groovy": "groovy",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "less": "less",
    "xml": "xml",
    "xaml": "xml",
    "json": "json",
    "jsonc": "jsonc",
    "jsonl": "jsonl",
    "vue": "vue",
    "svelte": "svelte",
    "tex": "latex",
    "latex": "latex",
    "coffee": "coffeescript",
    "sql": "sql",
    "bat": "bat",
    "cmd": "bat",
    "ps1": "powershell",
    "psm1": "powershell",
    "makefile": "makefile",
    "mk": "makefile",
    "dockerfile": "dockerfile",
    "r": "r",
    "elm": "elm",
    "hs": "haskell",
    "lhs": "haskell",
    "fs": "fsharp",
    "fsx": "fsharp",
    "fsi": "fsharp",
    "ml": "ocaml",
    "mli": "ocaml",
    "ex": "elixir",
    "exs": "elixir",
    "nim": "nim",
    "cr": "crystal",
    "zig": "zig",
    "v": "verilog",
    "vhd": "vhdl",
    "wasm": "wasm",
    "wat": "wat",
    "graphql": "graphql",
    "gql": "graphql",
}


def resolve_svg_name(icon_key: str, inventory: set[str]) -> str | None:
    """Map a VS Code iconDefinition key ('_cpp_1') to a seti-ui SVG file ('cpp.svg')."""
    assert icon_key.startswith("_")
    stem = icon_key[1:]  # drop the leading underscore
    if stem.endswith("_light"):
        stem = stem[: -len("_light")]
    # exact match first
    if f"{stem}.svg" in inventory:
        return f"{stem}.svg"
    # strip a trailing _<number> suffix (e.g. cpp_1 -> cpp)
    trimmed = re.sub(r"_\d+$", "", stem)
    if trimmed != stem and f"{trimmed}.svg" in inventory:
        return f"{trimmed}.svg"
    # Seti uses hyphenated names (c-sharp, f-sharp); try swapping underscores
    alt = stem.replace("_", "-")
    if f"{alt}.svg" in inventory:
        return f"{alt}.svg"
    return None


CONTENTS_JSON_TEMPLATE = {
    "images": [
        {
            "filename": "",   # filled in per asset
            "idiom": "universal",
        }
    ],
    "info": {
        "author": "xcode",
        "version": 1,
    },
    "properties": {
        "preserves-vector-representation": True,
        "template-rendering-intent": "template",
    },
}


def write_asset(asset_name: str, svg_bytes: bytes) -> None:
    """Write one imageset under Assets.xcassets/Icons/Seti/<asset_name>.imageset/."""
    dir_path = ASSETS_DIR / f"{asset_name}.imageset"
    dir_path.mkdir(parents=True, exist_ok=True)
    svg_path = dir_path / f"{asset_name}.svg"
    svg_path.write_bytes(svg_bytes)
    contents = {
        **CONTENTS_JSON_TEMPLATE,
        "images": [{"filename": f"{asset_name}.svg", "idiom": "universal"}],
    }
    (dir_path / "Contents.json").write_text(
        json.dumps(contents, indent=2) + "\n", encoding="utf-8"
    )


def write_group_contents() -> None:
    """Make the Seti/ folder a namespaced asset group."""
    group_contents = {
        "info": {"author": "xcode", "version": 1},
        "properties": {"provides-namespace": True},
    }
    (ASSETS_DIR / "Contents.json").write_text(
        json.dumps(group_contents, indent=2) + "\n", encoding="utf-8"
    )


def hex_to_rgb_literal(h: str) -> str:
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return f"(r: {r:.4f}, g: {g:.4f}, b: {b:.4f})"


def emit_swift_map(
    asset_names: dict[str, str],            # iconKey -> asset basename (e.g. "_cpp" -> "cpp")
    colors_dark: dict[str, str],            # iconKey -> "#rrggbb"
    colors_light: dict[str, str],           # iconKey -> "#rrggbb"
    file_extensions: dict[str, str],        # ext -> iconKey
    file_names: dict[str, str],             # name -> iconKey
    language_ids: dict[str, str],           # langId -> iconKey
    default_file: str,
) -> None:
    lines: list[str] = []
    ap = lines.append
    ap("//")
    ap("//  SetiIconMap.swift")
    ap("//")
    ap("//  CotEditor")
    ap("//  https://coteditor.com")
    ap("//")
    ap("//  GENERATED FILE — do not edit by hand.")
    ap("//  Regenerate via Scripts/generate_seti_icons.py")
    ap("//")
    ap("//  Source data (both MIT):")
    ap("//    - https://github.com/microsoft/vscode  (theme-seti mapping)")
    ap("//    - https://github.com/jesseweed/seti-ui (SVG artwork)")
    ap("//")
    ap("")
    ap("import AppKit")
    ap("")
    ap("enum SetiIconMap {")
    ap("")
    ap("    typealias RGB = (r: Double, g: Double, b: Double)")
    ap("")
    ap(f"    static let defaultFile = \"{asset_names[default_file]}\"")
    ap(f"    static let defaultFolder = \"folder\"")
    ap("")

    # iconKey -> asset name
    ap("    /// VS Code icon-definition key (e.g. `_cpp`) → asset catalog name (e.g. `cpp`).")
    ap("    static let assetNames: [String: String] = [")
    for key in sorted(asset_names):
        ap(f"        \"{key}\": \"{asset_names[key]}\",")
    ap("    ]")
    ap("")

    # dark palette
    ap("    /// Icon-key → sRGB triple for dark appearance (Seti's primary palette).")
    ap("    static let darkColors: [String: RGB] = [")
    for key in sorted(colors_dark):
        ap(f"        \"{key}\": {hex_to_rgb_literal(colors_dark[key])},")
    ap("    ]")
    ap("")

    # light palette
    ap("    /// Icon-key → sRGB triple for light appearance (Seti's light overrides).")
    ap("    static let lightColors: [String: RGB] = [")
    for key in sorted(colors_light):
        ap(f"        \"{key}\": {hex_to_rgb_literal(colors_light[key])},")
    ap("    ]")
    ap("")

    # mappings
    def emit_table(name: str, table: dict[str, str]) -> None:
        ap(f"    static let {name}: [String: String] = [")
        for k in sorted(table):
            ap(f"        \"{k}\": \"{table[k]}\",")
        ap("    ]")
        ap("")

    emit_table("fileExtensions", file_extensions)
    emit_table("fileNames", file_names)
    emit_table("languageIds", language_ids)

    ap("}")
    ap("")

    SWIFT_OUT.parent.mkdir(parents=True, exist_ok=True)
    SWIFT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("Fetching theme JSON…", file=sys.stderr)
    theme = fetch_theme()

    with httpx.Client(headers={"User-Agent": "coteditor-seti-gen"}) as client:
        print("Listing seti-ui icons…", file=sys.stderr)
        inventory = fetch_svg_inventory(client)
        print(f"  {len(inventory)} SVGs available", file=sys.stderr)

        # ---- Resolve icon defs to SVG files + colors ----
        icon_defs = theme["iconDefinitions"]

        # VS Code ships paired icon defs: `_foo` (primary) and `_foo_light` (light
        # appearance override). We walk the primary ones and pair them up.
        dark_keys = [k for k in icon_defs if not k.endswith("_light")]

        # Resolve each dark icon key to an SVG name + pull its color.
        asset_names: dict[str, str] = {}          # iconKey -> asset basename
        colors_dark: dict[str, str] = {}
        colors_light: dict[str, str] = {}
        unresolved: list[str] = []

        DEFAULT_COLOR = "#cccccc"
        for key in dark_keys:
            svg_file = resolve_svg_name(key, inventory)
            if svg_file is None:
                unresolved.append(key)
                continue
            asset_names[key] = svg_file.removesuffix(".svg")
            colors_dark[key] = icon_defs[key].get("fontColor", DEFAULT_COLOR)
            light_key = f"{key}_light"
            colors_light[key] = icon_defs.get(light_key, {}).get(
                "fontColor", colors_dark[key]
            )

        if unresolved:
            print(
                f"warning: {len(unresolved)} icon keys have no matching SVG and "
                f"will fall back to default: {unresolved[:10]}{'…' if len(unresolved) > 10 else ''}",
                file=sys.stderr,
            )

        # The default file icon must be downloadable too.
        default_file_key = theme["file"]
        if default_file_key not in asset_names:
            print(f"fatal: default file icon '{default_file_key}' missing from inventory", file=sys.stderr)
            return 1
        # The theme doesn't define a folder icon — use jesseweed's generic folder.svg.
        if "folder.svg" not in inventory:
            print("fatal: folder.svg missing from jesseweed/seti-ui inventory", file=sys.stderr)
            return 2

        # ---- Download SVGs & write asset catalog ----
        # Always include folder.svg even though no iconDef points at it.
        svgs_to_download = {asset_names[k] + ".svg" for k in asset_names}
        svgs_to_download.add("folder.svg")
        svgs_to_download.add("folder.svg")  # defensive

        # Wipe any stale assets so removed upstream icons don't linger.
        if ASSETS_DIR.exists():
            for child in ASSETS_DIR.iterdir():
                if child.is_dir() and child.suffix == ".imageset":
                    for f in child.iterdir():
                        f.unlink()
                    child.rmdir()
                elif child.is_file():
                    child.unlink()

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        write_group_contents()

        print(f"Downloading {len(svgs_to_download)} SVGs…", file=sys.stderr)
        for svg_name in sorted(svgs_to_download):
            url = SETI_ICON_RAW.format(name=svg_name)
            r = client.get(url, timeout=30)
            if r.status_code != 200:
                print(f"  skip {svg_name}: HTTP {r.status_code}", file=sys.stderr)
                continue
            asset = svg_name.removesuffix(".svg")
            write_asset(asset, r.content)
        print("  done.", file=sys.stderr)

        # ---- Build lookup tables: drop entries whose icon key has no SVG ----
        valid_keys = set(asset_names)

        def filter_map(src: dict[str, str]) -> dict[str, str]:
            out: dict[str, str] = {}
            for k, v in src.items():
                if v in valid_keys:
                    out[k] = v
                else:
                    # Fall back silently to _default if configured; otherwise drop.
                    pass
            return out

        file_extensions = filter_map(theme.get("fileExtensions", {}))
        file_names = filter_map(theme.get("fileNames", {}))
        language_ids = filter_map(theme.get("languageIds", {}))

        # Fold common extensions from languageIds into fileExtensions so CotEditor
        # gets proper icons for files that VS Code resolves via language detection.
        for ext, lang_id in EXTRA_EXTENSION_TO_LANGUAGE.items():
            if ext in file_extensions:
                continue  # never clobber an explicit theme mapping
            icon_key = language_ids.get(lang_id)
            if icon_key is not None:
                file_extensions[ext] = icon_key

        # ---- Emit Swift ----
        emit_swift_map(
            asset_names=asset_names,
            colors_dark=colors_dark,
            colors_light=colors_light,
            file_extensions=file_extensions,
            file_names=file_names,
            language_ids=language_ids,
            default_file=default_file_key,
        )

        print(f"Wrote {SWIFT_OUT.relative_to(REPO_ROOT)}", file=sys.stderr)
        print(
            f"  assets: {len(asset_names)}  ext: {len(file_extensions)}  "
            f"names: {len(file_names)}  langs: {len(language_ids)}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
