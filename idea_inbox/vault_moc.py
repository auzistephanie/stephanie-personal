#!/usr/bin/env python3
"""Regenerate 00-MOC/*.md from current vault contents.

Called automatically by weekly_reflection.py (every Friday).
Also callable manually: python3 idea_inbox/vault_moc.py
"""
from __future__ import annotations
import pathlib
import re
from datetime import datetime, timedelta

_ROOT = pathlib.Path(__file__).parent.parent
VAULT_ROOT = _ROOT / "obsidian-vault"
MOC_DIR = VAULT_ROOT / "00-MOC"
_TODAY = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")

_CATEGORY_LABELS = {
    "AI":     "AI 工具評估",
    "Tool":   "工具評估",
    "Method": "方法論",
}


def _read_note(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")

    # frontmatter
    fm: dict[str, str] = {}
    fm_m = re.match(r"^---\n(.+?)\n---\n", text, re.DOTALL)
    if fm_m:
        for line in fm_m.group(1).split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()

    # title: first # heading, fallback to filename stem
    title_m = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem

    # one-line summary: first non-empty content line after the title heading
    summary = ""
    in_fm = False
    found_title = False
    for line in text.split("\n"):
        if line.strip() == "---":
            in_fm = not in_fm
            continue
        if in_fm:
            continue
        if line.startswith("# "):
            found_title = True
            continue
        if found_title and line.strip() and not line.startswith("#"):
            summary = line.strip()[:80]
            break

    # unchecked todo items
    pending = re.findall(r"^- \[ \] (.+)$", text, re.MULTILINE)

    return {
        "path":     path,
        "stem":     path.stem,
        "title":    title,
        "category": fm.get("category", ""),
        "date":     fm.get("date", ""),
        "summary":  summary,
        "pending":  pending,
        "text":     text,
    }


def _list_notes(folder: pathlib.Path) -> list[dict]:
    if not folder.exists():
        return []
    return [_read_note(f) for f in sorted(folder.glob("*.md"))]


def _footer() -> str:
    return f"\n---\n*最後更新：{_TODAY} | 自動由 vault_moc.py 生成*\n"


# ── MOC builders ─────────────────────────────────────────────────────────────

def _build_個人學習_moc(notes: list[dict]) -> str:
    groups: dict[str, list] = {}
    for n in notes:
        groups.setdefault(n["category"] or "其他", []).append(n)

    lines = ["# 個人學習 MOC", "", "> 所有 AI / tech 工具評估、方法論筆記嘅索引。", ""]

    for cat, cat_notes in sorted(groups.items()):
        label = _CATEGORY_LABELS.get(cat, cat)
        lines += [f"## {label}", ""]
        for n in cat_notes:
            lines.append(f"- [[{n['stem']}]] — {n['summary'] or '—'}")
        lines.append("")

    pending_lines = [
        f"- [ ] {p}（來自 [[{n['stem']}]]）"
        for n in notes for p in n["pending"]
    ]
    if pending_lines:
        lines += ["## 未完成 Commitments", ""] + pending_lines + [""]

    return "\n".join(lines) + _footer()


def _build_每週反思_moc(notes: list[dict]) -> str:
    lines = [
        "# 每週反思 MOC", "",
        "> 所有每週反思筆記索引。最新嘅喺最頂。", "",
        "## 反思筆記（新 → 舊）", "",
    ]
    for n in reversed(notes):
        week_m = re.search(r"W\d+[^)]*\)", n["text"])
        week_info = f" — {week_m.group(0)}" if week_m else ""
        lines.append(f"- [[{n['stem']}]]{week_info}")
    lines.append("")

    pending_lines = [
        f"- [ ] {p}（來自 [[{n['stem']}]]）"
        for n in notes for p in n["pending"]
    ]
    if pending_lines:
        lines += ["## 持續未完成 Commitments（跨週）", ""] + pending_lines + [""]

    return "\n".join(lines) + _footer()


def _build_買樓裝修_moc(personal: list[dict], renovation: list[dict]) -> str:
    all_notes = personal + [n for n in renovation if n["stem"] != "README"]

    lines = [
        "# 買樓裝修 MOC", "",
        "> 長沙灣麗玥苑置業 + 裝修規劃嘅所有記錄索引。", "",
        "## 主要記錄", "",
    ]
    for n in all_notes:
        lines.append(f"- [[{n['stem']}]] — {n['summary'] or '—'}")
    lines += [
        "",
        "## 決策記錄", "",
        "*(每次新決定 → 照 `00-Templates/買樓裝修決定.md` template 建 note，放 `03-買樓裝修/`)*",
        "",
    ]

    pending_lines = [
        f"- [ ] {p}（來自 [[{n['stem']}]]）"
        for n in all_notes for p in n["pending"]
    ]
    if pending_lines:
        lines += ["## 未完成 Commitments", ""] + pending_lines + [""]

    return "\n".join(lines) + _footer()


# ── Public API ────────────────────────────────────────────────────────────────

def update_all_moc() -> dict[str, int]:
    """Regenerate all MOC pages. Returns {moc_name: note_count}."""
    MOC_DIR.mkdir(parents=True, exist_ok=True)

    learning = _list_notes(VAULT_ROOT / "個人學習")
    (MOC_DIR / "個人學習 MOC.md").write_text(_build_個人學習_moc(learning), encoding="utf-8")

    reflections = _list_notes(VAULT_ROOT / "04-每週反思")
    (MOC_DIR / "每週反思 MOC.md").write_text(_build_每週反思_moc(reflections), encoding="utf-8")

    personal    = _list_notes(VAULT_ROOT / "02-個人")
    renovation  = _list_notes(VAULT_ROOT / "03-買樓裝修")
    (MOC_DIR / "買樓裝修 MOC.md").write_text(
        _build_買樓裝修_moc(personal, renovation), encoding="utf-8"
    )

    return {
        "個人學習 MOC":  len(learning),
        "每週反思 MOC":  len(reflections),
        "買樓裝修 MOC":  len(personal) + len(renovation),
    }


if __name__ == "__main__":
    results = update_all_moc()
    for name, count in results.items():
        print(f"✅ {name}: {count} notes")
