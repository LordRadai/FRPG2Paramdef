#!/usr/bin/env python3
"""
translate_paramdef.py

Translates Japanese <DisplayName> fields in PARAMDEF XML files using
Google Translate (unofficial endpoint — no API key or account needed).
No external dependencies — uses Python stdlib only.

Usage:
    # Translate a single file
    python translate_paramdef.py input.xml output.xml

    # Translate all XML files in a directory
    python translate_paramdef.py --dir ./paramdefs ./paramdefs_translated

    # Overwrite files in-place
    python translate_paramdef.py --dir ./paramdefs --inplace

    # Verbose output (print each translation)
    python translate_paramdef.py input.xml output.xml -v
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BATCH_SIZE  = 30    # texts per request (keep low to avoid hitting URL length limits)
DELAY       = 0.5   # seconds between requests (be polite to Google)
SRC_LANG    = "ja"
DST_LANG    = "en"
# ──────────────────────────────────────────────────────────────────────────────

GT_URL = "https://translate.googleapis.com/translate_a/single"


def google_translate_batch(texts: list[str]) -> list[str]:
    """
    Translate a list of strings from Japanese to English via the
    unofficial Google Translate endpoint (no key required).
    """
    # Join with a rare delimiter so we send one request per batch
    # but can still split the result reliably.
    # Sending individual 'q' params is the most reliable approach.
    params = [
        ("client", "gtx"),
        ("sl", SRC_LANG),
        ("tl", DST_LANG),
        ("dt", "t"),
    ]
    for text in texts:
        params.append(("q", text))

    url = GT_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google Translate HTTP error {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"Google Translate request failed: {exc}") from exc

    data = json.loads(raw)

    # The response is a nested list; each top-level item corresponds to a
    # sentence segment. We collect all translated pieces.
    translations = []
    for item in data[0]:
        if item and item[0]:
            translations.append(item[0].strip())

    # If Google split our texts differently than we sent them,
    # fall back to joining everything (happens rarely with single-word inputs)
    if len(translations) != len(texts):
        # Try per-item fallback
        results = []
        for text in texts:
            results.append(_translate_single(text))
            time.sleep(DELAY)
        return results

    return translations


def _translate_single(text: str) -> str:
    """Translate a single string (fallback for when batch splitting fails)."""
    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": SRC_LANG,
        "tl": DST_LANG,
        "dt": "t",
        "q": text,
    })
    url = GT_URL + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(item[0] for item in data[0] if item and item[0]).strip()


def translate_tree(tree: ET.ElementTree, verbose: bool = False) -> int:
    """
    Translate all <DisplayName> elements containing Japanese text, in-place.
    Returns the number of fields translated.
    """
    all_elements = tree.findall(".//DisplayName")
    to_translate = [el for el in all_elements if el.text and not el.text.isascii()]
    if not to_translate:
        return 0

    originals = [el.text for el in to_translate]
    translated: list[str] = []

    total_batches = (len(originals) + BATCH_SIZE - 1) // BATCH_SIZE
    for i, start in enumerate(range(0, len(originals), BATCH_SIZE)):
        batch = originals[start: start + BATCH_SIZE]
        print(f"  Batch {i+1}/{total_batches} ({len(batch)} names)...")
        translated.extend(google_translate_batch(batch))
        if start + BATCH_SIZE < len(originals):
            time.sleep(DELAY)

    for el, new_text in zip(to_translate, translated):
        if verbose:
            print(f"    {el.text!r:40s}  ->  {new_text!r}")
        el.text = new_text

    return len(to_translate)


def process_file(src: Path, dst: Path, verbose: bool = False) -> None:
    """Parse, translate, and write a single XML file."""
    print(f"\nProcessing: {src}")
    tree = ET.parse(src)

    count = translate_tree(tree, verbose=verbose)
    print(f"  Translated {count} DisplayName(s)")

    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    print(f"  Saved -> {dst}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate Japanese <DisplayName> fields in PARAMDEF XML files (Google Translate, no key)."
    )
    parser.add_argument("input",             help="Source file or directory")
    parser.add_argument("output", nargs="?", help="Destination file or directory (omit with --inplace)")
    parser.add_argument("--dir",     action="store_true", help="Treat input as a directory")
    parser.add_argument("--inplace", action="store_true", help="Overwrite source files")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each translation")
    args = parser.parse_args()

    src_path = Path(args.input)

    # ── Single file ───────────────────────────────────────────────────────────
    if not args.dir and src_path.is_file():
        if args.inplace:
            dst_path = src_path
        elif args.output:
            dst_path = Path(args.output)
        else:
            parser.error("Provide an output path or use --inplace.")
        process_file(src_path, dst_path, verbose=args.verbose)
        print("\nDone.")
        return

    # ── Directory ─────────────────────────────────────────────────────────────
    if not src_path.is_dir():
        sys.exit(f"Error: '{src_path}' is not a file or directory.")

    xml_files = sorted(src_path.rglob("*.xml"))
    if not xml_files:
        sys.exit(f"No XML files found in '{src_path}'.")

    print(f"Found {len(xml_files)} XML file(s) in '{src_path}'")

    for xml_file in xml_files:
        relative = xml_file.relative_to(src_path)
        if args.inplace:
            dst = xml_file
        elif args.output:
            dst = Path(args.output) / relative
        else:
            parser.error("Provide an output directory or use --inplace.")

        try:
            process_file(xml_file, dst, verbose=args.verbose)
        except Exception as exc:
            print(f"  ERROR processing {xml_file}: {exc}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()