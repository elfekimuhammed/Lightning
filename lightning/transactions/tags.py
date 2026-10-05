"""Tags: #words in a transaction's notes, such as #eid, #sahel-trip or #عيد.

A tag is ordinary text in the notes, so nothing is stored apart and editing the notes edits the tags.
It is a # followed by letters, digits, - or _, with at least one letter, so "invoice #4521" is not a
tag; "#Eid" and "#eid" are the same tag. A # right after a letter or digit ("C#") does not start one.
"""
from __future__ import annotations

import re

_TAG = re.compile(r"(?<![\w#&/])#([\w-]+)")


def normalize(text: object) -> str:
    """'#Eid' -> 'eid'; '' when the text is not a tag."""
    tag = str(text or "").strip().removeprefix("#").strip("-_").casefold()
    return tag if re.fullmatch(r"[\w-]+", tag) and any(ch.isalpha() for ch in tag) else ""


def tags_in(text: str | None) -> list[str]:
    """Every tag in a note, once each, in the order written."""
    found: list[str] = []
    for raw in _TAG.findall(text or ""):
        tag = normalize(raw)
        if tag and tag not in found:
            found.append(tag)
    return found


def split(text: str | None) -> list[tuple[str, str]]:
    """A note as pieces to show: (text, "") for plain text and ("#Eid", "eid") for a tag."""
    pieces, at = [], 0
    for match in _TAG.finditer(text or ""):
        tag = normalize(match.group(1))
        if not tag:
            continue
        written = "#" + match.group(1).rstrip("-_")
        if match.start() > at:
            pieces.append((text[at:match.start()], ""))
        pieces.append((written, tag))
        at = match.start() + len(written)
    if at < len(text or ""):
        pieces.append((text[at:], ""))
    return pieces
