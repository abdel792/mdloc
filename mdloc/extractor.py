import re
import hashlib

def stable_id(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def extract_markdown(text):
    segments = {}

    def replace(match):
        content = match.group(0)
        seg_id = stable_id(content)
        segments[seg_id] = content
        return f"$(ID:{seg_id})"

    # Ignore code blocks
    pattern = r"^(?!\s*```)(?!\s*$)(.+)$"
    skeleton = re.sub(pattern, replace, text, flags=re.MULTILINE)

    return segments, skeleton