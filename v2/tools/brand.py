"""Shared by build_v2.py and build_data_page.py: the DexSuite name in the brand colour."""
import re


def brand(page):
    """Wrap every visible DexSuite in span.ds (the wordmark gradient), skipping tags, <pre>, <script>, <title> and the hero h1."""
    out, skip = [], 0
    for part in re.split(r"(<[^>]+>)", page):
        if part.startswith("<"):
            tag = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
            name = tag.group(1).lower() if tag else ""
            if name in ("pre", "script", "title", "h1", "style"):
                skip += -1 if part.startswith("</") else 1
            out.append(part)
        else:
            out.append(part if skip else part.replace("DexSuite", '<span class="ds">DexSuite</span>'))
    return "".join(out)
