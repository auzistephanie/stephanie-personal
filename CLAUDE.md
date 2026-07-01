# Stephanie Personal — Automation Repo

> 詳細資訊按需 `read_file` 讀取，唔好靠記憶或猜測。

## 概覽

| 功能 | 說明 |
|---|---|
| CV Generator | 按職位生成 tailored CV + cover letter；CV 原稿放 `cv/`，輸出放 `cv/Tailored_CVs/` |
| Idea Inbox | Telegram bot 收 idea → 自動分類（`idea_inbox/idea_inbox.py` `IDEA_CATEGORIES`）存 Master Google Sheet → 每週 digest |
| 智囊團 | Idea Review 時召喚多角色 council 討論，評估可行性 + 優先級（角色設定 `docs/idea_review_council.md`）|
| Obsidian Vault（Second Brain）| 實際 vault 喺 `obsidian-vault/`（唔係 `obsidian/`，嗰個係空資料夾）。結構 + tag 用法見 `obsidian-vault/README.md`；問 vault 問題用 `askvault` skill |
| Obsidian Reflection | 每週五自動生成反思草稿 → 寫入 `obsidian-vault/04-每週反思/` → 同步觸發 MOC 重建 |
| Vault MOC（自動索引）| `idea_inbox/vault_moc.py`，由 weekly_reflection.py 每次跑完自動觸發，重建 `obsidian-vault/00-MOC/` 五個 index（個人學習／每週反思／買樓裝修／01-工作／05-貓貓健康），並彙整所有 note 嘅未剔 `- [ ]` commitment |
| Idea → Obsidian 自動歸檔 | idea-inbox-digest 執行「做」後，按 category 寫入對應 vault 資料夾（見 idea-inbox-digest scheduled task 內 category→subfolder 對照表）|
| Shared Sheet Bridge | Idea Inbox 用同一 `MASTER_SHEET_ID`（business repo 共用）；`error_to_idea.py` 由 business repo 寫入 |

## 架構（簡覽）

```
stephanie-personal/
├── cv/                # CV 原稿、cover letter 模板、Tailored_CVs/
├── idea_inbox/        # Idea bot、idea_review.py、idea_router.py、weekly_reflection.py、vault_moc.py
├── obsidian-vault/     # 實際 Obsidian second brain vault（00-MOC/ 01-工作/ 02-個人/ 03-買樓裝修/ 04-每週反思/ 05-貓貓健康/ 個人學習/）
├── .claude/skills/askvault/  # 問 vault 問題嘅 Cowork skill
├── docs/               # 個人背景文件、idea_review_council 角色設定
└── scripts/            # 雜項腳本（github_push.py）
```

## 共用資源

- `MASTER_SHEET_ID`：Idea Inbox 同 business repo 共用同一張 Google Sheet
- Idea Inbox 欄位定義：參考 business repo `.claude/SHEETS_ASANA.md`
- `error_to_idea.py`：仍在 business repo `scripts/`，唔需要 copy 過嚟

## Cowork Tasks

| Task | 觸發 | 說明 |
|---|---|---|
| `idea-inbox-digest` | 平日 11:18am | inline 智囊團分析 pending ideas，「做」的話按 category 寫入 obsidian-vault |
| `weekly-reflection-draft` | 每週五 5:08pm | `idea_inbox/weekly_reflection.py`：生成反思草稿 → 寫 vault → 自動重建 MOC → Telegram 通知 |
| Notify Kristy Monthly | 每月第1個 weekday | 仍在 business repo `scripts/notify_kristy_monthly.py` |

## Git Push

用 `scripts/github_push.py`（GitHub API，避開 git CLI lock file 問題）：

```bash
python3 scripts/github_push.py "<commit message>"
```

## 首次使用

複製 `.env.template` 至 `.env`，填入真實憑證後再運行任何腳本：

```bash
cp .env.template .env
# 然後編輯 .env，填入各項 credentials
```
