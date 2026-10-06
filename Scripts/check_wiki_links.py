#!/usr/bin/env python3
"""Check that every [[wiki link]] in the vault resolves to an existing, live note.

Run from anywhere: python3 "Areas/Second Brain/Scripts/check_wiki_links.py"
Exit code 0 = no broken links; 1 = broken links found.

Reports two things:

BROKEN  — the link resolves to nothing. Always an error, exit 1.
ARCHIVED — the link resolves, but only to a note under an `Archive/` directory,
           and the linking note is itself live. Warning only, exit 0.

The archived check exists because that case is otherwise silent: the file still
exists so the link resolves and the vault looks green, but it now points at dead
content and nothing says so. Links from one archived note to another are normal
and are not reported. Added 2026-09-01.

Rules (matching Obsidian's resolution):
- [[Name]] resolves if any .md file in the vault is named "Name.md" (case-insensitive).
- [[Name|alias]] and [[Name#heading]] resolve on the part before | or #.
- [[path/To/Name]] resolves on the last path segment.
- [[Name.base]] and [[Name.base#View]] resolve to an Obsidian Bases file (added 2026-09-04).
- Links inside fenced code blocks and inline `code spans` are IGNORED — that's where
  illustrative examples and templates live (CLAUDE.md conventions, skill specs).
- A file whose frontmatter carries `link-check: skip` is IGNORED entirely. That is for
  verbatim sources kept unedited (pasted articles, transcripts) whose [[links]] are the
  original author's examples and are not ours to fix. Added 2026-08-31.

Written 2026-08-16, after the _Project.md naming convention silently broke every
project link in the vault for two days. See "2026-08-16 Folder note convention.md".
"""

import re
import sys
from pathlib import Path

# Vault root = three levels up from this script (Scripts -> Second Brain -> Areas -> root)
VAULT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".obsidian", ".claude"}

LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
SKIP_MARKER = "link-check: skip"
INLINE_CODE_RE = re.compile(r"`[^`]*`")
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def note_index() -> dict[str, list[Path]]:
    """Map lowercase note name -> every file with that name (a name can repeat)."""
    idx: dict[str, list[Path]] = {}
    for p in VAULT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        idx.setdefault(p.stem.lower(), []).append(p)
    for p in VAULT.rglob("*.base"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        idx.setdefault(p.name.lower(), []).append(p)   # [[Tasks.base#View]] -> "tasks.base"
    return idx


def is_archived(p: Path) -> bool:
    """True if the note sits under an Archive/ directory at any depth."""
    return "Archive" in p.relative_to(VAULT).parts[:-1]


def target_of(link: str) -> str:
    target = link.split("|")[0].split("#")[0].strip()
    target = target.split("/")[-1]  # path-style links resolve on final segment
    return target


def is_skipped(text: str) -> bool:
    """True if the file's frontmatter carries `link-check: skip` (verbatim sources)."""
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    return end != -1 and SKIP_MARKER in text[:end]


def main() -> int:
    idx = note_index()
    broken: list[tuple[str, int, str]] = []
    archived: list[tuple[str, int, str, str]] = []
    for p in sorted(VAULT.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        text = p.read_text(encoding="utf-8")
        if is_skipped(text):
            continue
        source_is_live = not is_archived(p)
        fence = None  # (char, length) of the currently open fence, else None
        for lineno, line in enumerate(text.splitlines(), 1):
            m_fence = FENCE_RE.match(line.strip())
            if m_fence:
                marker = m_fence.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1]:
                    fence = None  # closes only on same char, >= opening length
                continue
            if fence is not None:
                continue
            line = INLINE_CODE_RE.sub("", line)
            for m in LINK_RE.finditer(line):
                target = target_of(m.group(1))
                if not target:  # [[#heading]] same-file link
                    continue
                matches = idx.get(target.lower())
                if not matches:
                    broken.append((str(p.relative_to(VAULT)), lineno, m.group(0)))
                elif source_is_live and all(is_archived(t) for t in matches):
                    archived.append((str(p.relative_to(VAULT)), lineno, m.group(0),
                                     str(matches[0].relative_to(VAULT))))

    if broken:
        print(f"BROKEN LINKS: {len(broken)}")
        for path, lineno, link in broken:
            print(f"  {path}:{lineno}  {link}")
    if archived:
        print(f"\nARCHIVED TARGETS: {len(archived)} — link resolves, but only into Archive/")
        for path, lineno, link, dest in archived:
            print(f"  {path}:{lineno}  {link} -> {dest}")
        print("  Fix the prose, repoint the link, or accept it knowingly.")
    if not broken and not archived:
        print("All wiki links resolve, none into Archive/.")
    elif not broken:
        print("\nNo broken links.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
