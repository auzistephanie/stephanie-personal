"""core/idea_review.py — Idea Inbox review logic.

Reads pending ideas from Google Sheet, returns structured list for review,
and updates status/action after decisions are made.

Columns: Date(A) | Message(B) | Status(C) | Claude Notes(D) | Action(E) | Category(F)
Notes format also contains [Category] prefix set at save time (for backward compat).
"""
from __future__ import annotations
import re
from datetime import date, datetime, timedelta
from core.config import MASTER_SHEET_ID

IDEA_INBOX_TAB = "Idea Inbox"
ACTIONS = ["go", "deep dive", "hold", "archive", "research", "skip"]


_HOLD_MARKER_RE = re.compile(r"\s*\[Hold x(\d+)\]\s*$")


def _extract_category(notes: str) -> str:
    """Parse [Category] from existing notes string."""
    m = re.match(r"\[(\w+)\]", notes.strip())
    return m.group(1) if m else "Other"


def _extract_hold_count(notes: str) -> int:
    """Parse trailing [Hold xN] marker from notes. Returns 0 if absent."""
    m = _HOLD_MARKER_RE.search(notes or "")
    return int(m.group(1)) if m else 0


def _days_since(date_str: str) -> int | None:
    """Return days elapsed since date_str (format 'DD/MM/YYYY HH:MM'), or None if unparsable."""
    try:
        d = datetime.strptime(date_str.strip().split(" ")[0], "%d/%m/%Y").date()
        return (date.today() - d).days
    except Exception:
        return None


def get_pending_ideas(gc, include_message: bool = False) -> list[dict]:
    """Return all rows where Status == 'pending'.

    Args:
        include_message: If False (default), omit the raw message column to save
            tokens during review sessions — notes already contain the analysed
            summary. Pass True only when full original text is needed (e.g. when
            the user explicitly expands a card to read the source message).
    """
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    rows = ws.get_all_values()
    if not rows:
        return []

    pending = []
    for i, row in enumerate(rows[1:], start=2):
        status = row[2].strip().lower() if len(row) > 2 else ""
        if status == "pending":
            notes = row[3] if len(row) > 3 else ""
            # Col F (index 5) takes priority; fall back to parsing [Category] from notes
            category = (row[5].strip() if len(row) > 5 and row[5].strip() else None) or _extract_category(notes)
            idea = {
                "row": i,
                "date": row[0] if len(row) > 0 else "",
                "status": status,
                "category": category,
                "notes": notes,
                "action": row[4] if len(row) > 4 else "",
                "hold_count": _extract_hold_count(notes),
                "days_since": _days_since(row[0] if len(row) > 0 else ""),
            }
            if include_message:
                idea["message"] = row[1] if len(row) > 1 else ""
            pending.append(idea)
    return pending


def update_research_brief(gc, row: int, brief: str) -> None:
    """Write research brief / deep dive output to Col G and mark status as reviewed."""
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    ws.update(values=[[brief]], range_name=f"G{row}", value_input_option="USER_ENTERED")
    ws.update(values=[["reviewed"]], range_name=f"C{row}", value_input_option="USER_ENTERED")


def get_research_ideas(gc) -> list[dict]:
    """Return all ideas with action='research' or 'deep dive', oldest first."""
    return [i for i in get_all_ideas(gc) if i["action"].strip().lower() in ("research", "deep dive")]


DELETED_IDEAS_TAB = "Deleted Ideas"
_DELETED_HEADER = ["Date", "Message", "Status", "Claude Notes", "Action", "Category", "Research", "DeletedAt"]


def _get_or_create_deleted_ws(gc):
    sh = gc.open_by_key(MASTER_SHEET_ID)
    try:
        return sh.worksheet(DELETED_IDEAS_TAB)
    except Exception:
        ws = sh.add_worksheet(title=DELETED_IDEAS_TAB, rows=200, cols=len(_DELETED_HEADER))
        ws.append_row(_DELETED_HEADER)
        return ws


def _archive_rows(gc, ws, rows: list[int]) -> None:
    """Copy given Idea Inbox rows to Deleted Ideas tab with a DeletedAt timestamp."""
    deleted_ws = _get_or_create_deleted_ws(gc)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    archive_rows = []
    for row in rows:
        values = ws.row_values(row)
        while len(values) < 7:
            values.append("")
        archive_rows.append(values[:7] + [now])
    if archive_rows:
        deleted_ws.append_rows(archive_rows, value_input_option="USER_ENTERED")


def delete_idea(gc, row: int) -> None:
    """Move an idea row to 'Deleted Ideas' tab then remove it (used for '刪除' action)."""
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    _archive_rows(gc, ws, [row])
    ws.delete_rows(row)


def delete_ideas(gc, rows: list[int]) -> None:
    """Move multiple idea rows to 'Deleted Ideas' tab then remove them — must delete
    from highest row number to lowest to avoid row-index shifting affecting
    subsequent deletions."""
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    _archive_rows(gc, ws, rows)
    for row in sorted(rows, reverse=True):
        ws.delete_rows(row)


def purge_old_deleted_ideas(gc, days: int = 30) -> int:
    """Remove rows from 'Deleted Ideas' tab whose DeletedAt is older than `days`.
    Returns number of rows purged."""
    ws = _get_or_create_deleted_ws(gc)
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return 0
    header = rows[0]
    deleted_at_col = header.index("DeletedAt") if "DeletedAt" in header else len(header) - 1
    cutoff = datetime.now() - timedelta(days=days)
    to_purge = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= deleted_at_col:
            continue
        try:
            ts = datetime.strptime(row[deleted_at_col].strip(), "%d/%m/%Y %H:%M")
        except Exception:
            continue
        if ts < cutoff:
            to_purge.append(i)
    for row in sorted(to_purge, reverse=True):
        ws.delete_rows(row)
    return len(to_purge)


def update_idea(gc, row: int, action: str, status: str = None, action_plan: str = "", category: str = "") -> None:
    """Update status, Claude Notes, action, and category for a given row.

    If status is None, defaults to 'pending' for 'hold', else 'reviewed'.
    If action_plan is empty, preserves existing Col D (keeps [Category] prefix) —
    except for 'hold' (increments trailing [Hold xN] marker) and other actions
    (strips any leftover [Hold xN] marker once resolved).
    category writes to Col F if provided.
    """
    action_lower = action.strip().lower()
    if status is None:
        status = "pending" if action_lower == "hold" else "reviewed"
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)

    if not action_plan:
        current_notes = ws.acell(f"D{row}").value or ""
        base_notes = _HOLD_MARKER_RE.sub("", current_notes)
        if action_lower == "hold":
            new_count = _extract_hold_count(current_notes) + 1
            new_notes = f"{base_notes} [Hold x{new_count}]"
            ws.update(values=[[status, new_notes, action]], range_name=f"C{row}:E{row}", value_input_option="USER_ENTERED")
        elif base_notes != current_notes:
            ws.update(values=[[status, base_notes, action]], range_name=f"C{row}:E{row}", value_input_option="USER_ENTERED")
        else:
            ws.update(values=[[status]], range_name=f"C{row}", value_input_option="USER_ENTERED")
            ws.update(values=[[action]], range_name=f"E{row}", value_input_option="USER_ENTERED")
    else:
        ws.update(values=[[status, action_plan, action]], range_name=f"C{row}:E{row}", value_input_option="USER_ENTERED")
    if category:
        ws.update(values=[[category]], range_name=f"F{row}", value_input_option="USER_ENTERED")


def get_pending_count(gc) -> int:
    return len(get_pending_ideas(gc))


def get_all_ideas(gc) -> list[dict]:
    """Return all idea rows regardless of status."""
    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    rows = ws.get_all_values()
    if not rows:
        return []
    ideas = []
    for i, row in enumerate(rows[1:], start=2):
        notes = row[3] if len(row) > 3 else ""
        category = (row[5].strip() if len(row) > 5 and row[5].strip() else None) or _extract_category(notes)
        ideas.append({
            "row": i,
            "date": row[0] if len(row) > 0 else "",
            "message": row[1] if len(row) > 1 else "",
            "status": row[2].strip().lower() if len(row) > 2 else "",
            "category": category,
            "notes": notes,
            "action": row[4] if len(row) > 4 else "",
            "research_brief": row[6].strip() if len(row) > 6 else "",
        })
    return ideas


def get_recent_ideas(gc, n: int = 5) -> list[dict]:
    """Return the last n ideas regardless of status."""
    all_ideas = get_all_ideas(gc)
    return all_ideas[-n:] if len(all_ideas) >= n else all_ideas


def get_last_idea(gc) -> dict | None:
    """Return the most recently saved idea."""
    all_ideas = get_all_ideas(gc)
    return all_ideas[-1] if all_ideas else None


def get_stats(gc) -> dict[str, int]:
    """Return count of ideas by category, sorted by count descending."""
    all_ideas = get_all_ideas(gc)
    stats: dict[str, int] = {}
    for idea in all_ideas:
        cat = idea["category"] or "Other"
        stats[cat] = stats.get(cat, 0) + 1
    return dict(sorted(stats.items(), key=lambda x: x[1], reverse=True))


def search_ideas(gc, keyword: str, limit: int = 5) -> list[dict]:
    """Search ideas by keyword in message (case-insensitive). Returns last `limit` matches."""
    all_ideas = get_all_ideas(gc)
    kw = keyword.lower()
    matches = [i for i in all_ideas if kw in i["message"].lower()]
    return matches[-limit:] if len(matches) > limit else matches
