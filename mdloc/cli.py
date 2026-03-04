"""
mdloc CLI module.

Provides two main commands:

- extract:
    Convert a Markdown file into an XLIFF 2.0 file.
    The Markdown structure is preserved inside a <skeleton> element.
    Only translatable text is exposed inside <unit>/<segment>/<source>.
    Each unit includes contextual <notes> (line number and Markdown prefix).

- reconstruct:
    Rebuild the original Markdown file by reinjecting translated text
    into the skeleton using stable placeholders.

This implementation guarantees:

- Clean XLIFF 2.0 structure
- Markdown syntax hidden from translators
- Exact skeleton preservation
- Stable placeholder-based reconstruction
- Context preservation (line numbers and prefixes)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import click
import xml.etree.ElementTree as ET


# ============================================================
# Constants
# ============================================================

PLACEHOLDER_PATTERN: str = "$(ID:{})"
XLIFF_NS: str = "urn:oasis:names:tc:xliff:document:2.0"


# ============================================================
# Extraction Logic
# ============================================================

def extract_markdown(original_text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Extract translatable content from a Markdown file.

    The function processes the file line by line:
    - Detects Markdown prefixes (#, ##, *, indentation, etc.)
    - Replaces only the textual content with placeholders
    - Preserves the exact Markdown structure in the skeleton
    - Stores contextual information for XLIFF notes

    Args:
        original_text (str):
            The full Markdown file content.

    Returns:
        Tuple[str, List[Dict[str, str]]]:
            - skeleton:
                Markdown content with placeholders instead of text.
            - units:
                List of translation units containing:
                    {
                        "id": str,
                        "source": str,
                        "line": str,
                        "prefix": str
                    }
    """

    lines: List[str] = original_text.splitlines()
    new_lines: List[str] = []
    units: List[Dict[str, str]] = []

    for line_number, line in enumerate(lines, start=1):

        stripped = line.lstrip()

        if not stripped:
            new_lines.append(line)
            continue

        indentation = line[: len(line) - len(stripped)]

        markdown_prefix = ""
        content = stripped

        # Detect headings
        if stripped.startswith("#"):
            parts = stripped.split(" ", 1)
            if len(parts) == 2:
                markdown_prefix = indentation + parts[0] + " "
                content = parts[1]

        # Detect unordered lists
        elif stripped.startswith(("* ", "- ", "+ ")):
            markdown_prefix = indentation + stripped[:2]
            content = stripped[2:]

        else:
            markdown_prefix = indentation

        if not content.strip():
            new_lines.append(line)
            continue

        unit_id = str(uuid.uuid4())
        placeholder = PLACEHOLDER_PATTERN.format(unit_id)

        new_line = markdown_prefix + placeholder
        new_lines.append(new_line)

        units.append({
            "id": unit_id,
            "source": content,
            "line": str(line_number),
            "prefix": markdown_prefix
        })

    skeleton = "\n".join(new_lines)

    return skeleton, units


# ============================================================
# XLIFF Builder
# ============================================================

def build_xliff(skeleton: str, units: List[Dict[str, str]], file_id: str) -> str:
    """
    Build a complete XLIFF 2.0 document.

    The generated structure:

    <xliff version="2.0" srcLang="en">
        <file id="..." original="...">
            <skeleton>...</skeleton>
            <unit>
                <notes>
                    <note appliesTo="source">line: X</note>
                    <note appliesTo="source">prefix: ...</note>
                </notes>
                <segment>
                    <source>Text</source>
                </segment>
            </unit>
        </file>
    </xliff>

    Args:
        skeleton (str):
            Markdown skeleton containing placeholders.

        units (List[Dict[str, str]]):
            Extracted translation units.

        file_id (str):
            Identifier for the <file> element.

    Returns:
        str:
            Serialized XLIFF content.
    """

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
        {
            "id": file_id,
            "original": file_id
        }
    )

    # Instead of adding the skeleton to the XML tree, we keep it separate
    # We'll inject it manually later to guarantee line breaks


    for unit in units:

        unit_elem = ET.SubElement(file_elem, "unit", {"id": unit["id"]})

        notes_elem = ET.SubElement(unit_elem, "notes")

        note_line = ET.SubElement(notes_elem, "note", {"appliesTo": "source"})
        note_line.text = f"line: {unit['line']}"

        if unit["prefix"].strip():
            note_prefix = ET.SubElement(notes_elem, "note", {"appliesTo": "source"})
            note_prefix.text = f"prefix: {unit['prefix']}"

        segment = ET.SubElement(unit_elem, "segment")
        source = ET.SubElement(segment, "source")
        source.text = unit["source"]

    ET.indent(xliff, space="   ")

    # Serialize the XML tree (without skeleton)
    ET.indent(xliff, space="    ")
    xml_body = ET.tostring(xliff, encoding="unicode")

    # Find where <file> opens and closes
    file_start = xml_body.find("<file ")
    file_end = xml_body.find(">", file_start) + 1
    file_close = xml_body.rfind("</file>")

    # Clean skeleton to remove leading/trailing empty lines
    skeleton_clean = skeleton.strip("\n")

    # Insert skeleton after <file ...> tag with proper line breaks
    xml_body = (
        xml_body[:file_end]            # up to closing '>' of <file ...>
        + "\n<skeleton>\n"             # newline + opening skeleton
        + skeleton_clean + "\n"        # skeleton content
        + "</skeleton>"              # closing skeleton tag
        + xml_body[file_end:file_close]  # rest of file content
        + xml_body[file_close:]          # closing </file>
    )

    xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'

    return xml_header + xml_body


# ============================================================
# XLIFF Parsing
# ============================================================

def parse_xliff(xliff_content: str) -> Tuple[str, Dict[str, str]]:
    """
    Parse an XLIFF 2.0 file and extract:

    - skeleton
    - translation units (target if present, otherwise source)

    Args:
        xliff_content (str):
            Raw XLIFF content.

    Returns:
        Tuple[str, Dict[str, str]]:
            - skeleton (str)
            - translations (dict id -> translated text)
    """

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
    """
    Reconstruct the Markdown file by replacing placeholders
    with translated content.

    Args:
        skeleton (str):
            Markdown skeleton containing placeholders.

        translations (Dict[str, str]):
            Mapping of placeholder IDs to translated text.

    Returns:
        str:
            Fully reconstructed Markdown content.
    """

    result = skeleton

    # Remove leading empty lines in skeleton before reconstruction
    skeleton_clean = skeleton.lstrip("\n")

    result = skeleton_clean

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
    """
    Extract translatable content from a Markdown file into XLIFF 2.0.
    """

    click.echo(f"Generating XLIFF file {output_xliff} from {input_md}...")

    original_text = Path(input_md).read_text(encoding="utf-8-sig")

    skeleton, units = extract_markdown(original_text)

    file_id = Path(input_md).name

    xliff_content = build_xliff(skeleton, units, file_id)

    Path(output_xliff).write_text(xliff_content, encoding="utf-8")

    click.echo(
        f"Generated XLIFF file with {len(units)} translatable strings."
    )


@cli.command()
@click.argument("input_xliff", type=click.Path(exists=True))
@click.argument("output_md", type=click.Path())
def reconstruct(input_xliff: str, output_md: str) -> None:
    """
    Reconstruct a Markdown file from a translated XLIFF file.
    """

    click.echo(f"Generating markdown file {output_md} from {input_xliff}...")

    xliff_content = Path(input_xliff).read_text(encoding="utf-8")

    skeleton, translations = parse_xliff(xliff_content)

    reconstructed = reconstruct_markdown(skeleton, translations)

    Path(output_md).write_text(reconstructed, encoding="utf-8")

    click.echo(
        f"Generated markdown file with {len(translations)} translatable strings."
    )


if __name__ == "__main__":
    cli()