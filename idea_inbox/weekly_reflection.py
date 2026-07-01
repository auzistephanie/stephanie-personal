#!/usr/bin/env python3
"""
scripts/weekly_reflection.py — 每週五自動生成反思草稿

流程：
1. 收集本週 Idea Inbox 新 ideas
2. 掃描本週新增嘅 Obsidian notes
3. LLM 生成反思草稿
4. 寫入 04-每週反思/YYYY-MM-DD [週題].md
5. Telegram 通知

排程：每週五 17:00 HKT（Cowork scheduled task）
"""
from __future__ import annotations
import os
import sys
import pathlib
from datetime import datetime, timedelta, date

_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# ── Config ────────────────────────────────────────────────────────────────────

VAULT_PATH = _ROOT / "obsidian-vault" / "04-每週反思"
VAULT_PATH.mkdir(parents=True, exist_ok=True)

OBSIDIAN_ROOT = _ROOT / "obsidian-vault"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _hkt_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=8)


def _week_range() -> tuple[date, date]:
    today = _hkt_now().date()
    mon = today - timedelta(days=today.weekday())
    fri = mon + timedelta(days=4)
    return mon, fri


def _get_this_week_ideas(gc) -> list[str]:
    """Get ideas added to Idea Inbox this week."""
    from core.config import MASTER_SHEET_ID
    mon, fri = _week_range()
    try:
        ws = gc.open_by_key(MASTER_SHEET_ID).worksheet("Idea Inbox")
        rows = ws.get_all_values()
        ideas = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            try:
                # Date format: dd/mm/yyyy HH:MM
                d = datetime.strptime(row[0].strip()[:10], "%d/%m/%Y").date()
                if mon <= d <= fri:
                    msg = row[1].strip()[:100] if len(row) > 1 else ""
                    cat = row[5].strip() if len(row) > 5 else ""
                    if msg:
                        ideas.append(f"[{cat}] {msg}" if cat else msg)
            except Exception:
                continue
        return ideas[:10]
    except Exception as e:
        print(f"[weekly_reflection] ideas error: {e}")
        return []


def _get_new_obsidian_notes() -> list[str]:
    """Scan all vault folders for notes created/modified this week."""
    mon, _ = _week_range()
    notes = []
    for folder in OBSIDIAN_ROOT.iterdir():
        if not folder.is_dir() or folder.name.startswith("0"):
            continue
        for f in folder.glob("*.md"):
            try:
                mtime = date.fromtimestamp(f.stat().st_mtime)
                if mtime >= mon:
                    notes.append(f"{folder.name}/{f.stem}")
            except Exception:
                continue
    # Also check 01-工作, 02-個人, 04-貓貓健康
    for folder_name in ["01-工作", "02-個人", "04-貓貓健康"]:
        folder = OBSIDIAN_ROOT / folder_name
        if not folder.exists():
            continue
        for f in folder.glob("*.md"):
            try:
                mtime = date.fromtimestamp(f.stat().st_mtime)
                if mtime >= mon:
                    name = f"{folder_name}/{f.stem}"
                    if name not in notes:
                        notes.append(name)
            except Exception:
                continue
    return notes[:10]


def _generate_draft(ideas: list[str], notes: list[str]) -> tuple[str, str]:
    """Use LLM to generate a weekly title + reflection draft in Cantonese.

    Returns (title, draft) where title is a short 4-8 char Cantonese phrase
    summarising the week's highlight, used as the filename.
    """
    import requests

    ideas_text = "\n".join(f"- {i}" for i in ideas) if ideas else "（本週冇新 idea）"
    notes_text = "\n".join(f"- {n}" for n in notes) if notes else "（本週冇新 note）"

    prompt = (
        "你係 Stephanie 嘅個人助手。佢係 Venturenix Lab 嘅 Operations Executive，"
        "同時喺規劃 2027 年置業裝修。\n\n"
        f"本週 Idea Inbox 新增嘅 ideas：\n{ideas_text}\n\n"
        f"本週新增嘅 Obsidian notes：\n{notes_text}\n\n"
        "根據以上資料，用廣東話輸出以下兩部分（嚴格按格式，唔好多餘前言）：\n\n"
        "TITLE: [4-8字廣東話，概括呢週最重要嘅事或主題，例如：拍板兩大 idea、完成裝修報價]\n\n"
        "DRAFT:\n"
        "**做得好嘅 👍**\n"
        "1. [從 ideas/notes 提煉，1-3點]\n\n"
        "**做漏咗 / 可以更好嘅 😅**\n"
        "1. [建議性提醒，1-2點]\n\n"
        "**下週重點**\n"
        "- [ ] [根據未完成/新 idea 建議，1-3項]\n\n"
        "**本週決策回顧**\n"
        "[簡短總結本週重要決定，1-2句]"
    )

    def _parse(text: str) -> tuple[str, str]:
        lines = text.strip().splitlines()
        title = ""
        draft_lines = []
        in_draft = False
        for line in lines:
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("DRAFT:"):
                in_draft = True
            elif in_draft:
                draft_lines.append(line)
        draft = "\n".join(draft_lines).strip()
        return title or "週記", draft or "（LLM 未能生成草稿，請自行填寫）"

    # Try OpenRouter first, then DeepSeek
    try:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "google/gemini-2.5-flash-lite", "max_tokens": 700,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            if resp.ok:
                return _parse(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[weekly_reflection] OpenRouter error: {e}")

    try:
        import tomli
        p = pathlib.Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
        with open(p, "rb") as f:
            ds_key = tomli.load(f).get("deepseek", {}).get("api_key", "")
        if ds_key:
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {ds_key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "max_tokens": 700,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            if resp.ok:
                return _parse(resp.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[weekly_reflection] DeepSeek error: {e}")

    return "週記", "（LLM 未能生成草稿，請自行填寫）"


def _write_note(title: str, draft: str) -> pathlib.Path:
    """Write the reflection note to 04-每週反思/, filename based on week title."""
    today = _hkt_now().date()
    mon, fri = _week_range()
    week_num = today.isocalendar()[1]
    # Sanitise title for filename (remove chars unsafe on most filesystems)
    safe_title = title.replace("/", "／").replace("\\", "").replace(":", "：").strip()
    filename = f"{today.strftime('%Y-%m-%d')} {safe_title}.md"
    filepath = VAULT_PATH / filename

    content = (
        f"---\n"
        f"date: {today}\n"
        f"week: W{week_num} ({mon.strftime('%-d %b')}–{fri.strftime('%-d %b')})\n"
        f"tags: [週記]\n"
        f"---\n\n"
        f"# {safe_title} — W{week_num} ({mon.strftime('%-d %b')}–{fri.strftime('%-d %b')})\n\n"
        f"{draft}\n\n"
        f"---\n"
        f"*草稿由 Claude 根據本週 Idea Inbox + Obsidian notes 自動生成，請自行修改。*\n"
    )
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _obsidian_link(filepath: pathlib.Path) -> str:
    """Generate an obsidian:// deep link using the canonical vault+file format.

    唔靠絕對路徑（跨機／split 後絕對路徑會對唔上），改用 vault 名 + vault 內相對
    路徑，只要 Obsidian 有個叫 obsidian-vault 嘅 vault 就開得到。
    """
    from urllib.parse import quote
    vault = "obsidian-vault"
    try:
        rel = filepath.resolve().relative_to(OBSIDIAN_ROOT.resolve())
    except ValueError:
        rel = pathlib.Path(filepath.name)
    rel_str = str(rel.with_suffix(""))  # Obsidian 唔需要 .md 後綴
    return f"obsidian://open?vault={quote(vault, safe='')}&file={quote(rel_str, safe='')}"


def _send_telegram(filepath: pathlib.Path) -> None:
    """Send Telegram notification with a clickable Obsidian deep link."""
    import requests as req
    try:
        import tomli
        p = pathlib.Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
        with open(p, "rb") as f:
            secrets = tomli.load(f)
        token = os.environ.get("IDEA_BOT_TOKEN") or secrets.get("idea_bot", {}).get("bot_token", "")
        chat_id = os.environ.get("IDEA_CHAT_ID") or secrets.get("idea_bot", {}).get("chat_id", "")
        if not token or not chat_id:
            print("[weekly_reflection] Telegram token/chat_id not found")
            return
        link = _obsidian_link(filepath)
        msg = (
            f"📝 <b>週記草稿已建好！</b>\n\n"
            f"📂 {filepath.name}\n\n"
            f'<a href="{link}">✏️ 喺 Obsidian 打開修改</a>'
        )
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10,
        )
    except Exception as e:
        print(f"[weekly_reflection] Telegram error: {e}")


def main():
    from core.sheets_client import get_gc
    gc = get_gc()

    print("📊 收集本週資料...")
    ideas = _get_this_week_ideas(gc)
    notes = _get_new_obsidian_notes()
    print(f"  Ideas: {len(ideas)} 條")
    print(f"  New notes: {len(notes)} 個")

    print("✍️  生成週記草稿...")
    title, draft = _generate_draft(ideas, notes)
    print(f"  週題：{title}")

    print("💾 寫入 Obsidian...")
    filepath = _write_note(title, draft)
    print(f"  ✅ {filepath}")

    print("📱 發送 Telegram 通知...")
    _send_telegram(filepath)

    print("🗺️  更新 MOC 頁...")
    try:
        from idea_inbox.vault_moc import update_all_moc
        moc_results = update_all_moc()
        for name, count in moc_results.items():
            print(f"  ✅ {name}: {count} notes")
    except Exception as e:
        print(f"  ⚠️  MOC update failed: {e}")

    print("✅ 完成！")
    try:
        from core import heartbeat
        heartbeat.beat(gc, "weekly-reflection")
    except Exception:
        pass


if __name__ == "__main__":
    main()
