"""core/loop_engine.py — Loop Engineering: iterative LLM generation with auto-audit.

範式：定好 criteria → AI 生成 → auto-audit → surgical fix → repeat（max N 輪）
核心差異：唔係「改 prompt 再試」，而係「定好 criteria，讓 AI 自己檢查自己」。

Usage:
    from core.loop_engine import loop_audit, AuditResult

    content, rounds, results = loop_audit(
        generate_fn=lambda: my_generate(),
        audit_fn=my_audit_fn,       # programmatic checks, no extra LLM call
        fix_fn=my_fix_fn,           # only called when there are fails
        max_rounds=3,
    )
"""
from __future__ import annotations
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class AuditResult:
    """Single criterion audit result."""

    def __init__(self, criterion: str, passed: bool, reason: str = ""):
        self.criterion = criterion
        self.passed = passed
        self.reason = reason

    def __repr__(self) -> str:
        status = "✅" if self.passed else "❌"
        return f"{status} {self.criterion}" + (f" — {self.reason}" if self.reason else "")


def loop_audit(
    generate_fn: Callable[[], str],
    audit_fn: Callable[[str], list[AuditResult]],
    fix_fn: Callable[[str, list[AuditResult]], str],
    max_rounds: int = 3,
) -> tuple[str, int, list[AuditResult]]:
    """Loop Engineering core: generate → audit → surgical fix → repeat.

    Args:
        generate_fn: Generates initial content (called once on Round 1).
        audit_fn:    Programmatic audit — returns list[AuditResult]. No extra LLM call.
        fix_fn:      Receives (content, fail_results), returns fixed content.
                     Only called when there are fails; only fixes fail items.
        max_rounds:  Maximum iterations. Recommended: 3 for short content, 2 for long.

    Returns:
        (final_content, rounds_taken, final_audit_results)
        - rounds_taken == 1  → all criteria passed first attempt (no extra tokens)
        - rounds_taken == N  → reached max_rounds (best-effort returned, fails logged)
    """
    content = ""
    audit_results: list[AuditResult] = []

    for round_num in range(1, max_rounds + 1):
        if round_num == 1:
            content = generate_fn()
        else:
            fails = [r for r in audit_results if not r.passed]
            if not fails:
                break
            content = fix_fn(content, fails)

        audit_results = audit_fn(content)
        fails = [r for r in audit_results if not r.passed]
        logger.debug("loop_audit round %d/%d: %d fail(s)", round_num, max_rounds, len(fails))

        if not fails:
            logger.debug("loop_audit: all criteria passed in round %d", round_num)
            return content, round_num, audit_results

    # Max rounds reached — return best-effort, log unresolved fails
    remaining = [r for r in audit_results if not r.passed]
    if remaining:
        logger.warning(
            "loop_audit: %d round(s) done, %d unresolved — %s",
            max_rounds,
            len(remaining),
            [r.criterion for r in remaining],
        )
    return content, max_rounds, audit_results
