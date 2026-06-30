---
name: idea-review
description: Review pending ideas in the Idea Inbox Google Sheet. Use this skill whenever Stephanie says "review ideas", "睇下 idea inbox", "check ideas", "有咩 idea pending", "幫我 review ideas", or wants to process accumulated ideas from the Telegram Idea Inbox bot. This skill loads pending ideas, displays them for Stephanie to decide the action per idea, then generates an action plan, updates the sheet, and sends a summary to auideabot.
---

# Idea Inbox Review

## Context

Stephanie sends ideas (text + screenshots) to a Telegram bot → saved into the "Idea Inbox" tab of the Master Google Sheet. Category is **already set** at save time — your job is to **present each idea clearly**, let Stephanie pick the action, then generate a brief action plan based on her decision.

**Sheet columns:** Date (A) | Message (B) | Status (C) | Claude Notes (D) | Action (E)
**Notes column** already contains `[Category]` prefix (e.g. `[Tool]`, `[Skill]`).

**Actions:** install now / hold / research / skip

**Research Backlog actions (for existing research ideas):** install now / hold / skip

---

## Workflow

### Step 1: Load pending ideas

```python
from core.sheets_client import get_gc
from core.idea_review import get_pending_ideas

gc = get_gc()
pending = get_pending_ideas(gc)
```

If `pending` is empty → "Inbox 係空㗎！冇 pending ideas。" and stop.

Otherwise → display all ideas for review (Step 2).

---

### Step 2: Display ideas — Stephanie picks action per idea

Show all pending ideas at once. For each idea, display:

```
📋 Idea Review — {N} 個 pending ideas

**{i}. [{Category}] {date}**
{full message}

Action？→ 📦 install now / 📋 backlog / 🔍 research / ⏭️ skip
```

**Wait for Stephanie to specify the action for each idea.**

She may say:
- "1 backlog, 2 skip" — multiple at once
- "idea 1 install now" — single idea
- "全部 backlog 除咗 3 skip" — bulk with exception

Confirm back what you understood before proceeding to Step 3.

---

### Step 3: Generate action plan per idea (after action is decided)

Once Stephanie has assigned an action to every idea, write a short action plan (2–4 lines) for each:

| Action | Action plan content |
|---|---|
| install now | 涉及邊個 file/function、具體步驟、估計難度（Quick Win / Medium） |
| hold | 暫時擱置原因 + 建議重新考慮嘅時機 |
| research | 點 research（search 乜 / 睇邊個 doc） |
| skip | 一句原因 |

Category hints:
- Tool/Skill → lean install now or backlog if clearly useful
- Automation → consider complexity, lean backlog
- Content → research unless immediately actionable
- Other → judge on merit

Present the plans briefly and ask for final confirmation before writing to sheet.

---

### Step 3b: Research Backlog — Deep Dive (run after Step 3, before Step 4)

After collecting pending idea actions, also load research ideas:

```python
from core.idea_review import get_research_ideas, update_research_brief

research = get_research_ideas(gc)
```

If `research` is empty, skip this section entirely.

For each idea with **empty Col G**, Claude generates a Deep Dive directly (no API call):

Format:
```
🔍 Deep Dive — [{Category}]
📌 核心：[idea 係咩，1句]
❓ 關鍵問題：[要搞清楚嘅 1–2 個問題]
🔗 與 VNX 關係：[相關程度 + 潛在用途]
📅 建議時機：[咩情況下值得行動]
```

Save immediately after generating:
```python
update_research_brief(gc, idea["row"], generated_deep_dive_text)
idea["research_brief"] = generated_deep_dive_text
```

Then display all research ideas (with brief):
```
🔍 Research Backlog — {N} 條

**{i}. [{Category}] {date}**
{full message}

{Col G content}

Action？→ 📦 install now / 📋 backlog / ⏭️ skip
```

Wait for Stephanie to assign an action to each research idea (install now / hold / skip).
Confirm back before updating.

---

### Step 4: Update sheet (after confirmation)

For pending ideas, call:

```python
from core.idea_review import update_idea, update_research_brief

update_idea(gc=gc, row=idea["row"], action=action, action_plan=action_plan_text)

# For "research" ideas: Claude generates Research Brief directly → save to Col G
# Format:
# 🔍 研究方向：[1句]
# ❓ 關鍵問題：[1–2個要搞清楚嘅問題]
# 📅 建議時機：[咩情況下值得深研]
if action == "research":
    # Claude writes the brief inline, then:
    update_research_brief(gc, idea["row"], claude_generated_brief)
```

For research backlog ideas (from Step 3b), update with the new action decided by Stephanie:

```python
update_idea(gc=gc, row=idea["row"], action=new_action)
# Deep Dive already saved to Col G in Step 3b — no need to regenerate
```

`action_plan_text` = the 2–4 line plan you wrote in Step 3 (plain text, no markdown).
Update each row immediately — partial progress is saved if something fails.

---

### Step 5: Send summary to Telegram via auideabot

```python
import os, requests

def send_idea_summary(text: str) -> None:
    token = os.environ.get("IDEA_BOT_TOKEN", "")
    chat_id = os.environ.get("IDEA_CHAT_ID", "")
    if not token or not chat_id:
        print("IDEA_BOT_TOKEN or IDEA_CHAT_ID not set — skipping Telegram")
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )

send_idea_summary(summary_text)
```

**Summary format:**

```
✅ <b>Idea Inbox Review 完成</b>
共 {N} 個 ideas 已處理

📦 <b>Install Now ({count}):</b>
• [{Category}] {message preview ~60 chars}
  → {action plan, 1 line}

📋 <b>Add to Backlog ({count}):</b>
• ...
  → ...

🔍 <b>Research ({count}):</b>
• [{Category}] {message preview ~60 chars}
  📄 {research brief first step line, if available}

⏭️ <b>Skipped ({count}):</b>
• ...

🔭 <b>Research Backlog 已處理 ({count}):</b>
• [{Category}] {message preview ~60 chars} → {new action}
```

Omit sections with 0 items. Omit Research Backlog section if no research ideas were reviewed.

---

### Step 6: Final reply in Cowork

```
✅ Review 完成！Sheet 已更新，summary 已送去 auideabot。
```

---

## Notes

- **一次過 present，唔係逐個 confirm** — show all ideas together, wait for one confirmation
- Be decisive: every idea gets one clear action
- Image ideas start with "[圖片]" — judge from the description
- Unclear/very short messages → "research"
- `action_plan` written to Sheet col D replaces the existing `[Category]` prefix — that's fine, category is already used for display
