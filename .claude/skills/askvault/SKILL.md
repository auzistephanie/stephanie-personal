---
name: askvault
description: 問 Obsidian vault 一個問題 — 搜尋相關筆記、整合廣東話答案、列出關聯 [[links]]、提返未完成 commitment。當 Stephanie 講「問 vault」、「/askvault」、「vault 有冇關於 X」、「vault 入面有咩 X」、「我之前有冇記過 X」時使用。
---

# Ask Vault

## Vault 定位

**Vault = 「思考 / 經驗 / 判斷」層**：備課點子、工具評估、決策脈絡、教學 insight、踩過嘅坑、方法論、面試 learnings。

**唔包括：** 營運數字（日期、報名數、checklist、broadcast）→ 問 webapp / bot。

## Vault 位置

```
/Users/stephanieau/stephanie-personal/obsidian-vault/
├── 00-MOC/          ← Map of Content：各範疇 index（起點）
├── 個人學習/        ← AI/tech 工具評估、方法論筆記
├── 01-工作/         ← VNX 工作決定
├── 02-個人/         ← 個人生活決定（買樓、裝修、財務）
├── 03-買樓裝修/     ← 買樓裝修相關記錄
├── 04-每週反思/     ← 每週反思筆記
├── 05-貓貓健康/     ← 貓貓健康記錄
└── 00-Templates/    ← 空白模板，唔係知識（略過）
```

---

## 流程

### Step 1：搵所有 vault notes

```bash
find /Users/stephanieau/stephanie-personal/obsidian-vault \
  -name "*.md" \
  -not -path "*/.obsidian/*" \
  -not -path "*/.smart-env/*" \
  -not -path "*/00-Templates/*" \
  | sort
```

### Step 2：讀相關 notes

用 Read tool 讀所有 notes（排除 Templates）。

如果 vault 有 20+ notes，先讀 `00-MOC/` 入面嘅 index，再 targeted 讀相關分類嘅 notes。

### Step 3：整合答案

根據 Stephanie 嘅問題，整合相關 notes，**廣東話**回答：

```
[核心答案 — 2–4 句，直接回答，唔廢話]

📚 相關筆記：
• [[Note Title]] — 一句說明點相關

⏳ 未完成嘅 commitment：
• 來自 [[Note Title]]：未剔嘅 - [ ] item 原文
（如無 pending items，省略呢段）

💡 可以深挖：
• 如想了解更多 [X]，可以問我關於 [[Y Note]]
（如無明顯延伸，省略呢段）
```

---

## 答題原則

| 原則 | 做法 |
|------|------|
| **廣東話** | 自然口語，唔係書面語 |
| **引用 note** | 用 `[[雙方括號]]` 標題格式 |
| **唔捏造** | vault 冇嘅，直接講「未有記錄」；可以問 Stephanie 係咩想寫落去 |
| **提 commitment** | 每篇 note 嘅 `- [ ]` 未剔項目都要 surface，唔好靜靜雞略過 |
| **唔包 Templates** | 模板係空白格式，唔係知識，略過 |
| **唔包 README** | 目錄性質，唔係知識，略過 |

---

## 常見觸發場景

| Stephanie 講 | 應該做 |
|---|---|
| 「vault 有冇關於 Headroom？」 | 讀 vault → 搵 AI 工具 notes → 答 |
| 「我之前有冇記過買樓決定？」 | 讀 vault → 搵 02-個人 + 03-買樓裝修 → 答 + 列 pending items |
| 「備課有咩 insight 可以參考？」 | 讀 vault → 搵 個人學習 + 每週反思 → 整合相關內容 |
| 「我上次反思講過要做咩？」 | 讀 04-每週反思 嘅最新 note → 列出「下週重點」未剔項目 |
| 「vault 有咩 AI 工具評估？」 | 讀 個人學習 所有 notes → 列出工具 + 結論 |
