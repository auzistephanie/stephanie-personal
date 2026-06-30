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
└── scripts/      # 雜項腳本
```

## 共用資源

- `MASTER_SHEET_ID`：Idea Inbox 同 business repo 共用同一張 Google Sheet
- Idea Inbox 欄位定義：參考 business repo `.claude/SHEETS_ASANA.md`
- `error_to_idea.py`：仍在 business repo `scripts/`，唔需要 copy 過嚟

## Cowork Tasks

| Task | Script | 觸發 |
|---|---|---|
| Idea Inbox Digest | `idea_inbox/idea_digest.py` | 平日 10:48am |
| Weekly Reflection | `idea_inbox/weekly_reflection.py` | 每週五 5:08pm |
| Notify Kristy Monthly | 仍在 business repo `scripts/notify_kristy_monthly.py` | 每月第1個 weekday |

## Git Push

用 **git CLI** 推送：

```bash
git add <files> && git commit -m "msg" && git push
```

## 首次使用

複製 `.env.template` 至 `.env`，填入真實憑證後再運行任何腳本：

```bash
cp .env.template .env
# 然後編輯 .env，填入各項 credentials
```
