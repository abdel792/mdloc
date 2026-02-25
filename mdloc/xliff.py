from lxml import etree

NS = "urn:oasis:names:tc:xliff:document:2.0"

def write_xliff(path, segments, skeleton, src_lang="en"):
    xliff = etree.Element("xliff",
        nsmap={None: NS},
        version="2.0",
        srcLang=src_lang
    )

    file_el = etree.SubElement(xliff, "file", id="file")

    skel = etree.SubElement(file_el, "skeleton")
    skel.text = skeleton

    for seg_id, text in segments.items():
        unit = etree.SubElement(file_el, "unit", id=seg_id)
        segment = etree.SubElement(unit, "segment")
        source = etree.SubElement(segment, "source")
        source.text = text

    tree = etree.ElementTree(xliff)
    tree.write(path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


from lxml import etree

XLIFF_NS = "urn:oasis:names:tc:xliff:document:2.0"


def read_xliff(path):
    """
    Read an XLIFF 2.0 file and extract:
    - The skeleton content
    - A dictionary mapping unit ID -> translated text (target or fallback to source)

    Returns:
        skeleton (str),
        translations (dict[str, str])
    """

    tree = etree.parse(str(path))
    root = tree.getroot()

    # Ensure this is a valid XLIFF 2.0 file
    if root.tag != f"{{{XLIFF_NS}}}xliff":
        raise ValueError(f"Not a valid XLIFF 2.0 file: {path}")

    ns = {"x": XLIFF_NS}

    # -------------------------
    # Extract skeleton safely
    # -------------------------
    skeleton = ""
    skeleton_el = root.find(".//x:skeleton", ns)

    if skeleton_el is not None:
        # Use method="text" to get full textual content
        skeleton = etree.tostring(
            skeleton_el,
            encoding="unicode",
            method="text"
        )

    # -------------------------
    # Extract translation units
    # -------------------------
    translations = {}

    units = root.findall(".//x:unit", ns)

    for unit in units:
        unit_id = unit.get("id")
        if not unit_id:
            continue

        source_el = unit.find(".//x:source", ns)
        target_el = unit.find(".//x:target", ns)

        source_text = source_el.text if source_el is not None and source_el.text else ""
        target_text = (
            target_el.text
            if target_el is not None and target_el.text
            else source_text
        )

        translations[unit_id] = target_text

    return skeleton, translations