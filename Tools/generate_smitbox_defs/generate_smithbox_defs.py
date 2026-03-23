#!/usr/bin/env python3
"""
split_paramdef.py

Splits a PARAMDEF XML into two separate files:

  1. <n>def  - lean struct definition, one self-closing <Field Def="..."/> per field
  2. <n>meta - metadata (AltName from DisplayName, ProjectEnum from Enum, Refs)

Optionally accepts a config.txt mapping enum names to Refs values.
When a field's <Enum> matches a key in the config, ProjectEnum is replaced by Refs.

config.txt format (one rule per line, # lines are comments):
    BULLET_PARAM_ENUM : BulletParam, EnemyBulletParam, SystemBulletParam
    BOOL_TYPE         : SomeRef

Usage:
    # Single file
    python split_paramdef.py input.xml --def ./defs --meta ./meta

    # Single file with enum-to-refs config
    python split_paramdef.py input.xml --def ./defs --meta ./meta --config config.txt

    # Whole folder
    python split_paramdef.py --dir ./paramdefs --def ./defs --meta ./meta --config config.txt
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# -- Enum-to-Refs config -------------------------------------------------------

def load_enum_config(path: Path) -> dict[str, str]:
    """
    Parse a config file mapping enum names to Refs strings.

    Format (one rule per line):
        ENUM_NAME : Ref1, Ref2, Ref3
        # comment lines and blank lines are ignored

    Returns {ENUM_NAME: "Ref1, Ref2, Ref3"}.
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


# -- Helpers -------------------------------------------------------------------

def indent(elem: ET.Element, level: int = 0) -> None:
    """Add pretty-print indentation in-place (stdlib ET has no built-in pretty print before 3.9)."""
    pad = "\n" + "    " * level
    if len(elem):
        elem.text = pad + "    "
        for child in elem:
            indent(child, level + 1)
        child.tail = pad  # last child
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


# -- Core split logic ----------------------------------------------------------

def split(src: Path, def_dst: Path, meta_dst: Path, enum_config: dict | None = None) -> None:
    tree = ET.parse(src)
    root = tree.getroot()

    fields_elem = root.find("Fields")
    if fields_elem is None:
        print(f"  SKIP (no <Fields> element): {src}")
        return

    param_type = (root.findtext("ParamType") or src.stem).strip()

    # 1. PARAMDEF - self-closing <Field Def="..."/> elements
    def_root = ET.Element("PARAMDEF", {"XmlVersion": root.get("XmlVersion", "0")})
    ET.SubElement(def_root, "ParamType").text    = param_type
    ET.SubElement(def_root, "DataVersion").text  = root.findtext("DataVersion") or ""
    ET.SubElement(def_root, "BigEndian").text    = root.findtext("BigEndian") or "false"
    ET.SubElement(def_root, "Unicode").text      = root.findtext("Unicode") or "true"
    ET.SubElement(def_root, "FormatVersion").text = root.findtext("FormatVersion") or ""

    def_fields = ET.SubElement(def_root, "Fields")

    # 2. PARAMMETA - one child element per field inside <Field>
    meta_root  = ET.Element("PARAMMETA", {"XmlVersion": root.get("XmlVersion", "0")})
    meta_field = ET.SubElement(meta_root, "Field")

    for field in fields_elem.findall("Field"):
        def_attr = field.get("Def", "")

        # Parse Def string: "type name" or "type name = default"
        # e.g. "f32 chameleonAngle1 = 1"  -> type="f32", name="chameleonAngle1", default="1"
        #      "u8 intrudeEnable"          -> type="u8",  name="intrudeEnable",   default=None
        #      "dummy8 aReserved[3]"       -> type="dummy8", name="aReserved",    default=None
        clean_def = def_attr
        if "=" in def_attr:
            clean_def = def_attr.split("=", 1)[0].strip()

        # Strip C-style bitfield width suffix from the name token (e.g. "u8 physical:1" -> "u8 physical")
        if ":" in clean_def:
            parts = clean_def.split()
            parts[-1] = parts[-1].split(":")[0]
            clean_def = " ".join(parts)

        # PARAMDEF entry (self-closing, default stripped)
        ET.SubElement(def_fields, "Field", {"Def": clean_def})

        # PARAMMETA entry
        # Tag name is always the field name (last token of the clean def, array suffix removed).
        # e.g. "f32 chameleonAngle1 = 1" -> tag "chameleonAngle1"
        #      "u8 intrudeEnable"         -> tag "intrudeEnable"
        #      "dummy8 aReserved[3]"      -> tag "aReserved"
        tokens     = clean_def.split()
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
                    # Reserved value: emit IsBool instead of Refs or ProjectEnum
                    meta_attribs["IsBool"] = "true"
                else:
                    meta_attribs["Refs"] = val
            else:
                meta_attribs["ProjectEnum"] = enum

        # Explicit <Refs> element in the source XML always wins
        refs = field.findtext("Refs") or field.get("Refs")
        if refs and refs.strip():
            meta_attribs["Refs"] = refs.strip()

        # ET may reorder attributes; enforce the desired output order explicitly
        ATTR_ORDER = ["AltName", "Padding", "IsBool", "ProjectEnum", "Refs"]
        ordered = {k: meta_attribs[k] for k in ATTR_ORDER if k in meta_attribs}
        ordered.update({k: v for k, v in meta_attribs.items() if k not in ordered})
        ET.SubElement(meta_field, field_name, ordered)

    write_xml(def_root,  def_dst)
    write_xml(meta_root, meta_dst)
    print(f"  -> {def_dst}")
    print(f"  -> {meta_dst}")


# -- CLI -----------------------------------------------------------------------

def file_stem(src: Path) -> str:
    """Filename without extension, also strips .paramdef / .parammeta double-extensions."""
    s = src.stem
    for suffix in (".paramdef", ".parammeta"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Split PARAMDEF XML file(s) into def and meta files.\n\n"
            "Single file:\n"
            "  python split_paramdef.py input.xml --def ./defs --meta ./meta\n\n"
            "With enum-to-refs config:\n"
            "  python split_paramdef.py input.xml --def ./defs --meta ./meta --config config.txt\n\n"
            "Whole folder:\n"
            "  python split_paramdef.py --dir ./paramdefs --def ./defs --meta ./meta --config config.txt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Source file or directory")
    parser.add_argument(
        "--def", dest="def_out", required=True,
        help="Output folder for def files",
    )
    parser.add_argument(
        "--meta", dest="meta_out", required=True,
        help="Output folder for meta files",
    )
    parser.add_argument(
        "--dir", action="store_true",
        help="Treat input as a directory and process all XML files recursively",
    )
    parser.add_argument(
        "--config", dest="config", default=None, metavar="FILE",
        help="Path to config.txt mapping enum names to Refs (optional)",
    )
    args = parser.parse_args()

    src_path  = Path(args.input)
    def_root  = Path(args.def_out)
    meta_root = Path(args.meta_out)

    enum_config: dict | None = None
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_file():
            print(f"Error: config file not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)
        enum_config = load_enum_config(cfg_path)
        print(f"Loaded {len(enum_config)} enum-to-refs rule(s) from '{cfg_path}'")

    # -- Single file -----------------------------------------------------------
    if not args.dir and src_path.is_file():
        name     = file_stem(src_path)
        def_dst  = def_root  / (name + ".xml")
        meta_dst = meta_root / (name + ".xml")
        print(f"Splitting: {src_path}")
        split(src_path, def_dst, meta_dst, enum_config=enum_config)
        print("Done.")
        return

    # -- Directory -------------------------------------------------------------
    if not src_path.is_dir():
        sys.exit(f"Error: '{src_path}' is not a file or directory. Add --dir for directories.")

    xml_files = sorted(src_path.rglob("*.xml"))
    if not xml_files:
        sys.exit(f"No XML files found in '{src_path}'.")

    print(f"Found {len(xml_files)} XML file(s) in '{src_path}'")
    print(f"  paramdef  -> {def_root}")
    print(f"  parammeta -> {meta_root}\n")

    for xml_file in xml_files:
        rel_dir  = xml_file.relative_to(src_path).parent
        name     = file_stem(xml_file)
        def_dst  = def_root  / rel_dir / (name + ".xml")
        meta_dst = meta_root / rel_dir / (name + ".xml")
        print(f"Splitting: {xml_file}")
        try:
            split(xml_file, def_dst, meta_dst, enum_config=enum_config)
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()