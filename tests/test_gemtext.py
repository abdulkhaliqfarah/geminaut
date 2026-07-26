"""Tests for geminaut.gemtext \u2014 gemtext parsing."""

from __future__ import annotations

from geminaut.gemtext import extract_links, parse_gemtext, to_plain_text

SAMPLE = """\
# Welcome to my capsule
This is a small web, and it is good.

## Links
=> gemini://example.org/ An example capsule
=> /about About this capsule

* First item
* Second item

> Small pieces, loosely joined.

```
def hello():
    print("preformatted")
```

Regular text continues here.
"""


def test_parses_headings() -> None:
    headings = [line for line in parse_gemtext(SAMPLE) if line.kind == "heading"]
    assert headings[0].text == "Welcome to my capsule"
    assert headings[0].level == 1
    assert headings[1].text == "Links"
    assert headings[1].level == 2


def test_parses_links_with_and_without_labels() -> None:
    links = extract_links(parse_gemtext(SAMPLE))
    assert links[0] == ("An example capsule", "gemini://example.org/")
    assert links[1] == ("About this capsule", "/about")


def test_parses_list_items() -> None:
    items = [line.text for line in parse_gemtext(SAMPLE) if line.kind == "list"]
    assert items == ["First item", "Second item"]


def test_parses_quote() -> None:
    quotes = [line.text for line in parse_gemtext(SAMPLE) if line.kind == "quote"]
    assert quotes == ["Small pieces, loosely joined."]


def test_parses_preformatted_block_and_toggles_off() -> None:
    lines = parse_gemtext(SAMPLE)
    pre_texts = [line.text for line in lines if line.kind == "preformatted"]
    assert pre_texts == ["", "def hello():", '    print("preformatted")']

    trailing = [line.text for line in lines if line.kind == "text" and line.text.strip()]
    assert "Regular text continues here." in trailing


def test_link_without_label_uses_url_as_text() -> None:
    lines = parse_gemtext("=> gemini://example.org/only-url\n")
    assert lines[0].text == "gemini://example.org/only-url"
    assert lines[0].url == "gemini://example.org/only-url"


def test_to_plain_text_round_trips_links() -> None:
    lines = parse_gemtext("=> gemini://example.org/ Example\n")
    assert to_plain_text(lines) == "=> gemini://example.org/ Example"
