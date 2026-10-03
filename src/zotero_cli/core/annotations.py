"""PDF annotations as one record shape, whichever gateway read them (Issue #558).

Zotero stores each highlight, note, image, ink stroke, underline and text box as an
`annotation` item whose parent is a PDF attachment. The Web API returns them as child
items (`annotationType`, `annotationText`, ...); `zotero.sqlite` keeps them in
`itemAnnotations` with an integer type. Both are mapped to the dicts built here.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence

# Zotero.Annotations.ANNOTATION_TYPE_*, as stored in itemAnnotations.type
SQLITE_TYPES = {1: "highlight", 2: "note", 3: "image", 4: "ink", 5: "underline", 6: "text"}
TYPES = tuple(SQLITE_TYPES.values())

Annotation = Dict[str, Any]


def build(
    key: str,
    attachment: str,
    kind: str,
    text: Optional[str] = None,
    comment: Optional[str] = None,
    color: Optional[str] = None,
    page: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    date_added: Optional[str] = None,
    sort_index: Optional[str] = None,
) -> Annotation:
    return {
        "key": key,
        "attachment": attachment,
        "type": kind,
        "text": text or "",
        "comment": comment or "",
        "color": color or "",
        "page": page or "",
        "tags": list(tags or []),
        "date_added": date_added or "",
        "sort_index": sort_index or "",
    }


def from_api(raw: Mapping[str, Any]) -> Optional[Annotation]:
    """An annotation from a Web API item object, or None if it isn't one."""
    data = raw.get("data", raw)
    if data.get("itemType") != "annotation":
        return None
    return build(
        key=str(raw.get("key") or data.get("key") or ""),
        attachment=str(data.get("parentItem") or ""),
        kind=str(data.get("annotationType") or ""),
        text=data.get("annotationText"),
        comment=data.get("annotationComment"),
        color=data.get("annotationColor"),
        page=data.get("annotationPageLabel"),
        tags=[t.get("tag", "") for t in data.get("tags", []) if t.get("tag")],
        date_added=data.get("dateAdded"),
        sort_index=data.get("annotationSortIndex"),
    )


def in_reading_order(annotations: List[Annotation]) -> List[Annotation]:
    """Grouped by attachment, then in the order they sit in the document (Zotero's
    sort index sorts as text)."""
    return sorted(annotations, key=lambda a: (a["attachment"], a["sort_index"]))


def to_markdown(annotations: Sequence[Annotation]) -> str:
    """An "Annotations" section for a Markdown export: one list item per annotation, with
    its page and type, the marked text, the comment and the tags. Empty when there are
    none. The text comes from the PDF, so line breaks are flattened and control characters
    removed."""
    from zotero_cli.core.utils.terminal_safety import strip_controls

    def line(value: str) -> str:
        return " ".join(strip_controls(value).split())

    if not annotations:
        return ""
    out = ["## Annotations", ""]
    for a in annotations:
        where = f"p. {line(a['page'])}, " if a["page"] else ""
        marked = f'"{line(a["text"])}"' if a["text"] else f"({a['type']})"
        out.append(f"- **{where}{a['type']}:** {marked}")
        if a["comment"]:
            out.append(f"  - Comment: {line(a['comment'])}")
        if a["tags"]:
            out.append(f"  - Tags: {', '.join(line(t) for t in a['tags'])}")
    return "\n".join(out) + "\n"
