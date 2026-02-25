# cli.py
import click
from pathlib import Path
from .extractor import extract_markdown
from .xliff import write_xliff, read_xliff
from .reconstructor import reconstruct


@click.group()
def cli():
    """mdloc CLI: Markdown <-> XLIFF extraction and reconstruction"""
    pass


@cli.command()
@click.argument("input_file")
def extract(input_file):
    """Extract Markdown and generate an XLIFF file"""
    input_path = Path(input_file)
    if not input_path.exists():
        print("File not found:", input_file)
        return

    # Read Markdown file
    print("Reading file:", input_file)
    text = input_path.read_text(encoding="utf-8")
    print("File length:", len(text))
    print("First 100 characters:", text[:100])

    # Extract segments and skeleton
    segments, skeleton = extract_markdown(text)
    print("Number of segments found:", len(segments))
    print("Skeleton preview (first 100 chars):", skeleton[:100])

    # Generate XLIFF file in the same directory
    output = input_path.resolve().with_suffix(".xliff")
    write_xliff(output, segments, skeleton)
    print("XLIFF file generated:", output)

@cli.command(name="reconstruct")
@click.argument("xliff_file")
def reconstruct_cmd(xliff_file):
    """Reconstruct Markdown from a translated XLIFF file"""

    xliff_path = Path(xliff_file)
    if not xliff_path.exists():
        print("XLIFF file not found:", xliff_file)
        return

    print("Reading XLIFF file:", xliff_file)

    # Read skeleton and translations dictionary
    skeleton, translations = read_xliff(xliff_path)
    if skeleton:
        skeleton = skeleton.lstrip("\ufeff")

    print("Number of translation units:", len(translations))
    print("Skeleton length:", len(skeleton))

    if not skeleton:
        print("Warning: Skeleton is empty.")
        return

    # Replace placeholders with translated text
    result_md = skeleton

    for unit_id, text in translations.items():
        result_md = result_md.replace(f"$(ID:{unit_id})", text)

    # Write reconstructed Markdown
    output_md = xliff_path.with_suffix(".translated.md")
    # Remove potential UTF-8 BOM
    result_md = result_md.lstrip("\ufeff")
    output_md.write_text(result_md, encoding="utf-8")

    print("Reconstructed Markdown file generated:", output_md)

# Ensure python -m mdloc.cli works
if __name__ == "__main__":
    cli()