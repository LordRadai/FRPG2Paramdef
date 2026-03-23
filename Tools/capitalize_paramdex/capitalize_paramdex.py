#!/usr/bin/env python3
"""
capitalize_displaynames.py

Capitalizes the first letter of every <DisplayName> in PARAMDEF XML files.
All other characters are left untouched.

Usage:
    # Single file, in-place
    python capitalize_displaynames.py input.xml --inplace

    # Single file with explicit output
    python capitalize_displaynames.py input.xml output.xml

    # Whole folder
    python capitalize_displaynames.py --dir ./paramdefs ./paramdefs_out

    # Whole folder, in-place
    python capitalize_displaynames.py --dir ./paramdefs --inplace
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def capitalize_tree(tree: ET.ElementTree) -> int:
    """Capitalize first letter of every <DisplayName> in-place. Returns count changed."""
    count = 0
    for el in tree.findall(".//DisplayName"):
        if el.text and el.text.strip():
            t = el.text
            el.text = t[0].upper() + t[1:]
            count += 1
    return count


def process_file(src: Path, dst: Path) -> None:
    tree = ET.parse(src)
    count = capitalize_tree(tree)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    print(f"  {src} -> {dst}  ({count} changed)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capitalize first letter of <DisplayName> fields in PARAMDEF XML files."
    )
    parser.add_argument("input",          help="Source file or directory")
    parser.add_argument("output", nargs="?", help="Destination file or directory")
    parser.add_argument("--dir",     action="store_true", help="Treat input as a directory")
    parser.add_argument("--inplace", action="store_true", help="Overwrite source files")
    args = parser.parse_args()

    src_path = Path(args.input)

    # ── Single file ───────────────────────────────────────────────────────────
    if not args.dir and src_path.is_file():
        if args.inplace:
            dst = src_path
        elif args.output:
            dst = Path(args.output)
        else:
            parser.error("Provide an output path or use --inplace.")
        process_file(src_path, dst)
        return

    # ── Directory ─────────────────────────────────────────────────────────────
    if not src_path.is_dir():
        sys.exit(f"Error: '{src_path}' is not a file or directory.")

    xml_files = sorted(src_path.rglob("*.xml"))
    if not xml_files:
        sys.exit(f"No XML files found in '{src_path}'.")

    for xml_file in xml_files:
        relative = xml_file.relative_to(src_path)
        if args.inplace:
            dst = xml_file
        elif args.output:
            dst = Path(args.output) / relative
        else:
            parser.error("Provide an output directory or use --inplace.")
        try:
            process_file(xml_file, dst)
        except Exception as exc:
            print(f"  ERROR processing {xml_file}: {exc}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()