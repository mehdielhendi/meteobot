"""Shared reply formatting helpers for consistent chatbot answers."""

from __future__ import annotations


def styled_reply(
    title: str,
    meta: list[str] | None = None,
    sections: list[tuple[str, list[str]]] | None = None,
    body_lines: list[str] | None = None,
    source: str | None = None,
) -> str:
    """Build a structured plain-text reply the UI can render richly.

    Convention (parsed by frontend):
    - first line = title
    - lines starting with no bullet and containing " : " early = meta
    - blank line + "• ..." = section header
    - "  field : value" = section fields
    - final "Source : ..." = source
    """
    lines: list[str] = [title]
    for item in meta or []:
        if item:
            lines.append(item)
    if body_lines:
        if meta:
            lines.append("")
        lines.extend(body_lines)
    for header, fields in sections or []:
        lines.append("")
        lines.append(f"• {header}" if not header.startswith("•") else header)
        for field in fields:
            if field.startswith("  "):
                lines.append(field)
            else:
                lines.append(f"  {field}")
    if source:
        lines.append(f"Source : {source}" if not source.startswith("Source") else source)
    return "\n".join(lines)


def pad_label(label: str, width: int = 12) -> str:
    return label.ljust(width)
