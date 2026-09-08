from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def likely_headings(text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) > 120:
            continue
        if re.match(r"^(\d+(\.\d+)*\.?|Chapter \d+|CHAPTER \d+|Appendix [A-Z])\s+", line):
            headings.append(line)
        elif line.isupper() and len(line.split()) <= 12:
            headings.append(line)
    seen: set[str] = set()
    unique: list[str] = []
    for heading in headings:
        if heading not in seen:
            seen.add(heading)
            unique.append(heading)
    return unique[:120]


def extract_pdf(path: Path, output_dir: Path) -> dict:
    with pdfplumber.open(path) as pdf:
        pages = []
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            pages.append(f"\n\n===== PAGE {i} =====\n{page_text}")
        text = normalize("".join(pages))

    output_path = output_dir / f"{path.stem}.txt"
    output_path.write_text(text, encoding="utf-8")
    return {
        "file": str(path),
        "text_file": str(output_path),
        "characters": len(text),
        "headings": likely_headings(text),
        "preview": text[:2500],
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: extract_pdfs.py OUTPUT_DIR PDF...")
    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [extract_pdf(Path(arg), output_dir) for arg in sys.argv[2:]]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
