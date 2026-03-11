"""
mdloc CLI module.

Enhanced version with:

- Markdown parsing via markdown-it-py
- URL and domain detection
- Automatic state="initial" for non-translatable lines
- Precise whitespace preservation
- Clean skeleton formatting
- Robust reconstruction
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import click
import xml.etree.ElementTree as ET
from markdown_it import MarkdownIt


# ============================================================
# Constants
# ============================================================

PLACEHOLDER_PATTERN: str = "$(ID:{})"
XLIFF_NS: str = "urn:oasis:names:tc:xliff:document:2.0"

md = MarkdownIt()

URL_PATTERN = re.compile(r"https?://\S+")
DOMAIN_PATTERN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
MD_REFERENCE_PATTERN = re.compile(r"^\s*\[\d+\]:\s*")


# ============================================================
# Utility Functions
# ============================================================

def is_non_translatable(text: str) -> bool:
    """
    Return True if text contains no human translatable content.
    """
    stripped = text.strip()

    stripped = MD_REFERENCE_PATTERN.sub("", stripped)
    stripped = URL_PATTERN.sub("", stripped)
    stripped = DOMAIN_PATTERN.sub("", stripped)

    stripped = re.sub(r"[^\w]", "", stripped)

    return stripped == ""


def split_protected_parts(text: str) -> List[Tuple[bool, str]]:
    """
    Split text into (is_translatable, content) parts.
    URLs and domain names are protected.
    """

    parts: List[Tuple[bool, str]] = []

    pattern = re.compile(
        r"https?://\S+|\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b"
    )

    last = 0

    for match in pattern.finditer(text):
        start, end = match.span()

        if start > last:
            parts.append((True, text[last:start]))

        parts.append((False, match.group()))
        last = end

    if last < len(text):
        parts.append((True, text[last:]))

    return parts


# ============================================================
# Extraction Logic
# ============================================================

def extract_markdown(original_text: str) -> Tuple[str, List[Dict[str, str]]]:

    lines = original_text.splitlines()
    new_lines: List[str] = []
    units: List[Dict[str, str]] = []

    for line_number, line in enumerate(lines, start=1):

        if not line.strip():
            new_lines.append(line)
            continue

        # Entire line non-translatable → state="initial"
        if is_non_translatable(line):
            unit_id = str(uuid.uuid4())
            placeholder = PLACEHOLDER_PATTERN.format(unit_id)

            new_lines.append(placeholder)

            units.append({
                "id": unit_id,
                "source": line,
                "line": str(line_number),
                "initial": True
            })
            continue

        tokens = md.parse(line)

        new_line = ""
        contains_translatable = False

        for token in tokens:
            if token.type == "inline":
                for child in token.children:

                    if child.type == "text":
                        parts = split_protected_parts(child.content)

                        for is_translatable, content in parts:

                            if not content:
                                continue

                            if is_translatable and content.strip():
                                prefix = ""
                                text = content
                                if text.startswith(": "):
                                    prefix = ": "
                                    text = text[2:]
                                unit_id = str(uuid.uuid4())
                                placeholder = PLACEHOLDER_PATTERN.format(unit_id)
                                new_line += prefix + placeholder
                                contains_translatable = True
                                units.append({
                                    "id": unit_id,
                                    "source": text,
                                    "line": str(line_number),
                                    "initial": False
                                })
                            else:
                                new_line += content

                    else:
                        new_line += child.markup or child.content or ""

            else:
                new_line += token.markup or ""

        if not contains_translatable:
            unit_id = str(uuid.uuid4())
            placeholder = PLACEHOLDER_PATTERN.format(unit_id)

            new_lines.append(placeholder)

            units.append({
                "id": unit_id,
                "source": line,
                "line": str(line_number),
                "initial": True
            })
        else:
            new_lines.append(new_line)

    skeleton = "\n".join(new_lines)

    return skeleton, units


# ============================================================
# XLIFF Builder
# ============================================================

def build_xliff(skeleton: str, units: List[Dict[str, str]], file_id: str) -> str:

    xliff = ET.Element(
        "xliff",
        {
            "xmlns": XLIFF_NS,
            "version": "2.0",
            "srcLang": "en"
        }
    )

    file_elem = ET.SubElement(
        xliff,
        "file",
        {"id": file_id, "original": file_id}
    )

    for unit in units:

        unit_elem = ET.SubElement(file_elem, "unit", {"id": unit["id"]})

        notes_elem = ET.SubElement(unit_elem, "notes")

        note_line = ET.SubElement(notes_elem, "note", {"appliesTo": "source"})
        note_line.text = f"line: {unit['line']}"

        if unit["initial"]:
            note_initial = ET.SubElement(notes_elem, "note", {"appliesTo": "source"})
            note_initial.text = "non-translatable content preserved"

        if unit["initial"]:
            segment = ET.SubElement(unit_elem, "segment", {"state": "initial"})
        else:
            segment = ET.SubElement(unit_elem, "segment")

        source = ET.SubElement(segment, "source")
        source.text = unit["source"]

        if unit["initial"]:
            target = ET.SubElement(segment, "target")
            target.text = unit["source"]

    ET.indent(xliff, space="    ")

    xml_body = ET.tostring(xliff, encoding="unicode")

    # Insert skeleton cleanly
    file_start = xml_body.find("<file ")
    file_end = xml_body.find(">", file_start) + 1
    file_close = xml_body.rfind("</file>")

    skeleton_clean = skeleton.strip("\n")

    xml_body = (
        xml_body[:file_end]
        + "\n<skeleton>\n"
        + skeleton_clean + "\n"
        + "</skeleton>\n"
        + xml_body[file_end:file_close]
        + xml_body[file_close:]
    )

    xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'

    return xml_header + xml_body


# ============================================================
# XLIFF Parsing
# ============================================================

def parse_xliff(xliff_content: str) -> Tuple[str, Dict[str, str]]:

    ns = {"x": XLIFF_NS}
    root = ET.fromstring(xliff_content)

    skeleton_elem = root.find(".//x:skeleton", ns)
    skeleton = skeleton_elem.text if skeleton_elem is not None else ""

    translations: Dict[str, str] = {}

    for unit in root.findall(".//x:unit", ns):
        unit_id = unit.attrib["id"]

        target = unit.find(".//x:target", ns)
        source = unit.find(".//x:source", ns)

        if target is not None and target.text:
            translations[unit_id] = target.text
        elif source is not None and source.text:
            translations[unit_id] = source.text

    return skeleton or "", translations


# ============================================================
# Reconstruction
# ============================================================

def reconstruct_markdown(skeleton: str, translations: Dict[str, str]) -> str:

    result = skeleton.lstrip("\n")

    for unit_id, translated_text in translations.items():
        placeholder = PLACEHOLDER_PATTERN.format(unit_id)
        result = result.replace(placeholder, translated_text)

    return result


# ============================================================
# CLI Commands
# ============================================================

@click.group()
def cli() -> None:
    """mdloc command-line interface."""
    pass


@cli.command()
@click.argument("input_md", type=click.Path(exists=True))
@click.argument("output_xliff", type=click.Path())
def extract(input_md: str, output_xliff: str) -> None:

    click.echo(f"Generating XLIFF file {output_xliff} from {input_md}...")

    original_text = Path(input_md).read_text(encoding="utf-8-sig")

    skeleton, units = extract_markdown(original_text)

    file_id = Path(input_md).name

    xliff_content = build_xliff(skeleton, units, file_id)

    Path(output_xliff).write_text(xliff_content, encoding="utf-8")

    click.echo(
        f"Generated XLIFF file with {len(units)} units."
    )


@cli.command()
@click.argument("input_xliff", type=click.Path(exists=True))
@click.argument("output_md", type=click.Path())
def reconstruct(input_xliff: str, output_md: str) -> None:

    click.echo(f"Generating markdown file {output_md} from {input_xliff}...")

    xliff_content = Path(input_xliff).read_text(encoding="utf-8")

    skeleton, translations = parse_xliff(xliff_content)

    reconstructed = reconstruct_markdown(skeleton, translations)

    Path(output_md).write_text(reconstructed, encoding="utf-8")

    click.echo(
        f"Generated markdown file with {len(translations)} units."
    )


if __name__ == "__main__":
    cli()