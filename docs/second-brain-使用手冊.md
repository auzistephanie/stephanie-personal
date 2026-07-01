# Second Brain 使用手冊（Obsidian + Idea Inbox + Telegram）

> 2026-07-01 建立。呢份係完整 step-by-step 操作指南；技術實作細節見 `idea_inbox/*.py` + `.claude/skills/askvault/SKILL.md`。

---

## 0. 一圖睇晒成個循環

```
你 Telegram 打字/影相 → auideabot
    ↓ LLM auto_categorize()
存入 Idea Inbox Google Sheet（9 個 category 之一）
    ↓
平日 11:18am `idea-inbox-digest`（Cowork 自動觸發）
    ↓ 智囊團（Eheh/Pixel/Sage/Coco/Mochi/Pace）分析每條
你揀：✅ 做 / ⏸ 暫緩 / 🗄️ 唔要
    ↓（做）
Claude 執行 + 按 category 自動寫 note 入 obsidian-vault 對應資料夾
    ↓
每週五 5:08pm `weekly-reflection-draft`（Cowork 自動觸發）
    ↓
掃返本週 Idea Inbox + 新 notes → LLM 生成反思 → 寫入 04-每週反思/
    ↓
自動觸發 vault_moc.py → 重建 00-MOC/ 五個 index
    ↓
Telegram 通知你（含 Obsidian deep link）
```

你唯一需要「主動做」嘅步驟：**Telegram 打字**（capture）、**揀 做/暫緩/唔要**（decide）、**問 vault**（retrieve）。其餘全自動。

---

## 1. Setup（一次性，已完成）

- Vault 位置：`/Users/stephanieau/stephanie-personal/obsidian-vault/`
- Obsidian plugin：Smart Connections（related-notes 側邊欄）+ Remotely Save（跨裝置同步）
- 手機同步：跟 `docs/obsidian-sync-guide.md`（Mac + Android，用 Remotely Save + Google Drive）

如果換新裝置或重裝 Obsidian，先睇 `docs/obsidian-sync-guide.md`。

---

## 2. Step by Step：日常點用

### Step 1 — Capture（隨手記，唔使諗分類）

開 Telegram → auideabot → 打字或影相，例如：

```
今日睇到隻貓成日撓門，可能有壓力，要留意
```

系統自動：
1. LLM 判斷 category（見下面 9 個分類）
2. 存落 Idea Inbox Google Sheet 一行
3. 唔使你揀資料夾、唔使你診邊個 project——之後自動處理

**9 個分類（`idea_inbox/idea_inbox.py` IDEA_CATEGORIES）：**

| Category | 用喺邊 |
|---|---|
| `Tool` | 外部工具/平台/app |
| `Automation` | 自動化流程/script/integration |
| `Content` | 文章/教學/參考資料 |
| `ClaudeCode` | Claude skill/prompt/AI workflow |
| `AI` | AI 模型/研究/趨勢 |
| `Business` | VNX 業務（課程/定價/策略） |
| `Property` | 買樓/裝修/供款 |
| `PetHealth` | 貓貓（或其他寵物）健康/獸醫/照顧（2026-07-01 新加） |
| `Personal` | 其他個人生活 |

分唔到就自動變 `Other` 或 LLM 自創 CamelCase tag。

---

### Step 2 — Digest（自動，平日 11:18am）

`idea-inbox-digest` 自動跑，Claude 扮 6 位智囊團角色分析你 pending 嘅每一條 idea，出 widget 俾你揀：

- **✅ 做** → Claude 即場執行（研究/寫 code/寫 file），完咗自動寫 note 入 vault
- **⏸ 暫緩** → 留返 Sheet，之後再睇
- **🗄️ 唔要** → 存檔

如果想即刻睇，唔想等排程，喺 Cowork 講「review ideas」就得。

---

### Step 3 — 自動歸檔（Category → 資料夾）

揀「做」之後，Claude 按 category 寫 note，命名 `YYYY-MM-DD <標題>.md`：

| Category | 去邊 |
|---|---|
| ClaudeCode / AI / Tool / Content / Automation | `個人學習/` |
| Business | `01-工作/` |
| Property | `03-買樓裝修/` |
| PetHealth | `05-貓貓健康/`（2026-07-01 新加） |
| Personal / Other | `02-個人/` |

Note 內會有：`## 智囊團分析` + `## Claude 執行結果`（做咗啲乜或者「待你執行」+ next steps）。

---

### Step 4 — 手動記錄（唔經 Telegram，重要決定用）

有啲嘢想自己親手記（例如買樓決定嘅完整脈絡），去對應資料夾複製 template：

| 資料夾 | Template | 幾時用 |
|---|---|---|
| `01-工作/` | `00-Templates/決策記錄.md` | VNX 工作決定 |
| `02-個人/` | `00-Templates/決策記錄.md` | 個人生活決定 |
| `03-買樓裝修/` | `00-Templates/買樓裝修決定.md` | 每次買樓/裝修新決定 |
| `05-貓貓健康/` | `00-Templates/貓貓健康.md` | 貓貓健康記錄 |
| `04-每週反思/` | `00-Templates/每週反思.md` | 自動生成，一般唔使手動 |

唔需要填晒所有欄位，**有 3 行就夠**。Tag 用法：`#vnx #automation #課程`（工作）、`#買樓 #裝修 #生活`（個人）、`#貓貓健康`。

**觸發習慣：** 每次關 Asana task 之前，花 3 分鐘填一個決策記錄。

---

### Step 5 — 每週反思（自動，週五 5:08pm）

`weekly_reflection.py` 自動：
1. 收集本週 Idea Inbox 新 ideas
2. 掃全部資料夾本週新增/改動嘅 notes
3. LLM 生成反思草稿（做得好/做漏咗/下週重點/決策回顧）
4. 寫入 `04-每週反思/YYYY-MM-DD <週題>.md`
5. Telegram send 你（連 Obsidian deep link，撳到就直接開嗰篇 note 改）

**你要做：** 收到 Telegram 通知，開嚟睇一睇，覺得唔啱就自己改。純草稿，唔係最終定稿。

---

### Step 6 — MOC 自動索引（自動，跟住 Step 5 一齊跑）

`vault_moc.py` 重建 `00-MOC/` 入面 5 個 index 頁：

- `個人學習 MOC.md` — 按分類（AI工具評估/工具評估/方法論）列晒所有筆記
- `每週反思 MOC.md` — 由新到舊列晒所有週記
- `買樓裝修 MOC.md` — 02-個人 + 03-買樓裝修 全部記錄
- `01-工作 MOC.md` — VNX 工作決定記錄索引
- `05-貓貓健康 MOC.md` — 貓貓健康記錄，按貓貓（Mochi/Eheh）分組

每個 MOC 底部仲有 **「未完成 Commitments」**——自動掃全部 note 入面未剔嘅 `- [ ]`，跨 note 彙整埋一齊。想知自己仲有咩手尾未跟，睇 MOC 就夠，唔使逐篇 note 揭。

---

### Step 7 — 問 Vault（retrieve，隨時用）

想搵返之前記過嘅嘢，喺 Cowork 講：

```
問 vault：我之前有冇記過 Headroom？
問 vault：買樓決定去到邊一步？
vault 有咩 AI 工具評估？
我上次反思講過要做咩？
```

會觸發 `askvault` skill：讀成個 vault → 廣東話整合答案 → 列相關 `[[note]]` → 提未完成 commitment。**vault 冇嘅佢會老實講「未有記錄」，唔會作。**

---

## 3. 完整資料夾對照

```
obsidian-vault/
├── 00-MOC/          ← 自動生成 index，唔使手動改
├── 00-Templates/    ← 4 個模板（決策/週反思/買樓裝修/貓貓健康）
├── 01-工作/         ← VNX 工作決定
├── 02-個人/         ← 個人生活決定
├── 03-買樓裝修/     ← 買樓裝修（有 README 記時間線 + 快速參考表）
├── 04-每週反思/     ← 自動生成週記
├── 05-貓貓健康/     ← 貓貓健康記錄（2026-07-01 新加，Telegram 已打通）
└── 個人學習/        ← AI/tech 工具評估、方法論
```

---

## 4. 常見問題

**Q：Telegram 打錯分類點算？**
去 Idea Inbox Google Sheet 手動改個 category 欄就得，唔影響已存嘅內容。

**Q：想即刻睇今日 idea 進度，唔等 11:18am？**
Cowork 講「review ideas」即刻觸發。

**Q：手機唔喺身邊，Mac 又冇開，錯過咗 Telegram capture 點算？**
冇所謂，你隨時可以直接去對應資料夾手動加 note（Step 4），一樣會俾 MOC / askvault 讀到。

**Q：點知呢套系統有冇真係用開？**
問我「second brain 成效點」，我會實測數各資料夾 note 數/日期分佈俾你睇（唔靠估）。

---

## 5. 未決定事項（跟進中）

- 要唔要喺 Obsidian app 度另外裝 Smart Chat plugin（`askvault` 已覆蓋大部分需求，呢個純粹想喺 app 內直接問）

**已完成（2026-07-01）：** `01-工作` `05-貓貓健康` 已加返 MOC index，5 個 MOC 頁全部由 `vault_moc.py` 自動重建。

---
*本手冊由 Claude 根據 stephanie-personal repo 實際程式碼 + scheduled task 內容整理，2026-07-01。如流程有改動，麻煩叫 Claude 重新 sync 呢份文件。*
