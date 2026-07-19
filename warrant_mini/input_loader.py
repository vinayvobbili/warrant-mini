"""Resolve a review source into clean plain text.

Accepts three source shapes, auto-detected:
  * a URL (http/https)      -> fetched and stripped to visible text
  * a path to a .txt/.md    -> read from disk
  * anything else           -> treated as pasted literal text
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

_UA = "warrant-mini/0.1 (compliance-review demo)"
_MAX_URL_BYTES = 2_000_000


@dataclass
class LoadedInput:
    text: str
    source_label: str  # human-readable description of where the text came from


def _looks_like_url(s: str) -> bool:
    parsed = urlparse(s.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _fetch_url(url: str) -> LoadedInput:
    with httpx.Client(follow_redirects=True, timeout=20.0, headers={"User-Agent": _UA}) as client:
        resp = client.get(url)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text[:_MAX_URL_BYTES], "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    # Prefer the main/article body when present; fall back to the whole document.
    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text(separator="\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        raise ValueError(f"Fetched {url} but extracted no readable text.")
    return LoadedInput(text=text, source_label=f"URL: {url}")


def load_input(src: str) -> LoadedInput:
    """Resolve `src` (URL, file path, or literal text) into plain text."""
    if _looks_like_url(src):
        return _fetch_url(src)

    path = Path(src).expanduser()
    # Only treat it as a file if it actually exists — a short pasted sentence
    # shouldn't be mistaken for a missing file path.
    if path.exists() and path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"{path} is empty.")
        return LoadedInput(text=text, source_label=f"file: {path}")

    text = src.strip()
    if not text:
        raise ValueError("No input text provided.")
    return LoadedInput(text=text, source_label="pasted text")
