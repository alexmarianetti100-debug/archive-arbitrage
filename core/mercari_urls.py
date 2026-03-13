from __future__ import annotations

import re


def mercari_item_id(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    match = re.search(r"/item/(m\d+)", text)
    if match:
        return match.group(1)

    match = re.search(r"\b(m\d+)\b", text)
    if match:
        return match.group(1)

    if text.isdigit():
        return f"m{text}"

    return text


def mercari_item_url(item_id_or_url: str | None) -> str:
    item_id = mercari_item_id(item_id_or_url)
    if not item_id:
        return ""
    return f"https://jp.mercari.com/item/{item_id}"
