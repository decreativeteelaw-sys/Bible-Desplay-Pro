#!/usr/bin/env python3
"""One-time KJV installer. Downloads and stores the complete Bible locally."""
import json, urllib.request, urllib.error, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "kjv.json"

OSIS_NAMES = {
    'Gen': 'Genesis',
    'Exod': 'Exodus',
    'Lev': 'Leviticus',
    'Num': 'Numbers',
    'Deut': 'Deuteronomy',
    'Josh': 'Joshua',
    'Judg': 'Judges',
    'Ruth': 'Ruth',
    '1Sam': '1 Samuel',
    '2Sam': '2 Samuel',
    '1Kgs': '1 Kings',
    '2Kgs': '2 Kings',
    '1Chr': '1 Chronicles',
    '2Chr': '2 Chronicles',
    'Ezra': 'Ezra',
    'Neh': 'Nehemiah',
    'Esth': 'Esther',
    'Job': 'Job',
    'Ps': 'Psalms',
    'Prov': 'Proverbs',
    'Eccl': 'Ecclesiastes',
    'Song': 'Song of Solomon',
    'Isa': 'Isaiah',
    'Jer': 'Jeremiah',
    'Lam': 'Lamentations',
    'Ezek': 'Ezekiel',
    'Dan': 'Daniel',
    'Hos': 'Hosea',
    'Joel': 'Joel',
    'Amos': 'Amos',
    'Obad': 'Obadiah',
    'Jonah': 'Jonah',
    'Mic': 'Micah',
    'Nah': 'Nahum',
    'Hab': 'Habakkuk',
    'Zeph': 'Zephaniah',
    'Hag': 'Haggai',
    'Zech': 'Zechariah',
    'Mal': 'Malachi',
    'Matt': 'Matthew',
    'Mark': 'Mark',
    'Luke': 'Luke',
    'John': 'John',
    'Acts': 'Acts',
    'Rom': 'Romans',
    '1Cor': '1 Corinthians',
    '2Cor': '2 Corinthians',
    'Gal': 'Galatians',
    'Eph': 'Ephesians',
    'Phil': 'Philippians',
    'Col': 'Colossians',
    '1Thess': '1 Thessalonians',
    '2Thess': '2 Thessalonians',
    '1Tim': '1 Timothy',
    '2Tim': '2 Timothy',
    'Titus': 'Titus',
    'Phlm': 'Philemon',
    'Heb': 'Hebrews',
    'Jas': 'James',
    '1Pet': '1 Peter',
    '2Pet': '2 Peter',
    '1John': '1 John',
    '2John': '2 John',
    '3John': '3 John',
    'Jude': 'Jude',
    'Rev': 'Revelation'
}

SOURCES = [
    ("Midvash bible-data (public-domain KJV)",
     "https://raw.githubusercontent.com/midvash/bible-data/main/versions/en/kjv/kjv.json"),
    ("Midvash GitHub raw mirror",
     "https://github.com/midvash/bible-data/raw/refs/heads/main/versions/en/kjv/kjv.json"),
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Bible-Display-Pro/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))

def normalize(raw):
    books = raw.get("books", [])
    if len(books) != 66:
        raise ValueError(f"Expected 66 Bible books; found {len(books)}.")
    normalized, total, chapters_total = [], 0, 0
    for b in books:
        name = b.get("name") or b.get("book")
        name = OSIS_NAMES.get(name, name)
        if not name:
            raise ValueError("A Bible book is missing its name.")
        chapters = b.get("chapters", {})
        out = {}
        if isinstance(chapters, list):
            for i, chapter in enumerate(chapters, 1):
                chapter_no = str(chapter.get("chapter", i))
                verses = chapter.get("verses", [])
                out[chapter_no] = {}
                for j, verse in enumerate(verses, 1):
                    text = verse.get("text", "")
                    if isinstance(text, dict):
                        text = text.get("text", "")
                    out[chapter_no][str(verse.get("verse", j))] = str(text)
        elif isinstance(chapters, dict):
            for chapter_no, verses in chapters.items():
                if isinstance(verses, list):
                    out[str(chapter_no)] = {
                        str(v.get("verse", i)): str(v.get("text", ""))
                        for i, v in enumerate(verses, 1)
                    }
                else:
                    out[str(chapter_no)] = {str(vno): str(text) for vno, text in verses.items()}
        else:
            raise ValueError(f"Unexpected chapter structure in {name}.")
        if not out or any(not verses for verses in out.values()):
            raise ValueError(f"Missing chapter or verse data in {name}.")
        chapters_total += len(out)
        total += sum(len(verses) for verses in out.values())
        normalized.append({"name": name, "chapters": out})
    if chapters_total != 1189:
        raise ValueError(f"Expected 1,189 chapters; found {chapters_total}.")
    if total != 31102:
        raise ValueError(f"Expected 31,102 verses; found {total}.")
    return {
        "translation": "King James Version",
        "abbreviation": "KJV",
        "source": "midvash/bible-data",
        "license": "Public domain",
        "books": normalized
    }, chapters_total, total

def main():
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
            if len(existing.get("books", [])) == 66:
                print(f"KJV database already exists at {OUT}")
                print("Run this installer again only if you want to replace it.")
                return
        except Exception:
            pass
    errors = []
    for label, url in SOURCES:
        print(f"Trying source: {label}")
        try:
            raw = fetch(url)
            result, chapters, verses = normalize(raw)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            temp = OUT.with_suffix(".json.tmp")
            temp.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            temp.replace(OUT)
            print("\\nKJV installation successful.")
            print(f"Validated: {len(result['books'])} books, {chapters:,} chapters, {verses:,} verses.")
            print(f"Saved locally to: {OUT}")
            print("The Bible is now available offline; no internet is needed for everyday use.")
            return
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            print(f"Source failed: {exc}")
    print("\\nCould not install the KJV database.")
    for err in errors:
        print(" - " + err)
    print("Check your internet connection and run setup_kjv.py again.")
    print("The app itself uses no paid services or Python packages.")
    input("Press Enter to close...")
    sys.exit(1)

if __name__ == "__main__":
    main()
