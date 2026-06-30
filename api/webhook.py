"""stephanie-personal — Idea Inbox Telegram Webhook (Vercel + Flask)

Required env vars:
    IDEA_BOT_TOKEN            — auideabot token
    IDEA_CHAT_ID              — Telegram chat ID for auideabot
    GCP_SERVICE_ACCOUNT_JSON  — Full service account JSON string
    MASTER_SHEET_ID           — Google Sheet ID (default hardcoded)
    DEEPSEEK_API_KEY          — DeepSeek API key
"""
from __future__ import annotations
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

import requests
from flask import Flask, jsonify, request

from core.sheets_client import get_gc

app = Flask(__name__)

_IDEA_KEYBOARD = {
    "keyboard": [
        [{"text": "/last"}, {"text": "/list"}, {"text": "/pending"}],
        [{"text": "/stats"}, {"text": "/digest"}, {"text": "/search"}],
        [{"text": "/ainews"}, {"text": "/deep"}, {"text": "/help"}],
    ],
    "resize_keyboard": True,
    "persistent": True,
}


def _send_idea(chat_id: int | str, text: str, parse_mode: str = "HTML", reply_markup=None) -> None:
    token = os.environ.get("IDEA_BOT_TOKEN", "")
    if not token:
        return
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=payload,
        timeout=10,
    )


_PREAMBLE_KW = ("截圖", "呢張", "以下", "以上", "用廣東話", "以下幾點", "內容係關於", "呢個 idea")

_ERROR_KW = (
    "traceback", "exception", "error:", "raise ", "modulenotfounderror",
    "importerror", "typeerror", "attributeerror", "syntaxerror", "valueerror",
    "keyerror", "runtimeerror", "stacktrace", "critical", "fatal", "500 internal",
)


def _is_error_screenshot(description: str, caption: str = "") -> bool:
    combined = (description + " " + caption).lower()
    return sum(1 for kw in _ERROR_KW if kw in combined) >= 2


def _obsidian_folder(category: str) -> str:
    if category in ("ClaudeCode", "AI", "Tool", "Content", "Automation"):
        return "📂 個人學習 #learning"
    if category in ("Business",):
        return "📂 Venturenix"
    return "📂 02-個人 #個人"


def _img_short_preview(msg: str, max_chars: int = 120) -> str:
    m = re.search(r'主題[：:]\s*(.+?)(?:\n|$)', msg)
    if m:
        return f"[圖片] {m.group(1).strip()[:max_chars]}"
    for line in msg.splitlines():
        line = re.sub(r'\*+', '', line).strip().lstrip("•").strip()
        if len(line) > 10 and not any(kw in line for kw in _PREAMBLE_KW):
            return f"[圖片] {line[:max_chars]}"
    return msg[:max_chars]


def _img_full_body(msg: str, max_chars: int = 900) -> str:
    lines, skip = [], True
    for line in msg.splitlines():
        cleaned = re.sub(r'\*+', '', line).strip().lstrip("•").strip()
        if skip:
            if not cleaned or any(kw in cleaned for kw in _PREAMBLE_KW):
                continue
            skip = False
        if cleaned:
            lines.append(cleaned)
    body = "\n".join(lines)[:max_chars]
    return body or msg[:max_chars]


def _esc(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _get_ai_news(gc, date_str: str | None = None) -> list[dict]:
    """Read AI News tab — returns today's entries (or latest if date_str given)."""
    from datetime import datetime, timedelta
    if date_str is None:
        date_str = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")
    try:
        from core.config import MASTER_SHEET_ID
        ws = gc.open_by_key(MASTER_SHEET_ID).worksheet("AI News")
        rows = ws.get_all_values()
        news = []
        for row in rows[1:]:
            if len(row) >= 2 and row[0].startswith(date_str):
                news.append({
                    "title":     row[1] if len(row) > 1 else "",
                    "source":    row[2] if len(row) > 2 else "",
                    "tag":       row[3] if len(row) > 3 else "",
                    "relevance": row[4] if len(row) > 4 else "",
                    "summary":   row[5] if len(row) > 5 else "",
                    "purpose":   row[6] if len(row) > 6 else "",
                    "url":       row[7] if len(row) > 7 else "",
                })
        return news[:5]
    except Exception:
        return []


def _handle_idea_cmd(chat_id: int | str, cmd: str, args: list[str], gc) -> None:
    from idea_inbox.idea_review import (
        get_pending_count, get_pending_ideas, get_recent_ideas,
        get_last_idea, get_stats, search_ideas,
    )

    if cmd in ("/help", "/start"):
        _send_idea(chat_id, (
            "💡 <b>Idea Inbox Bot</b>\n\n"
            "直接 send 文字或截圖即存！\n\n"
            "<b>Commands：</b>\n"
            "/last — 最後一條 idea\n"
            "/list — 最近 5 條 ideas\n"
            "/pending — Pending review 數量\n"
            "/stats — 各 category 統計\n"
            "/digest — 手動觸發 digest\n"
            "/search 關鍵字 — 搜尋 ideas\n"
            "/ainews — 今日 AI News（每朝 9:10 自動抓取）\n"
            "/deep — Research 列表\n"
            "/deep N — Explore 第 N 條\n"
            "/help — 顯示呢個訊息\n\n"
            "<b>✅ Idea 操作</b>（會先 preview，按確認先執行）\n"
            "• 執行 / 研究 / 刪除 idea row [N]\n"
            "  例：刪除 idea row 23"
        ), reply_markup=_IDEA_KEYBOARD)

    elif cmd == "/last":
        idea = get_last_idea(gc)
        if not idea:
            _send_idea(chat_id, "💡 Inbox 係空嘅！")
            return
        msg = idea["message"]
        body = _esc(_img_full_body(msg)) if msg.startswith("[圖片]") else _esc(msg[:900])
        status_icon = "⏳" if idea["status"] == "pending" else "✅"
        _send_idea(chat_id, (
            f"💡 <b>最後一條 Idea</b> {status_icon}\n\n"
            f"📅 {idea['date']}\n"
            f"🏷️ {idea['category']}\n\n"
            f"{body}"
        ))

    elif cmd == "/list":
        ideas = get_recent_ideas(gc, 5)
        if not ideas:
            _send_idea(chat_id, "💡 Inbox 係空嘅！")
            return
        lines = ["💡 <b>最近 5 條 Ideas</b>\n"]
        for idea in reversed(ideas):
            msg = idea["message"]
            preview = _esc(_img_short_preview(msg, 100)) if msg.startswith("[圖片]") else _esc(msg[:100]) + ("…" if len(msg) > 100 else "")
            icon = "⏳" if idea["status"] == "pending" else "✅"
            lines.append(f"{icon} [{idea['category']}] {preview}")
        _send_idea(chat_id, "\n".join(lines))

    elif cmd == "/pending":
        count = get_pending_count(gc)
        if count == 0:
            _send_idea(chat_id, "✅ 冇 pending ideas，inbox 係空嘅！")
        else:
            _send_idea(chat_id, f"⏳ 有 <b>{count}</b> 個 ideas 等緊 review\n\n週四 11am 會自動發 digest！")

    elif cmd == "/stats":
        stats = get_stats(gc)
        if not stats:
            _send_idea(chat_id, "💡 Inbox 係空嘅！")
            return
        total = sum(stats.values())
        lines = [f"📊 <b>Idea Inbox 統計</b>（共 {total} 條）\n"]
        for cat, count in stats.items():
            lines.append(f"• {cat}: {count}")
        _send_idea(chat_id, "\n".join(lines))

    elif cmd == "/digest":
        pending = get_pending_ideas(gc)
        if not pending:
            _send_idea(chat_id, "💡 冇 pending ideas，inbox 係空嘅！")
            return
        lines = [f"💡 <b>Idea Inbox — {len(pending)} 個 pending ideas 等你 review</b>\n"]
        for idea in pending[:5]:
            msg = idea["message"]
            preview = _esc(_img_short_preview(msg, 80)) if msg.startswith("[圖片]") else _esc(msg[:80]) + ("…" if len(msg) > 80 else "")
            lines.append(f"• [{idea['category']}] {preview}")
        if len(pending) > 5:
            lines.append(f"• …（仲有 {len(pending) - 5} 個）")
        lines.append('\n喺 Cowork 叫「review ideas」開始 review！')
        _send_idea(chat_id, "\n".join(lines))

    elif cmd == "/deep":
        from idea_inbox.idea_inbox import generate_deep_dive
        from idea_inbox.idea_review import get_research_ideas, update_research_brief

        research = get_research_ideas(gc)
        if not research:
            _send_idea(chat_id, "🔍 冇 research ideas")
            return

        if not args:
            lines = [f"🔍 <b>Research</b>（共 {len(research)} 條）\n"]
            for i, idea in enumerate(reversed(research[-10:]), 1):
                msg = idea["message"]
                preview = _esc(_img_short_preview(msg, 80) if msg.startswith("[圖片]") else (msg[:80] + ("…" if len(msg) > 80 else "")))
                badge = " 📄" if idea.get("research_brief") else ""
                lines.append(f"{i}. [{idea['category']}] {preview}{badge}")
            lines.append("\n用 /deep N 做 Explore（📄 = 已有分析）")
            _send_idea(chat_id, "\n".join(lines))
            return

        try:
            n = int(args[0]) - 1
            ideas_list = list(reversed(research[-10:]))
            if n < 0 or n >= len(ideas_list):
                _send_idea(chat_id, f"❌ 請輸入 1–{len(ideas_list)} 之間嘅數字")
                return
            idea = ideas_list[n]
        except ValueError:
            _send_idea(chat_id, "❌ 請輸入數字，例如：/deep 2")
            return

        _send_idea(chat_id, "🔍 生成緊 Explore...")
        analysis = generate_deep_dive(idea["message"], idea["category"])
        update_research_brief(gc, idea["row"], f"[Explore]\n{analysis}")

        msg = idea["message"]
        title = _img_short_preview(msg, 60) if msg.startswith("[圖片]") else msg[:60]
        _send_idea(chat_id, (
            f"🔍 <b>Explore — [{idea['category']}]</b>\n"
            f"<i>{_esc(title)}{'…' if len(idea['message']) > 60 else ''}</i>\n\n"
            f"{_esc(analysis)}"
        ))

    elif cmd == "/ainews":
        news = _get_ai_news(gc)
        if not news:
            _send_idea(chat_id, (
                "📰 今日暫無 AI News\n\n"
                "每朝 9:10 自動抓取，若已過 9:10 仍無，可能今日冇相關新聞。"
            ))
            return
        lines = [f"📰 <b>今日 AI News</b>（{len(news)} 條）\n"]
        for i, n in enumerate(news, 1):
            tag = f"[{n['tag']}] " if n["tag"] else ""
            lines.append(f"{i}. {tag}<b>{_esc(n['title'])}</b>")
            if n["summary"]:
                lines.append(f"   {_esc(n['summary'][:120])}")
            if n["purpose"]:
                lines.append(f"   💡 {_esc(n['purpose'][:80])}")
            if n["url"]:
                lines.append(f"   🔗 {n['url']}")
            lines.append("")
        _send_idea(chat_id, "\n".join(lines).rstrip())

    elif cmd == "/search":
        if not args:
            _send_idea(chat_id, "🔍 請輸入關鍵字，例如：/search SleekFlow")
            return
        keyword = " ".join(args)
        results = search_ideas(gc, keyword)
        if not results:
            _send_idea(chat_id, f"🔍 搵唔到「{keyword}」相關嘅 ideas")
            return
        lines = [f"🔍 <b>搜尋「{keyword}」— {len(results)} 個結果</b>\n"]
        for idea in results:
            msg = idea["message"]
            preview = _esc(_img_short_preview(msg, 120)) if msg.startswith("[圖片]") else _esc(msg[:100]) + ("…" if len(msg) > 100 else "")
            status_icon = "⏳" if idea["status"] == "pending" else "✅"
            lines.append(f"{status_icon} [{idea['category']}] {preview}")
        _send_idea(chat_id, "\n".join(lines))

    else:
        _send_idea(chat_id, "❓ 未知指令。輸入 /help 睇所有 commands。")


@app.route("/api/idea/debug", methods=["GET"])
def idea_debug():
    return jsonify({
        "ok": True,
        "idea_bot_token_set": bool(os.environ.get("IDEA_BOT_TOKEN")),
        "master_sheet_id_set": bool(os.environ.get("MASTER_SHEET_ID")),
        "gcp_sa_set": bool(os.environ.get("GCP_SERVICE_ACCOUNT_JSON")),
    })


@app.route("/api/idea", methods=["POST"])
def idea_webhook():
    try:
        data = request.get_json(force=True, silent=True) or {}

        cb = data.get("callback_query")
        if cb:
            from idea_inbox.idea_router import confirm_action, cancel_action
            cb_chat_id = cb.get("message", {}).get("chat", {}).get("id")
            idea_chat_id = os.environ.get("IDEA_CHAT_ID", "")
            if idea_chat_id and str(cb_chat_id) != str(idea_chat_id):
                return jsonify({"ok": True})
            cb_action, pid = cb["data"].split(":", 1)
            gc = get_gc()
            result_msg = confirm_action(pid, gc) if cb_action == "confirm" else cancel_action(pid, gc)
            idea_token = os.environ.get("IDEA_BOT_TOKEN", "")
            requests.post(
                f"https://api.telegram.org/bot{idea_token}/answerCallbackQuery",
                json={"callback_query_id": cb["id"]},
                timeout=10,
            )
            requests.post(
                f"https://api.telegram.org/bot{idea_token}/editMessageText",
                json={
                    "chat_id": cb_chat_id,
                    "message_id": cb["message"]["message_id"],
                    "text": result_msg,
                },
                timeout=10,
            )
            return jsonify({"ok": True})

        msg = data.get("message") or data.get("edited_message")
        if not msg:
            return jsonify({"ok": True})

        chat_id = msg.get("chat", {}).get("id")
        gc = get_gc()

        from idea_inbox.idea_inbox import save_idea, get_tg_file_url, vision_describe, quick_mochi_take, upload_image_to_drive
        token = os.environ.get("IDEA_BOT_TOKEN", "")

        if msg.get("text"):
            text = msg["text"].strip()
            if text.startswith("/"):
                parts = text.split()
                cmd = parts[0].lower().split("@")[0]
                args = parts[1:]
                _handle_idea_cmd(chat_id, cmd, args, gc)
                return jsonify({"ok": True})

            from idea_inbox.idea_router import is_idea_action_text, route_idea_action
            if is_idea_action_text(text):
                preview, pid = route_idea_action(text, gc)
                if pid is None:
                    _send_idea(chat_id, preview)
                else:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": preview,
                            "reply_markup": {
                                "inline_keyboard": [[
                                    {"text": "✅ 確認", "callback_data": f"confirm:{pid}"},
                                    {"text": "❌ 取消", "callback_data": f"cancel:{pid}"},
                                ]]
                            },
                        },
                        timeout=10,
                    )
                return jsonify({"ok": True})

            category = save_idea(gc, text)
            mochi = quick_mochi_take(text, category)
            folder = _obsidian_folder(category)
            _send_idea(chat_id, f"✅ 已存入 Idea Inbox [{category}] → {folder}\n\n{mochi}")

        elif msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]
            caption = msg.get("caption", "")
            try:
                url = get_tg_file_url(token, file_id)
                description = vision_describe(url)

                full_text_nodrive = f"[圖片] {description}" + (f" | {caption}" if caption else "")

                if _is_error_screenshot(description, caption):
                    save_idea(gc, f"[Bug] {description[:500]}", note="error-screenshot")
                    _send_idea(chat_id, (
                        f"🐛 <b>偵測到 Error Screenshot</b>\n\n"
                        f"{_esc(description[:300])}\n\n"
                        f"✅ 已存入 Idea Inbox [Bug]"
                    ))
                    return jsonify({"ok": True})

                category, saved_row = save_idea(gc, full_text_nodrive, note="image", return_row=True)

                drive_url = ""
                try:
                    img_bytes = requests.get(url, timeout=20).content
                    drive_url = upload_image_to_drive(img_bytes, f"idea_{chat_id}_{file_id}.jpg", category=category)
                    if drive_url and saved_row:
                        from core.config import MASTER_SHEET_ID
                        from idea_inbox.idea_inbox import IDEA_INBOX_TAB
                        ws2 = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
                        ws2.update_cell(saved_row, 2, full_text_nodrive + f"\n{drive_url}")
                except Exception as up_e:
                    print(f"[idea_webhook] drive upload failed: {up_e}")

                full_text = full_text_nodrive + (f"\n{drive_url}" if drive_url else "")
                mochi = quick_mochi_take(full_text, category)
                folder = _obsidian_folder(category)
                _send_idea(chat_id, f"🖼️ <b>圖片內容</b>\n{_esc(description)}")
                _send_idea(chat_id, f"✅ 已存入 Idea Inbox [{category}] → {folder}\n\n{mochi}")
            except Exception as e:
                fallback = f"[圖片] {caption}" if caption else "[圖片] 未能讀取"
                save_idea(gc, fallback, note="image-error")
                err_msg = str(e)[:200]
                _send_idea(chat_id, f"⚠️ 圖片錯誤：{err_msg}")
                print(f"[idea_webhook] vision error: {e}")

        else:
            _send_idea(chat_id, "⚠️ 只支援文字或圖片，請重試")

    except Exception as e:
        print(f"[idea_webhook] error: {e}")

    return jsonify({"ok": True})
