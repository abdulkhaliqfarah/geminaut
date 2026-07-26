"""Parse gemtext (.gmi) documents into structured lines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LineKind = Literal["text", "link", "heading", "list", "quote", "preformatted"]


@dataclass
class GemtextLine:
    """A single parsed line of a gemtext document."""

    kind: LineKind
    text: str
    url: str | None = None
    level: int = 0  # heading level (1-3)


def parse_gemtext(source: str) -> list[GemtextLine]:
    """Parse raw gemtext into a list of :class:`GemtextLine`."""
    lines: list[GemtextLine] = []
    in_preformatted = False

    for raw_line in source.splitlines():
        if raw_line.startswith("```"):
            in_preformatted = not in_preformatted
            if in_preformatted:
                lines.append(GemtextLine(kind="preformatted", text=raw_line[3:].strip()))
            continue

        if in_preformatted:
            lines.append(GemtextLine(kind="preformatted", text=raw_line))
            continue

        if raw_line.startswith("=>"):
            remainder = raw_line[2:].strip()
            url, _, label = remainder.partition(" ")
            lines.append(GemtextLine(kind="link", text=label.strip() or url, url=url))
        elif raw_line.startswith("###"):
            lines.append(GemtextLine(kind="heading", text=raw_line[3:].strip(), level=3))
        elif raw_line.startswith("##"):
            lines.append(GemtextLine(kind="heading", text=raw_line[2:].strip(), level=2))
        elif raw_line.startswith("#"):
            lines.append(GemtextLine(kind="heading", text=raw_line[1:].strip(), level=1))
        elif raw_line.startswith("* "):
            lines.append(GemtextLine(kind="list", text=raw_line[2:].strip()))
        elif raw_line.startswith(">"):
            lines.append(GemtextLine(kind="quote", text=raw_line[1:].strip()))
        else:
            lines.append(GemtextLine(kind="text", text=raw_line))

    return lines


def extract_links(lines: list[GemtextLine]) -> list[tuple[str, str]]:
    """Return (label, url) pairs for every link line, in document order."""
    return [(line.text, line.url) for line in lines if line.kind == "link" and line.url]


def to_plain_text(lines: list[GemtextLine]) -> str:
    """Render parsed gemtext back into a simple readable plain-text form."""
    out: list[str] = []
    for line in lines:
        if line.kind == "heading":
            out.append(("#" * line.level) + " " + line.text)
        elif line.kind == "link":
            out.append(f"=> {line.url} {line.text}")
        elif line.kind == "list":
            out.append(f"\u2022 {line.text}")
        elif line.kind == "quote":
            out.append(f"> {line.text}")
        else:
            out.append(line.text)
    return "\n".join(out)
