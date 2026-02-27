"""
mdloc CLI module.

Provides two main commands:

- extract: Convert a Markdown file into an XLIFF 2.0 file while preserving
           the Markdown structure inside a <skeleton> element and exposing
           only translatable text inside <unit>/<segment>/<source> elements.

- reconstruct: Rebuild the original Markdown file by injecting translated
               text back into the skeleton.

This implementation guarantees:

- No Markdown syntax exposed to translators
- No indentation pollution in reconstructed Markdown
- Stable placeholder-based reconstruction
- Clean and readable XLIFF output
"""

import uuid
import click
from pathlib import Path
from markdown_it import MarkdownIt
import xml.etree.ElementTree as ET


PLACEHOLDER_PATTERN = "$(ID:{})"
XLIFF_NS = "urn:oasis:names:tc:xliff:document:2.0"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


# ============================================================
# Extraction Logic
# ============================================================

def extract_markdown(original_text: str):
    """
    Extract translatable text from Markdown content.

    The function parses the Markdown into an AST using markdown-it-py,
    replaces only plain text nodes with unique placeholders, and preserves
    the original Markdown structure inside a skeleton string.

    Args:
        original_text (str): The original Markdown file content.

    Returns:
        tuple[str, list[dict]]:
            - skeleton (str): Markdown content with placeholders.
            - units (list): List of translation units (id + source text).
    """

    md = MarkdownIt()
    tokens = md.parse(original_text)

    skeleton = original_text
    units = []

    search_start = 0

    for token in tokens:
        if token.type != "inline" or not token.children:
            continue

        for child in token.children:
            if child.type != "text":
                continue

            content = child.content
            if not content.strip():
                continue

            index = skeleton.find(content, search_start)
            if index == -1:
                continue

            unit_id = uuid.uuid4().hex
            placeholder = PLACEHOLDER_PATTERN.format(unit_id)

            skeleton = (
                skeleton[:index]
                + placeholder
                + skeleton[index + len(content):]
            )

            units.append({
                "id": unit_id,
                "source": content
            })

            search_start = index + len(placeholder)

    return skeleton, units


# ============================================================
# XLIFF Builder
# ============================================================

def build_xliff(skeleton: str, units: list, file_id: str) -> str:
    """
    Build a clean and readable XLIFF 2.0 document.

    The generated XLIFF:
    - Uses version 2.0
    - Preserves Markdown exactly inside <skeleton>
    - Exposes only text inside <unit>/<segment>/<source>
    - Does not inject indentation into skeleton content
    - Includes a minimal XML declaration

    Args:
        skeleton (str): Markdown skeleton with placeholders.
        units (list): Extracted translation units.
        file_id (str): Identifier for the <file> element.

    Returns:
        str: Serialized XLIFF content.
    """

    xliff = ET.Element(
        "xliff",
        {
            "xmlns": XLIFF_NS,
            "version": "2.0",
            "srcLang": "en"
        }
    )

    file_elem = ET.SubElement(xliff, "file", {"id": file_id})

    # Preserve skeleton exactly as-is
    skeleton_elem = ET.SubElement(
        file_elem,
        "skeleton",
        {XML_SPACE: "preserve"}
    )
    skeleton_elem.text = "\n" + skeleton
    skeleton_elem.tail = "\n"

    for unit in units:
        unit_elem = ET.SubElement(file_elem, "unit", {"id": unit["id"]})
        segment = ET.SubElement(unit_elem, "segment")
        source = ET.SubElement(segment, "source")
        source.text = unit["source"]

    # Indent XML structure (not skeleton content)
    ET.indent(xliff, space="    ")

    xml_body = ET.tostring(xliff, encoding="unicode")

    # Manual XML declaration (exact format)
    xml_header = '<?xml version="1.0"?>\n'

    return xml_header + xml_body


# ============================================================
# XLIFF Parsing
# ============================================================

def parse_xliff(xliff_content: str):
    """
    Parse an XLIFF file and extract skeleton and translations.

    Ensures no unintended leading newline is introduced
    in the reconstructed Markdown.

    Args:
        xliff_content (str): Raw XLIFF content.

    Returns:
        tuple[str, dict]:
            - skeleton (str)
            - translations (dict id -> translated text)
    """

    ns = {"x": XLIFF_NS}
    root = ET.fromstring(xliff_content)

    skeleton_elem = root.find(".//x:skeleton", ns)
    skeleton = skeleton_elem.text if skeleton_elem is not None else ""

    if skeleton is None:
        skeleton = ""

    # Remove accidental leading newline caused by XML formatting
    if skeleton.startswith("\n"):
        skeleton = skeleton[1:]

    translations = {}

    for unit in root.findall(".//x:unit", ns):
        unit_id = unit.attrib["id"]

        target = unit.find(".//x:target", ns)
        source = unit.find(".//x:source", ns)

        if target is not None and target.text:
            translations[unit_id] = target.text
        elif source is not None and source.text:
            translations[unit_id] = source.text

    return skeleton, translations


# ============================================================
# Reconstruction
# ============================================================

def reconstruct_markdown(skeleton: str, translations: dict) -> str:
    """
    Reconstruct the original Markdown by replacing placeholders
    with translated text.

    Args:
        skeleton (str): Markdown skeleton containing placeholders.
        translations (dict): Mapping of placeholder IDs to text.

    Returns:
        str: Reconstructed Markdown content.
    """

    result = skeleton

    for unit_id, translated_text in translations.items():
        placeholder = PLACEHOLDER_PATTERN.format(unit_id)
        result = result.replace(placeholder, translated_text)

    return result


# ============================================================
# CLI Commands
# ============================================================

@click.group()
def cli():
    """mdloc command-line interface."""
    pass


@cli.command()
@click.argument("input_md", type=click.Path(exists=True))
@click.argument("output_xliff", type=click.Path())
def extract(input_md, output_xliff):
    """
    Extract translatable content from a Markdown file into XLIFF.
    """

    click.echo(
        f"Generating XLIFF file {output_xliff} from {input_md}..."
    )

    original_text = Path(input_md).read_text(encoding="utf-8-sig")

    source_lines = original_text.count("\n") + 1

    skeleton, units = extract_markdown(original_text)

    skeleton_lines = skeleton.count("\n") + 1

    file_id = Path(input_md).name

    xliff_content = build_xliff(skeleton, units, file_id)

    Path(output_xliff).write_text(xliff_content, encoding="utf-8")

    click.echo(
        f"Generated XLIFF file with {len(units)} translatable strings, "
        f"{source_lines} total source lines, "
        f"and {skeleton_lines} skeleton lines."
    )


@cli.command()
@click.argument("input_xliff", type=click.Path(exists=True))
@click.argument("output_md", type=click.Path())
def reconstruct(input_xliff, output_md):
    """
    Reconstruct a Markdown file from a translated XLIFF file.
    """

    click.echo(
        f"Generating markdown file {output_md} from {input_xliff}..."
    )

    xliff_content = Path(input_xliff).read_text(encoding="utf-8")

    skeleton, translations = parse_xliff(xliff_content)

    total_units = len(translations)

    reconstructed = reconstruct_markdown(skeleton, translations)

    Path(output_md).write_text(reconstructed, encoding="utf-8")

    total_lines = reconstructed.count("\n") + 1
    translated_strings = sum(1 for v in translations.values() if v.strip())
    bad_translations = total_units - translated_strings

    click.echo(
        f"Generated markdown file with {total_lines} total lines, "
        f"{total_units} translatable strings, "
        f"and {translated_strings} translated strings. "
        f"Ignoring {bad_translations} bad translated strings."
    )


if __name__ == "__main__":
    cli()