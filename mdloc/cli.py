"""
mdloc CLI module.

Enhanced version with:

- Markdown parsing via markdown-it-py
- Detection of Markdown block prefixes (headings, lists, blockquotes)
- Detection of inline emphasis (bold, italic, inline code)
- URL and domain protection
- Automatic state="initial" for non-translatable lines
- Prefix and suffix detection
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

PROTECTED_PATTERN = re.compile(
    r"https?://\S+|\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b"
)

BLOCK_PREFIX_PATTERN = re.compile(
    r"^(\s*(?:#{1,6}\s+|>\s+|\*\s+|-\s+|\+\s+|\d+\.\s+))"
)
BLOCK_SUFFIX_PATTERN = re.compile(
    r"\s+(#{1,6})\s*$"
)

# ============================================================
# Utility Functions
# ============================================================

def is_non_translatable(text: str) -> bool:
    """
    Return True if the line contains no human-translatable content.
    """

    stripped = text.strip()

    stripped = MD_REFERENCE_PATTERN.sub("", stripped)
    stripped = URL_PATTERN.sub("", stripped)
    stripped = DOMAIN_PATTERN.sub("", stripped)

    stripped = re.sub(r"[^\w]", "", stripped)

    return stripped == ""


def split_protected_parts(text: str) -> List[Tuple[bool, str]]:
    """
    Split text into (is_translatable, content) segments.

    URLs and domain names are returned as non-translatable segments.
    """

    parts: List[Tuple[bool, str]] = []

    last = 0

    for match in PROTECTED_PATTERN.finditer(text):

        start, end = match.span()

        if start > last:
            parts.append((True, text[last:start]))

        parts.append((False, match.group()))

        last = end

    if last < len(text):
        parts.append((True, text[last:]))

    return parts


def extract_block_prefix(line: str) -> Tuple[str, str]:
    """
    Extract Markdown block prefix from a line.

    Examples:
        "# Title" -> ("# ", "Title")
        "- Item" -> ("- ", "Item")
        "> Quote" -> ("> ", "Quote")
    """

    match = BLOCK_PREFIX_PATTERN.match(line)

    if match:
        prefix = match.group(1)
        return prefix, line[len(prefix):]

    return "", line


def extract_text_prefix(text: str) -> Tuple[str, str]:
    """
    Extract punctuation prefix from text.

    Example:
        ": Hello" -> (": ", "Hello")
    """

    if text.startswith(": "):
        return ": ", text[2:]

    return "", text


def extract_block_suffix(text: str) -> Tuple[str, str]:
    """
    Extract trailing Markdown heading markers.

    Example:
        "Title #" -> (" #", "Title")
    """

    match = BLOCK_SUFFIX_PATTERN.search(text)

    if match:
        suffix = match.group(0)
        return suffix, text[:match.start()]

    return "", text

# ============================================================
# Extraction Logic
# ============================================================

def extract_markdown(original_text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Extract translation units from Markdown text.

    Returns:
        skeleton: Markdown skeleton containing placeholders
        units: list of translation units
    """

    lines = original_text.splitlines()

    new_lines: List[str] = []
    units: List[Dict[str, str]] = []

    for line_number, line in enumerate(lines, start=1):

        if not line.strip():
            new_lines.append(line)
            continue

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

        block_prefix, content_line = extract_block_prefix(line)
        block_suffix, content_line = extract_block_suffix(content_line)

        tokens = md.parse(content_line)

        new_line = block_prefix
        contains_translatable = False

        md_prefix = ""
        md_suffix = ""

        link_url = ""

        for token in tokens:

            if token.type != "inline":
                new_line += token.markup or ""
                continue

            for child in token.children:

                if child.type == "link_open":

                    href = ""

                    if child.attrs and "href" in child.attrs:
                        href = child.attrs["href"]

                    new_line += "["
                    link_url = href
                    continue

                if child.type == "link_close":

                    new_line += f"]({link_url})"
                    link_url = ""
                    continue

                if child.type == "strong_open":
                    md_prefix += "**"
                    continue

                if child.type == "strong_close":
                    md_suffix = "**"
                    continue

                if child.type == "em_open":
                    md_prefix += "*"
                    continue

                if child.type == "em_close":
                    md_suffix = "*"
                    continue

                if child.type == "code_inline":

                    text = child.content.strip()

                    if not text:
                        new_line += "`" + child.content + "`"
                        continue

                    unit_id = str(uuid.uuid4())
                    placeholder = PLACEHOLDER_PATTERN.format(unit_id)

                    new_line += placeholder
                    contains_translatable = True

                    units.append({
                        "id": unit_id,
                        "source": text,
                        "line": str(line_number),
                        "initial": False,
                        "prefix": block_prefix + md_prefix + "`",
                        "suffix": "`"
                    })

                    md_prefix = ""
                    md_suffix = ""

                    continue

                if child.type == "text":

                    parts = split_protected_parts(child.content)

                    for is_translatable, content in parts:

                        if not content:
                            continue

                        if not is_translatable:
                            new_line += content
                            continue

                        text_prefix, text = extract_text_prefix(content)

                        text = text.strip()

                        if not text:
                            new_line += content
                            continue

                        if not re.search(r"\w", text):
                            new_line += content
                            continue

                        unit_id = str(uuid.uuid4())
                        placeholder = PLACEHOLDER_PATTERN.format(unit_id)

                        new_line += text_prefix + md_prefix + placeholder + md_suffix + block_suffix
                        contains_translatable = True

                        units.append({
                            "id": unit_id,
                            "source": text,
                            "line": str(line_number),
                            "initial": False,
                            "prefix": block_prefix + md_prefix + text_prefix,
                            "suffix": md_suffix + block_suffix
                        })

                        md_prefix = ""
                        md_suffix = ""

                else:
                    new_line += child.markup or child.content or ""

        if not contains_translatable:

            unit_id = str(uuid.uuid4())
            placeholder = PLACEHOLDER_PATTERN.format(unit_id)

            new_lines.append(block_prefix + placeholder)

            units.append({
                "id": unit_id,
                "source": content_line,
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
    """
    Build an XLIFF 2.0 document.
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
        {"id": file_id, "original": file_id}
    )

    for unit in units:

        unit_elem = ET.SubElement(file_elem, "unit", {"id": unit["id"]})

        notes_elem = ET.SubElement(unit_elem, "notes")

        note_line = ET.SubElement(notes_elem, "note", {"appliesTo": "source"})
        note_line.text = f"line: {unit['line']}"

        if unit["initial"]:
            note_initial = ET.SubElement(notes_elem, "note")
            note_initial.text = "non-translatable content preserved"

        if unit.get("prefix"):
            note_prefix = ET.SubElement(
                notes_elem,
                "note",
                {"appliesTo": "source"}
            )
            note_prefix.text = f"prefix: {unit['prefix']}"

        if unit.get("suffix"):
            note_suffix = ET.SubElement(
                notes_elem,
                "note",
                {"appliesTo": "source"}
            )
            note_suffix.text = f"suffix: {unit['suffix']}"

        segment_attrs = {"state": "initial"} if unit["initial"] else {}

        segment = ET.SubElement(unit_elem, "segment", segment_attrs)

        source = ET.SubElement(segment, "source")
        source.text = unit["source"]

        if unit["initial"]:
            target = ET.SubElement(segment, "target")
            target.text = unit["source"]

    ET.indent(xliff, space="    ")

    xml_body = ET.tostring(xliff, encoding="unicode")

    file_start = xml_body.find("<file ")
    file_end = xml_body.find(">", file_start) + 1
    file_close = xml_body.rfind("</file>")

    skeleton_clean = skeleton.strip("\n")

    xml_body = (
        xml_body[:file_end]
        + "\n<skeleton>\n"
        + skeleton_clean + "\n"
        + "</skeleton>"
        + xml_body[file_end:file_close]
        + xml_body[file_close:]
    )

    xml_header = '<?xml version="1.0" encoding="utf-8"?>\n'

    return xml_header + xml_body


# ============================================================
# XLIFF Parsing
# ============================================================

def parse_xliff(xliff_content: str) -> Tuple[str, Dict[str, str]]:
    """
    Parse an XLIFF file and return skeleton and translations.
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
    Reconstruct Markdown text from skeleton and translations.
    """

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
    """
    Extract Markdown content into an XLIFF file.
    """

    click.echo(f"Generating XLIFF file {output_xliff} from {input_md}...")

    original_text = Path(input_md).read_text(encoding="utf-8-sig")

    skeleton, units = extract_markdown(original_text)

    file_id = Path(input_md).name

    xliff_content = build_xliff(skeleton, units, file_id)

    Path(output_xliff).write_text(xliff_content, encoding="utf-8")

    click.echo(f"Generated XLIFF file with {len(units)} units.")


@cli.command()
@click.argument("input_xliff", type=click.Path(exists=True))
@click.argument("output_md", type=click.Path())
def reconstruct(input_xliff: str, output_md: str) -> None:
    """
    Reconstruct Markdown file from translated XLIFF.
    """

    click.echo(f"Generating markdown file {output_md} from {input_xliff}...")

    xliff_content = Path(input_xliff).read_text(encoding="utf-8")

    skeleton, translations = parse_xliff(xliff_content)

    reconstructed = reconstruct_markdown(skeleton, translations)

    Path(output_md).write_text(reconstructed, encoding="utf-8")

    click.echo(f"Generated markdown file with {len(translations)} units.")


if __name__ == "__main__":
    cli()