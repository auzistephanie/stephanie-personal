"""scripts/idea_digest.py — Weekly Idea Inbox digest via Telegram.

Sends a summary of pending ideas to the VNX Telegram chat every Thursday 11am.
After a Cowork review session, send_review_summary() sends results via auideabot.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from core.sheets_client import get_gc
from core.idea_review import get_pending_ideas, get_research_ideas, purge_old_deleted_ideas


def _load_idea_bot_creds() -> tuple[str, str]:
    """Return (bot_token, chat_id) for auideabot from env or secrets.toml [idea_bot]."""
    token = os.environ.get("IDEA_BOT_TOKEN", "")
    chat_id = os.environ.get("IDEA_CHAT_ID", "")

    if not token or not chat_id:
        try:
            import sys as _sys
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _secrets_path = os.path.join(_root, ".streamlit", "secrets.toml")
            if _sys.version_info >= (3, 11):
                import tomllib as _tomllib
            else:
                try:
                    import tomllib as _tomllib
                except ImportError:
                    import tomli as _tomllib
            with open(_secrets_path, "rb") as _f:
                _s = _tomllib.load(_f)
            _ib = _s.get("idea_bot", {})
            token = token or _ib.get("bot_token", "")
            chat_id = chat_id or _ib.get("chat_id", "")
        except Exception as _e:
            print(f"[idea_digest] Could not load secrets.toml: {_e}")

    return token, chat_id


def send_idea_bot_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message via auideabot (idea_bot credentials). Used for all Idea Inbox notifications."""
    token, chat_id = _load_idea_bot_creds()
    if not token or not chat_id:
        print("IDEA_BOT_TOKEN or IDEA_CHAT_ID not set — skipping Telegram")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        if not resp.ok:
            print(f"[idea_digest] ⚠️ Failed: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as e:
        print(f"[idea_digest] ⚠️ Error: {e}")
        return False


def send_review_summary(results: list[dict]) -> None:
    """Send idea review summary back via auideabot after a Cowork session.

    Each item in results: {"category": str, "message": str, "action": str, "action_plan": str}
    """
    token, chat_id = _load_idea_bot_creds()
    if not token or not chat_id:
        print("IDEA_BOT_TOKEN or IDEA_CHAT_ID not set — skipping Telegram")
        return

    groups = {"go": [], "deep dive": [], "hold": [], "archive": []}
    for r in results:
        action = r.get("action", "archive")
        if action == "research":
            action = "deep dive"
        groups.get(action, groups["archive"]).append(r)

    lines = [f"✅ <b>Idea Inbox Review 完成</b>\n共 {len(results)} 個 ideas 已處理"]

    icons = {"go": "📋 <b>Go — 已傾完", "deep dive": "🔍 <b>Explore",
             "hold": "⏸️ <b>Hold", "archive": "🗄️ <b>Archive"}

    for action, icon in icons.items():
        items = groups[action]
        if not items:
            continue
        lines.append(f"\n{icon} ({len(items)}):</b>")
        for item in items:
            preview = item["message"][:60].replace("<", "&lt;").replace(">", "&gt;")
            if len(item["message"]) > 60:
                preview += "…"
            plan_line = item.get("action_plan", "").split("\n")[0]  # first line only
            lines.append(f"• [{item['category']}] {preview}")
            if plan_line and action in ("go", "deep dive"):
                lines.append(f"  → {plan_line}")

    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "HTML"},
        timeout=10,
    )
    print(f"Review summary sent via auideabot: {len(results)} ideas")


def main():
    gc = get_gc()
    try:
        purged = purge_old_deleted_ideas(gc, days=30)
        if purged:
            print(f"已清除 {purged} 個超過 30 日嘅 Deleted Ideas")
    except Exception as e:
        print(f"[idea_digest] purge_old_deleted_ideas 失敗: {e}")

    pending = get_pending_ideas(gc, include_message=True)
    research = get_research_ideas(gc)

    if not pending and not research:
        send_idea_bot_message("💡 <b>Idea Inbox</b>\n\n冇 pending ideas，inbox 係空嘅！")
        try:
            from core import heartbeat
            heartbeat.beat(gc, "idea-inbox-digest")
        except Exception:
            pass
        return

    if pending and research:
        header = f"💡 <b>Idea Inbox — {len(pending)} 個 pending + {len(research)} 條 Research 等你 review</b>"
    elif pending:
        header = f"💡 <b>Idea Inbox — {len(pending)} 個 pending ideas 等你 review</b>"
    else:
        header = f"💡 <b>Idea Inbox — {len(research)} 條 Research ideas 等你 Explore</b>"

    lines = [header, ""]

    for idea in pending[:5]:
        preview = idea["message"][:60].replace("<", "&lt;").replace(">", "&gt;")
        if len(idea["message"]) > 60:
            preview += "…"
        lines.append(f"• {preview}")
    if len(pending) > 5:
        lines.append(f"• …（仲有 {len(pending) - 5} 個）")

    if research:
        lines.append(f"\n🔍 <b>Research Backlog ({len(research)} 條)</b> — Explore 已準備好")

    lines.append('\n喺 Cowork 叫「review ideas」開始！')
    send_idea_bot_message("\n".join(lines))
    print(f"Digest sent: {len(pending)} pending, {len(research)} research ideas")
    try:
        from core import heartbeat
        heartbeat.beat(gc, "idea-inbox-digest")
    except Exception:
        pass


if __name__ == "__main__":
    main()
