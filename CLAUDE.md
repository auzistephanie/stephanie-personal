# Stephanie Personal — Automation Repo

> 詳細資訊按需 `read_file` 讀取，唔好靠記憶或猜測。

## 概覽

| 功能 | 說明 |
|---|---|
| CV Generator | 按職位生成 tailored CV + cover letter；CV 原稿放 `cv/`，輸出放 `Tailored_CVs/` |
| Idea Inbox | Telegram bot 收 idea → 自動分類存 Master Google Sheet → 每週 digest |
| 智囊團 | Idea Review 時召喚多角色 council 討論，評估可行性 + 優先級 |
| Obsidian Reflection | 每週反思草稿生成 → 同步至 Obsidian vault（`obsidian/`）|
| Shared Sheet Bridge | Idea Inbox 用同一 `MASTER_SHEET_ID`（business repo 共用）；`error_to_idea.py` 由 business repo 寫入 |

## 架構（簡覽）

```
stephanie-personal/
├── cv/           # CV 原稿、cover letter 模板
├── idea_inbox/   # Idea bot、digest、智囊團腳本
├── obsidian/     # 每週反思草稿
├── docs/         # 個人背景文件、idea_review_council 角色設定
└── scripts/      # github_push.py（推送用）
```

## 共用資源

- `MASTER_SHEET_ID`：Idea Inbox 同 business repo 共用同一張 Google Sheet
- Idea Inbox 欄位定義：參考 business repo `.claude/SHEETS_ASANA.md`
- `error_to_idea.py`：仍在 business repo `scripts/`，唔需要 copy 過嚟

## Git Push

**用 `scripts/github_push.py`** — 同 business repo 同款。唔用 git CLI（除非係全新 repo 首次 init）。

```bash
python3 scripts/github_push.py "your commit message"
```
