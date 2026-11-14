#!/usr/bin/env python3
"""Validate Bible Display Pro's local KJV database without changing it."""
import json, sys
from pathlib import Path
p = Path(__file__).resolve().parent / 'data' / 'kjv.json'
if not p.is_file():
    print(f'MISSING: {p}')
    print('Copy a complete KJV JSON database to data\\kjv.json, or run setup_kjv.py with internet access.')
    sys.exit(2)
try:
    raw = json.loads(p.read_text(encoding='utf-8'))
except Exception as e:
    print(f'INVALID JSON: {e}')
    sys.exit(3)
books = raw.get('books', []) if isinstance(raw, dict) else []
chapters = verses = 0
for book in books:
    chs = book.get('chapters', {}) if isinstance(book, dict) else {}
    if isinstance(chs, list):
        chapters += len(chs)
        for ch in chs:
            vs = ch.get('verses', []) if isinstance(ch, dict) else []
            verses += len(vs) if isinstance(vs, (list, dict)) else 0
    elif isinstance(chs, dict):
        chapters += len(chs)
        for ch in chs.values():
            if isinstance(ch, dict) and 'verses' in ch:
                ch = ch['verses']
            verses += len(ch) if isinstance(ch, (list, dict)) else 0
print(f'File: {p}\nSize: {p.stat().st_size:,} bytes\nBooks: {len(books)}\nChapters: {chapters:,}\nVerses: {verses:,}')
if len(books) != 66 or chapters != 1189 or verses != 31102:
    print('VALIDATION FAILED: expected 66 books, 1,189 chapters, 31,102 verses.')
    sys.exit(4)
print('VALIDATION PASSED: full KJV database is ready for offline use.')
