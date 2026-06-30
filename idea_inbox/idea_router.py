"""idea_inbox/idea_router.py — Idea action routing for auideabot (personal repo).

Handles 執行/研究/刪除 idea row N with preview + confirm/cancel flow.
Pending actions stored in "Agent Pending" tab on the shared Master Sheet.
"""
from __future__ import annotations

import json
import re
import time
import uuid

MASTER_SHEET_ID = "153iv2oll2GGHy0XgJHCqUAcWzhSPoeYD9lBX9YFsNew"
_PENDING_TAB = "Agent Pending"
_PENDING_HEADER = ["pid", "tool", "args_json", "preview", "ts"]
PENDING_TTL = 300

_pending: dict[str, dict] = {}


def _get_or_create_ws(gc, tab: str, header: list[str]):
    sh = gc.open_by_key(MASTER_SHEET_ID)
    try:
        return sh.worksheet(tab)
    except Exception:
        ws = sh.add_worksheet(title=tab, rows=200, cols=len(header))
        ws.append_row(header)
        return ws


def _load_pending(gc):
    try:
        ws = _get_or_create_ws(gc, _PENDING_TAB, _PENDING_HEADER)
        for row in ws.get_all_records():
            pid = str(row.get("pid", "")).strip()
            if not pid or pid in _pending:
                continue
            try:
                args = json.loads(row.get("args_json") or "{}")
            except Exception:
                args = {}
            _pending[pid] = {
                "tool": row.get("tool", ""),
                "args": args,
                "preview": row.get("preview", ""),
                "ts": float(row.get("ts") or 0),
            }
    except Exception:
        pass


def _save_pending(gc):
    try:
        ws = _get_or_create_ws(gc, _PENDING_TAB, _PENDING_HEADER)
        rows = [_PENDING_HEADER]
        for pid, entry in _pending.items():
            args = {k: v for k, v in entry["args"].items() if k != "gc"}
            rows.append([pid, entry["tool"], json.dumps(args, ensure_ascii=False), entry["preview"], entry["ts"]])
        ws.clear()
        ws.update("A1", rows)
    except Exception:
        pass


def _new_pending(gc, tool: str, args: dict, preview: str) -> str:
    now = time.time()
    _pending.clear()  # clear expired (serverless — only keep latest)
    pid = str(uuid.uuid4())
    _pending[pid] = {"tool": tool, "args": {k: v for k, v in args.items() if k != "gc"}, "preview": preview, "ts": now}
    _save_pending(gc)
    return pid


def is_idea_action_text(text: str) -> bool:
    if not ("idea" in text.lower() or "個 idea" in text):
        return False
    has_row = bool(re.search(r'row\s*(\d+)|第\s*(\d+)\s*行', text, re.IGNORECASE))
    has_verb = any(k in text for k in ("刪", "刪除", "執行", "研究"))
    return has_row or has_verb


def route_idea_action(text: str, gc) -> tuple[str, str | None]:
    row_m = re.search(r'row\s*(\d+)|第\s*(\d+)\s*行', text, re.IGNORECASE)
    if not row_m:
        return "邊一行 idea？麻煩提供 row number（例如「刪除 idea row 23」）。", None
    row = int(row_m.group(1) or row_m.group(2))

    if any(k in text for k in ("刪", "刪除")):
        preview = f"將刪除 Idea Inbox row {row}（整行），確認？"
        pid = _new_pending(gc, "delete_idea", {"row": row}, preview)
        return preview, pid

    if "執行" in text:
        preview = f"將標記 Idea row {row} → 「執行」，確認？"
        pid = _new_pending(gc, "update_idea", {"row": row, "action": "執行"}, preview)
        return preview, pid

    if "研究" in text:
        preview = f"將標記 Idea row {row} → 「研究」，確認？"
        pid = _new_pending(gc, "update_idea", {"row": row, "action": "研究"}, preview)
        return preview, pid

    return "唔明你想做咩。試吓：刪除 / 執行 / 研究 idea row N。", None


def confirm_action(pending_id: str, gc) -> str:
    _load_pending(gc)
    entry = _pending.get(pending_id)
    if not entry:
        return "⚠️ 找不到待確認嘅操作（可能已過期）。"

    tool = entry["tool"]
    args = entry["args"]

    try:
        if tool == "delete_idea":
            from idea_inbox.idea_review import delete_idea
            delete_idea(gc, args["row"])
            result = f"✅ 已刪除 Idea row {args['row']}。"
        elif tool == "update_idea":
            from idea_inbox.idea_review import update_idea
            update_idea(gc, args["row"], args.get("action", "執行"))
            result = f"✅ Idea row {args['row']} 已標記為「{args.get('action', '執行')}」。"
        else:
            result = f"⚠️ 未知操作 {tool}。"
    except Exception as e:
        result = f"❌ 執行失敗：{e}"

    del _pending[pending_id]
    _save_pending(gc)
    return result


def cancel_action(pending_id: str, gc) -> str:
    _load_pending(gc)
    if pending_id in _pending:
        del _pending[pending_id]
        _save_pending(gc)
    return "❌ 已取消。"
