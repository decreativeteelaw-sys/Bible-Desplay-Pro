#!/usr/bin/env python3
"""Download redistributable Google Fonts locally for fully offline rendering.

Google Fonts are licensed under the SIL Open Font License. Proprietary Windows
fonts (Arial Rounded MT Bold, Comic Sans MS, Script MT Bold) are intentionally
not copied or redistributed; the browser uses them when installed on Windows.
"""
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
FONT_DIR = ASSETS / "fonts"
LICENSE_DIR = FONT_DIR / "licenses"
CSS_PATH = ASSETS / "fonts.css"
MANIFEST = FONT_DIR / "fonts-installed.json"
API = "https://api.github.com/repos/google/fonts/contents/{root}/{slug}"

# 20 open-licensed families to ship locally. These are independent of the
# three proprietary Microsoft font names in the selector.
FAMILIES = [
    ("Anton", "anton"),
    ("Roboto", "roboto"),
    ("Open Sans", "opensans"),
    ("Lato", "lato"),
    ("Montserrat", "montserrat"),
    ("Poppins", "poppins"),
    ("Oswald", "oswald"),
    ("Bebas Neue", "bebasneue"),
    ("League Spartan", "leaguespartan"),
    ("Playfair Display", "playfairdisplay"),
    ("Merriweather", "merriweather"),
    ("Lobster", "lobster"),
    ("Pacifico", "pacifico"),
    ("Dancing Script", "dancingscript"),
    ("Cinzel", "cinzel"),
    ("Nunito", "nunito"),
    ("Raleway", "raleway"),
    ("Inter", "inter"),
    ("Source Sans 3", "sourcesans3"),
    ("Quicksand", "quicksand"),
]


def request_bytes(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Bible-Display-Pro-Setup/1.0",
        "Accept": "application/vnd.github+json, application/json, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def get_directory(slug):
    errors = []
    for root in ("ofl", "apache", "ufl"):
        try:
            return root, json.loads(request_bytes(API.format(root=root, slug=slug)).decode("utf-8"))
        except Exception as exc:
            errors.append(f"{root}: {exc}")
    raise RuntimeError("Could not find font folder on Google Fonts: " + "; ".join(errors))


def choose_font(files):
    candidates = [x for x in files if x.get("type") == "file" and x.get("name", "").lower().endswith((".ttf", ".otf"))]
    if not candidates:
        raise RuntimeError("No TTF/OTF file found in Google Fonts family folder")
    # Prefer variable fonts; avoid italic and non-Latin subsets where possible.
    candidates.sort(key=lambda x: (
        0 if "[" in x["name"] else 1,
        1 if "italic" in x["name"].lower() else 0,
        1 if "black" in x["name"].lower() else 0,
        1 if "bold" in x["name"].lower() else 0,
        1 if "latin-ext" in x["name"].lower() else 0,
        len(x["name"]),
    ))
    return candidates[0]


def download_family(item):
    name, slug = item
    root, files = get_directory(slug)
    font_info = choose_font(files)
    ext = Path(font_info["name"]).suffix.lower()
    filename = slug + ext
    target = FONT_DIR / filename
    if not target.is_file() or target.stat().st_size < 1000:
        target.write_bytes(request_bytes(font_info["download_url"], timeout=45))
    license_file = next((f for f in files if f.get("type") == "file" and f.get("name", "").lower() in ("ofl.txt", "license.txt", "license")), None)
    if license_file:
        license_target = LICENSE_DIR / (slug + "-" + license_file["name"])
        if not license_target.exists():
            license_target.write_bytes(request_bytes(license_file["download_url"], timeout=25))
    return {
        "family": name,
        "slug": slug,
        "filename": filename,
        "variable": "[" in font_info["name"],
        "weight": "100 900" if "[" in font_info["name"] else "400",
        "source": font_info.get("html_url", font_info.get("download_url", "")),
        "license": "SIL Open Font License (see assets/fonts/licenses)",
    }


def main():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if MANIFEST.exists():
        try:
            existing = {x.get("slug"): x for x in json.loads(MANIFEST.read_text(encoding="utf-8")).get("fonts", [])}
        except Exception:
            existing = {}
    results, errors = [], []
    todo = []
    for item in FAMILIES:
        old = existing.get(item[1])
        if old and (FONT_DIR / old.get("filename", "")).is_file():
            results.append(old)
        else:
            todo.append(item)

    if todo:
        print(f"[FONTS] Downloading {len(todo)} open-licensed font families from Google Fonts on GitHub...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            future_map = {pool.submit(download_family, item): item for item in todo}
            for future in concurrent.futures.as_completed(future_map):
                item = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"[FONTS] Installed {result['family']}")
                except Exception as exc:
                    errors.append((item[0], str(exc)))
                    print(f"[FONTS] Could not download {item[0]}: {exc}")

    # Build CSS for fonts actually present. Missing downloads remain ordinary
    # system-font fallbacks and are reported clearly; the app still starts.
    css = ["/* Generated by setup_fonts.py. Open-licensed font files are stored locally. */"]
    for family, slug in FAMILIES:
        info = next((x for x in results if x.get("slug") == slug), None)
        if not info:
            continue
        file_path = FONT_DIR / info["filename"]
        if not file_path.is_file() or file_path.stat().st_size < 1000:
            continue
        family_escaped = family.replace("\\", "\\\\").replace("'", "\\'")
        weight = info.get("weight", "400")
        css.append("@font-face{font-family:'%s';src:url('fonts/%s') format('%s');font-style:normal;font-weight:%s;font-display:swap}" % (
            family_escaped, info["filename"], "truetype" if file_path.suffix.lower() == ".ttf" else "opentype", weight))
    CSS_PATH.write_text("\n".join(css) + "\n", encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://github.com/google/fonts",
        "fonts": sorted(results, key=lambda x: x.get("family", "")),
        "missing": [{"family": name, "reason": why} for name, why in errors],
        "note": "Arial Rounded MT Bold, Comic Sans MS, and Script MT Bold are proprietary/system fonts and are not redistributed.",
    }, indent=2), encoding="utf-8")
    print(f"[FONTS] Local font stylesheet written: {CSS_PATH}")
    print(f"[FONTS] Available locally: {sum(1 for x in results if (FONT_DIR / x.get('filename','')).is_file())}/{len(FAMILIES)} families")
    if errors:
        print("[FONTS] Some downloads failed. The app can still run; run setup_fonts.py again when online to retry.")
    else:
        print("[FONTS] All 20 open-licensed font families are ready for offline use.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFont setup cancelled. The app can still use installed system fonts.")
        sys.exit(1)
