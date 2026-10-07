#!/usr/bin/env python3
"""Check that every [[wiki link]] in the vault resolves to a note.

Run from anywhere: python3 Scripts/check_wiki_links.py [--archived]
Exit code 0 = no broken links; 1 = broken links found.

BROKEN   — the link resolves to nothing. Always an error: fix the link or create the note.
ARCHIVED — the link resolves, but only to a note under an `Archive/` folder, from a live note.
           Usually fine: a dated history line about a finished task points at it. Counted, not
           listed; --archived lists them for a tidy-up.

Rules (matching Obsidian's resolution):
- [[Name]] resolves if any .md file in the vault is named "Name.md" (case-insensitive).
- [[Name|alias]] and [[Name#heading]] resolve on the part before | or #.
- [[path/To/Name]] resolves on the last path segment.
- [[Name.base]] and [[Name.base#View]] resolve to an Obsidian Bases file.
- Links inside fenced code blocks and inline `code spans` are ignored: that's where
  examples live.
- A file whose frontmatter carries `link-check: skip` is ignored entirely. That is for
  sources kept word for word (pasted articles, transcripts) whose [[links]] are not ours to fix.

A link only resolves if a note with that exact filename exists, so a rename or a typo
silently breaks every link to it. This catches that.
"""

import argparse
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent      # the folder above Scripts/
SKIP_DIRS = {".git", ".obsidian", ".claude"}

LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
SKIP_MARKER = "link-check: skip"
INLINE_CODE_RE = re.compile(r"`[^`]*`")
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def _files(root: Path, pattern: str):
    return (p for p in root.rglob(pattern) if not any(part in SKIP_DIRS for part in p.relative_to(root).parts))


def note_index(root: Path) -> dict[str, list[Path]]:
    """Map lowercase note name -> every file with that name (a name can repeat)."""
    idx: dict[str, list[Path]] = {}
    for p in _files(root, "*.md"):
        idx.setdefault(p.stem.lower(), []).append(p)
    for p in _files(root, "*.base"):
        idx.setdefault(p.name.lower(), []).append(p)   # [[Tasks.base#View]] -> "tasks.base"
    return idx


def is_archived(p: Path, root: Path) -> bool:
    """True if the note sits under an Archive/ folder at any depth."""
    return "Archive" in p.relative_to(root).parts[:-1]


def target_of(link: str) -> str:
    target = link.split("|")[0].split("#")[0].strip()
    return target.split("/")[-1]                    # path-style links resolve on the final segment


def is_skipped(text: str) -> bool:
    """True if the file's frontmatter carries `link-check: skip`."""
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    return end != -1 and SKIP_MARKER in text[:end]


def scan(root: Path = VAULT) -> tuple[list, list]:
    """([(file, line, link)] broken, [(file, line, link, target)] pointing only into Archive/)."""
    idx = note_index(root)
    broken, archived = [], []
    for p in sorted(_files(root, "*.md")):
        text = p.read_text(encoding="utf-8")
        if is_skipped(text):
            continue
        source_is_live = not is_archived(p, root)
        fence = None                                # (char, length) of the open fence, else None
        for lineno, line in enumerate(text.splitlines(), 1):
            m_fence = FENCE_RE.match(line.strip())
            if m_fence:
                marker = m_fence.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1]:
                    fence = None                    # closes only on the same char, at least as long
                continue
            if fence is not None:
                continue
            line = INLINE_CODE_RE.sub("", line)
            for m in LINK_RE.finditer(line):
                target = target_of(m.group(1))
                if not target:                      # [[#heading]], a link within the same note
                    continue
                matches = idx.get(target.lower())
                rel = p.relative_to(root).as_posix()
                if not matches:
                    broken.append((rel, lineno, m.group(0)))
                elif source_is_live and all(is_archived(t, root) for t in matches):
                    archived.append((rel, lineno, m.group(0), matches[0].relative_to(root).as_posix()))
    return broken, archived


def main(argv=None, root: Path = VAULT) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archived", action="store_true", help="list links that point only into Archive/")
    args = ap.parse_args(argv)
    broken, archived = scan(root)
    if broken:
        print(f"BROKEN LINKS: {len(broken)}")
        for path, lineno, link in broken:
            print(f"  {path}:{lineno}  {link}")
    if archived and args.archived:
        print(f"\nARCHIVED TARGETS: {len(archived)} (the link resolves, but only into Archive/)")
        for path, lineno, link, dest in archived:
            print(f"  {path}:{lineno}  {link} -> {dest}")
    elif archived:
        n = len(archived)
        print(f"{n} link{' points' if n == 1 else 's point'} into Archive/. That's normal for history lines; "
              "--archived lists them.")
    if not broken:
        print("No broken links.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
