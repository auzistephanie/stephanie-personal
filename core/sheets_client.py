"""Shared gspread client + pricing utilities.

Usage:
    from core.sheets_client import get_gc, scan_pricing_rounds
    gc = get_gc()
    ws = gc.open_by_key(SHEET_ID).worksheet("Tab Name")
"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime, date

import gspread
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False
from google.oauth2.service_account import Credentials
from core.config import SERVICE_ACCOUNT

# ── Pricing tab ───────────────────────────────────────────────────────────────

# All course codes that appear as column headers in the Pricing tab rounds table.
PRICING_KNOWN_CODES = {
    "FULL-029", "FULL-030", "PART-010",
    "AI-009", "AI-010",
    "WILY-001",
    "Remote - Max", "Remote - Vincent",
}


def _parse_pricing_date(s: str):
    """Parse a date string from the Pricing tab.
    Handles '3 Jun 2026(Wed)', '8 Jun 2026(Mon)', '3/6/2026', etc.
    Returns a date object or None.
    """
    if not s:
        return None
    s = s.strip()
    clean = re.sub(r'\([^)]*\)', '', s).strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    return None


def scan_pricing_rounds(all_vals, as_of_date, known_codes=None):
    """Scan the Pricing tab rounds table; return active EB price/deadline per course.

    For each course code column the function reads rows in the rounds table and
    keeps the *last* row where:
        - announce_date  <= as_of_date   (round has been announced)
        - deadline       >= as_of_date   (EB hasn't expired yet)

    Args:
        all_vals    : list[list[str]] — from worksheet.get_all_values()
        as_of_date  : date | datetime
                      • Pricing page  → pass today  (shows currently active EB)
                      • seminar_sync  → pass seminar_date  (finds the EB row
                        announced on that specific seminar date)
        known_codes : set[str] | None — course codes to look for;
                      defaults to PRICING_KNOWN_CODES

    Returns:
        {course_code: {"eb_price": str, "eb_deadline": str}}
    """
    if known_codes is None:
        known_codes = PRICING_KNOWN_CODES

    # Normalise as_of_date → date
    as_of = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date

    # Find the header row containing course codes
    code_row_idx = None
    for i, row in enumerate(all_vals):
        if any(c.strip() in known_codes for c in row):
            code_row_idx = i
            break
    if code_row_idx is None:
        return {}

    # Map course_code → column index
    course_cols = {}
    for j, cell in enumerate(all_vals[code_row_idx]):
        code = cell.strip()
        if code in known_codes:
            course_cols[code] = j

    # Find "Round" header row below code row
    rounds_header_idx = None
    for i in range(code_row_idx + 1, len(all_vals)):
        row = all_vals[i]
        if row and row[0].strip() == "Round":
            rounds_header_idx = i
            break
    if rounds_header_idx is None:
        return {}

    result = {}
    for i in range(rounds_header_idx + 1, len(all_vals)):
        row = all_vals[i]
        if not row:
            break
        max_col = max(course_cols.values(), default=0)
        while len(row) < max_col + 3:
            row.append("")
        if row[0].strip() == "" and not any(row[1:]):
            break

        for code, col_idx in course_cols.items():
            announce_str = row[col_idx].strip()     if col_idx     < len(row) else ""
            price_str    = row[col_idx + 1].strip() if col_idx + 1 < len(row) else ""
            deadline_str = row[col_idx + 2].strip() if col_idx + 2 < len(row) else ""
            if not price_str or not deadline_str:
                continue
            if price_str in ("No active round", "#N/A", "End", "--"):
                continue
            dt_deadline = _parse_pricing_date(deadline_str)
            if not (dt_deadline and dt_deadline >= as_of):
                continue
            dt_announce = _parse_pricing_date(announce_str)
            if dt_announce and dt_announce > as_of:
                continue  # not yet announced as of as_of_date
            result[code] = {"eb_price": price_str, "eb_deadline": deadline_str}

    return result

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def get_creds(scopes: list) -> Credentials:
    """Load service-account credentials. Checks three sources in order:
    1. GCP_SERVICE_ACCOUNT_JSON env var (Vercel / CI)
    2. Streamlit secrets (Streamlit Cloud)
    3. Local SA file (local dev)
    """
    raw = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    if _HAS_ST and "gcp_service_account" in st.secrets:
        return Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scopes
        )
    return Credentials.from_service_account_file(SERVICE_ACCOUNT, scopes=scopes)


# ── Retry layer ─────────────────────────────────────────────────────────────
#
# 所有 gspread API call（open_by_key / get_all_values / values_batch_get /
# update / append_row …）最終都經 client.http_client.request()。Google Sheets
# API 有 per-minute quota，撞到會 raise APIError 429（偶爾 5xx）。以前 130+ 個
# call site 全部冇重試，一撞 quota 成個 job fail。喺 get_gc() 統一 wrap 呢個
# chokepoint，call site 零改動就有 exponential backoff。

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_TRIES = 5          # 1 次 + 4 次重試（延遲：2, 4, 8, 16s = 30s 上限，fit Vercel 60s timeout）
_BASE_DELAY = 2.0       # 秒；2, 4, 8, 16 … exponential
_CALL_SLEEP = 0.5       # 每次 request 成功後 sleep（2 req/s max，大減 burst 風險）


def _install_retry(gc: gspread.Client) -> gspread.Client:
    """Wrap gc.http_client.request with retry-on-429/5xx + inter-call sleep (idempotent)."""
    from gspread.exceptions import APIError

    http = gc.http_client
    if getattr(http, "_retry_installed", False):
        return gc
    orig = http.request

    def request_with_retry(*args, **kwargs):
        for attempt in range(_MAX_TRIES):
            try:
                result = orig(*args, **kwargs)
                time.sleep(_CALL_SLEEP)  # stagger calls to stay under quota
                return result
            except APIError as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status not in _RETRY_STATUS or attempt == _MAX_TRIES - 1:
                    raise
                delay = _BASE_DELAY * (2 ** attempt)
                print(f"[sheets] APIError {status}, retry {attempt + 1}/"
                      f"{_MAX_TRIES - 1} in {delay:.1f}s")
                time.sleep(delay)
        return orig(*args, **kwargs)  # unreachable, satisfies type

    http.request = request_with_retry
    http._retry_installed = True
    return gc


def get_gc() -> gspread.Client:
    """Return an authorised gspread client with a built-in 429/5xx retry layer."""
    return _install_retry(gspread.authorize(get_creds(_SCOPES)))
