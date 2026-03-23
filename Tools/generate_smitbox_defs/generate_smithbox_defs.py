#!/usr/bin/env python3
"""
split_paramdef.py

Splits a PARAMDEF XML into two separate files:

  1. <n>.xml (def)  - lean struct definition, one self-closing <Field Def="..."/> per field
  2. <n>.xml (meta) - metadata (AltName, Padding, IsBool, ProjectEnum/Enum, Refs)

Optionally accepts:
  --config config.txt   maps enum names to Refs values or "bool"
  --enums  enums.json   master enum definitions; exclusive enums are embedded in each
                        meta's <Enums> block using Enum="...", shared ones keep
                        ProjectEnum="..." and are written to shared_enums.json next
                        to this script.

config.txt format (one rule per line, # lines are comments):
    BULLET_PARAM_ENUM : BulletParam, EnemyBulletParam, SystemBulletParam
    BOOL_TRUEFALSE_TYPE : bool

Usage:
    python split_paramdef.py input.xml --def ./defs --meta ./meta
    python split_paramdef.py input.xml --def ./defs --meta ./meta --config config.txt --enums enums.json
    python split_paramdef.py --dir ./paramdefs --def ./defs --meta ./meta --config config.txt --enums enums.json
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


# -- Enum-to-Refs config -------------------------------------------------------

def load_enum_config(path: Path) -> dict[str, str]:
    """
    Parse a config file mapping enum names to Refs strings or "bool".

    Format (one rule per line):
        ENUM_NAME : Ref1, Ref2, Ref3
        BOOL_TYPE : bool
        # comment lines and blank lines are ignored
    """
    mapping: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            print(f"  [config] WARNING line {lineno}: no ':' separator, skipping: {raw!r}")
            continue
        enum_name, _, refs_part = line.partition(":")
        enum_name = enum_name.strip()
        refs_val  = ", ".join(r.strip() for r in refs_part.split(",") if r.strip())
        if not enum_name or not refs_val:
            print(f"  [config] WARNING line {lineno}: empty key or value, skipping: {raw!r}")
            continue
        mapping[enum_name] = refs_val
    return mapping


# -- Master enums.json ---------------------------------------------------------

def load_master_enums(path: Path) -> dict[str, dict]:
    """
    Load enums.json and return a dict keyed by enum Name.
    Each value is the raw enum object from the JSON List.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["Name"]: entry for entry in data.get("List", [])}


def collect_enum_usage(xml_files: list[Path]) -> dict[str, set[str]]:
    """
    Scan all paramdef XML files and return a dict:
        { enum_name -> set of xml file stems that reference it }
    Only counts enums from <Enum> child elements (not enums resolved to Refs/bool via config).
    """
    usage: dict[str, set[str]] = defaultdict(set)
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
        except Exception:
            continue
        for el in tree.findall(".//Enum"):
            if el.text and el.text.strip():
                usage[el.text.strip()].add(xml_file.stem)
    return usage


# -- Helpers -------------------------------------------------------------------

def indent(elem: ET.Element, level: int = 0) -> None:
    """Add pretty-print indentation in-place."""
    pad = "\n" + "    " * level
    if len(elem):
        elem.text = pad + "    "
        for child in elem:
            indent(child, level + 1)
        child.tail = pad
        elem.tail = pad
    else:
        elem.tail = pad
    if level == 0:
        elem.tail = "\n"


def write_xml(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_enum_element(enum_name: str, field_type: str, master_enums: dict) -> ET.Element | None:
    """Build an <Enum Name="..." type="..."> element from the master enums dict."""
    entry = master_enums.get(enum_name)
    if not entry:
        return None
    enum_el = ET.Element("Enum", {"Name": enum_name, "type": field_type})
    for opt in entry.get("Options", []):
        ET.SubElement(enum_el, "Option", {"Value": opt["ID"], "Name": opt["Name"]})
    return enum_el


# -- Core split logic ----------------------------------------------------------

def split(
    src: Path,
    def_dst: Path,
    meta_dst: Path,
    enum_config: dict | None = None,
    master_enums: dict | None = None,
    shared_enum_names: set[str] | None = None,
) -> None:
    tree = ET.parse(src)
    root = tree.getroot()

    fields_elem = root.find("Fields")
    if fields_elem is None:
        print(f"  SKIP (no <Fields> element): {src}")
        return

    param_type = (root.findtext("ParamType") or src.stem).strip()

    # 1. PARAMDEF - self-closing <Field Def="..."/> elements
    def_root = ET.Element("PARAMDEF", {"XmlVersion": root.get("XmlVersion", "0")})
    ET.SubElement(def_root, "ParamType").text     = param_type
    ET.SubElement(def_root, "DataVersion").text   = root.findtext("DataVersion") or ""
    ET.SubElement(def_root, "BigEndian").text     = root.findtext("BigEndian") or "false"
    ET.SubElement(def_root, "Unicode").text       = root.findtext("Unicode") or "true"
    ET.SubElement(def_root, "FormatVersion").text = root.findtext("FormatVersion") or ""
    def_fields = ET.SubElement(def_root, "Fields")

    # 2. PARAMMETA
    meta_root  = ET.Element("PARAMMETA", {"XmlVersion": root.get("XmlVersion", "0")})
    meta_field = ET.SubElement(meta_root, "Field")

    # Collect exclusive enums we need to embed, preserving first-seen order
    # { enum_name -> field_type }
    exclusive_enums_seen: dict[str, str] = {}

    for field in fields_elem.findall("Field"):
        def_attr = field.get("Def", "")

        # Strip default value
        clean_def = def_attr
        if "=" in def_attr:
            clean_def = def_attr.split("=", 1)[0].strip()

        # Drop dummy8 bitfield entries entirely (e.g. "dummy8 someName:1")
        def_tokens = clean_def.split()
        if len(def_tokens) >= 2 and def_tokens[0] == "dummy8" and ":" in def_tokens[-1]:
            continue

        # dummy8 fields must always have an array size; add [1] if missing
        def_tokens = clean_def.split()
        if len(def_tokens) >= 2 and def_tokens[0] == "dummy8" and "[" not in def_tokens[-1]:
            def_tokens[-1] += "[1]"
            clean_def = " ".join(def_tokens)

        # PARAMDEF entry (bitfield preserved)
        ET.SubElement(def_fields, "Field", {"Def": clean_def})

        # Strip bitfield suffix for meta only
        meta_def = clean_def
        if ":" in meta_def:
            parts = meta_def.split()
            parts[-1] = parts[-1].split(":")[0]
            meta_def = " ".join(parts)

        tokens     = meta_def.split()
        field_type = tokens[0] if tokens else ""
        raw_name   = tokens[-1] if tokens else "unknown"
        field_name = raw_name.split("[")[0].split(":")[0]

        meta_attribs: dict[str, str] = {}

        display = field.findtext("DisplayName")
        if display and display.strip():
            meta_attribs["AltName"] = display.strip()

        if field_type == "dummy8":
            meta_attribs["Padding"] = "true"

        enum = (field.findtext("Enum") or "").strip()
        if enum:
            if enum_config and enum in enum_config:
                val = enum_config[enum]
                if val == "bool":
                    meta_attribs["IsBool"] = "true"
                else:
                    meta_attribs["Refs"] = val
            elif master_enums is not None and shared_enum_names is not None:
                if enum in shared_enum_names:
                    # Shared across files: keep as ProjectEnum
                    meta_attribs["ProjectEnum"] = enum
                else:
                    # Exclusive to this file: embed inline
                    meta_attribs["Enum"] = enum
                    if enum not in exclusive_enums_seen:
                        exclusive_enums_seen[enum] = field_type
            else:
                meta_attribs["ProjectEnum"] = enum

        # Explicit <Refs> element in the source XML always wins
        refs = field.findtext("Refs") or field.get("Refs")
        if refs and refs.strip():
            meta_attribs["Refs"] = refs.strip()

        # Enforce attribute output order
        ATTR_ORDER = ["AltName", "Padding", "IsBool", "ProjectEnum", "Enum", "Refs"]
        ordered = {k: meta_attribs[k] for k in ATTR_ORDER if k in meta_attribs}
        ordered.update({k: v for k, v in meta_attribs.items() if k not in ordered})
        ET.SubElement(meta_field, field_name, ordered)

    # Append <Enums> block for exclusive enums
    if exclusive_enums_seen and master_enums is not None:
        enums_el = ET.SubElement(meta_root, "Enums")
        for enum_name, ftype in exclusive_enums_seen.items():
            enum_el = build_enum_element(enum_name, ftype, master_enums)
            if enum_el is not None:
                enums_el.append(enum_el)
            else:
                print(f"  [enums] WARNING: '{enum_name}' not found in master enums, skipping embed")

    write_xml(def_root,  def_dst)
    write_xml(meta_root, meta_dst)
    print(f"  -> {def_dst}")
    print(f"  -> {meta_dst}")


# -- CLI -----------------------------------------------------------------------

def file_stem(src: Path) -> str:
    return src.stem


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Split PARAMDEF XML file(s) into def and meta XML files.\n\n"
            "Single file:\n"
            "  python split_paramdef.py input.xml --def ./defs --meta ./meta\n\n"
            "With config and master enums:\n"
            "  python split_paramdef.py input.xml --def ./defs --meta ./meta --config config.txt --enums enums.json\n\n"
            "Whole folder:\n"
            "  python split_paramdef.py --dir ./paramdefs --def ./defs --meta ./meta --config config.txt --enums enums.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Source file or directory")
    parser.add_argument("--def",    dest="def_out",  required=True, help="Output folder for def XML files")
    parser.add_argument("--meta",   dest="meta_out", required=True, help="Output folder for meta XML files")
    parser.add_argument("--dir",    action="store_true", help="Treat input as a directory")
    parser.add_argument("--config", dest="config", default=None, metavar="FILE",
                        help="config.txt mapping enum names to Refs or bool (optional)")
    parser.add_argument("--enums",  dest="enums",  default=None, metavar="FILE",
                        help="enums.json master enum definitions (optional)")
    args = parser.parse_args()

    src_path  = Path(args.input)
    def_root  = Path(args.def_out)
    meta_root = Path(args.meta_out)

    enum_config: dict | None = None
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_file():
            sys.exit(f"Error: config file not found: {cfg_path}")
        enum_config = load_enum_config(cfg_path)
        print(f"Loaded {len(enum_config)} enum-to-refs rule(s) from '{cfg_path}'")

    master_enums: dict | None = None
    if args.enums:
        enums_path = Path(args.enums)
        if not enums_path.is_file():
            sys.exit(f"Error: enums file not found: {enums_path}")
        master_enums = load_master_enums(enums_path)
        print(f"Loaded {len(master_enums)} enum definition(s) from '{enums_path}'")

    # Collect all XML files to process
    if not args.dir and src_path.is_file():
        xml_files = [src_path]
    elif src_path.is_dir():
        xml_files = sorted(src_path.rglob("*.xml"))
        if not xml_files:
            sys.exit(f"No XML files found in '{src_path}'.")
    else:
        sys.exit(f"Error: '{src_path}' is not a file or directory. Add --dir for directories.")

    # Determine shared vs exclusive enums across all files
    shared_enum_names: set[str] | None = None
    if master_enums is not None:
        usage = collect_enum_usage(xml_files)
        # Filter out enums already handled by config (Refs/bool)
        if enum_config:
            usage = {k: v for k, v in usage.items() if k not in enum_config}
        shared_enum_names = {name for name, files in usage.items() if len(files) > 1}
        exclusive_count   = sum(1 for files in usage.values() if len(files) == 1)
        print(f"Enum usage: {len(shared_enum_names)} shared, {exclusive_count} exclusive")

        # Write shared_enums.json next to this script
        if shared_enum_names:
            shared_list = [
                master_enums[n] for n in sorted(shared_enum_names) if n in master_enums
            ]
            shared_path = Path(__file__).parent / "shared_enums.json"
            shared_path.write_text(
                json.dumps({"List": shared_list}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Wrote {len(shared_list)} shared enum(s) to '{shared_path}'")

    # Process files
    if len(xml_files) == 1 and not args.dir:
        name     = file_stem(xml_files[0])
        def_dst  = def_root  / (name + ".xml")
        meta_dst = meta_root / (name + ".xml")
        print(f"Splitting: {xml_files[0]}")
        split(xml_files[0], def_dst, meta_dst,
              enum_config=enum_config,
              master_enums=master_enums,
              shared_enum_names=shared_enum_names)
        print("Done.")
        return

    print(f"Found {len(xml_files)} XML file(s) in '{src_path}'")
    print(f"  def   -> {def_root}")
    print(f"  meta  -> {meta_root}\n")

    for xml_file in xml_files:
        rel_dir  = xml_file.relative_to(src_path).parent
        name     = file_stem(xml_file)
        def_dst  = def_root  / rel_dir / (name + ".xml")
        meta_dst = meta_root / rel_dir / (name + ".xml")
        print(f"Splitting: {xml_file}")
        try:
            split(xml_file, def_dst, meta_dst,
                  enum_config=enum_config,
                  master_enums=master_enums,
                  shared_enum_names=shared_enum_names)
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()