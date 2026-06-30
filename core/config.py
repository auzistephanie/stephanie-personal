"""core/config.py — personal repo config (idea inbox + shared utilities)."""
from __future__ import annotations
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root

# Path to GCP service account JSON (local dev fallback; Vercel uses GCP_SERVICE_ACCOUNT_JSON env var)
SERVICE_ACCOUNT = os.environ.get(
    "GCP_SERVICE_ACCOUNT_PATH",
    os.path.join(_HERE, "just-clover-487108-a0-f091da582010.json"),
)

MASTER_SHEET_ID = os.environ.get(
    "MASTER_SHEET_ID",
    "153iv2oll2GGHy0XgJHCqUAcWzhSPoeYD9lBX9YFsNew",
)
