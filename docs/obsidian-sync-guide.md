# Obsidian 手機同步指南（Mac + Android）

免費方案：Remotely Save plugin + Google Drive

---

## 第一步：Mac 設定

### 1. 移去 iCloud / 獨立資料夾
將 `obsidian-vault` 資料夾移去你想放嘅位置（例如 Desktop 或 Documents），唔好放喺 git repo 入面。

### 2. 開 Obsidian vault
Obsidian → **Open Vault** → 揀你嗰個 `obsidian-vault` 資料夾

### 3. 開啟 Community Plugins
**Settings**（左下齒輪圖示）→ **Community plugins** → 撳 **Turn on community plugins**

### 4. 安裝 Remotely Save
Community plugins → **Browse** → 搜尋 `Remotely Save` → **Install** → **Enable**

### 5. 連接 Google Drive
Settings → **Remotely Save** → Remote Service 選 **Google Drive** → 撳 **Auth** → 彈出 Google 登入視窗 → 登入你個 Google 帳號 → 授權

### 6. 第一次 Sync
Remotely Save 設定頁 → 撳 **Run once** → 等佢上傳完成

✅ Mac 完成

---

## 第二步：Android 設定

### 1. 安裝 Obsidian
Play Store 搜 **Obsidian** → 安裝（免費）

### 2. 建新 Vault
開 Obsidian → **Create new vault** → 名字同 Mac 一樣（例如 `obsidian-vault`）→ 選一個本地位置 → Create

### 3. 開啟 Community Plugins
Settings → **Community plugins** → Turn on community plugins

### 4. 安裝 Remotely Save
Community plugins → **Browse** → 搜尋 `Remotely Save` → Install → Enable

### 5. 連接同一個 Google Drive 帳號
Settings → **Remotely Save** → Remote Service 選 **Google Drive** → Auth → 登入**同一個** Google 帳號 → 授權

### 6. 第一次 Sync（Download）
Remotely Save 設定 → 撳 **Run once** → 佢會自動將 Mac 嗰邊嘅 notes 下載落嚟

✅ Android 完成

---

## 日常使用方法

| 情況 | 做法 |
|------|------|
| Mac 寫完，想喺電話睇 | Mac 撳 sync → 電話開 Obsidian 撳 sync |
| 電話記咗嘢，返到 Mac 想睇 | 電話撳 sync → Mac 開 Obsidian 撳 sync |
| 唔記得 sync | 開 app 嗰陣佢會自動 sync（要喺設定開 auto sync） |

**開啟自動 Sync：** Remotely Save Settings → **Schedule for auto run** → 改做 `1` 分鐘

---

## 常見問題

**Q：兩邊同時改同一個 note，點算？**
→ Remotely Save 會保留兩個版本，檔名加 `_conflict`，你自己 merge 返

**Q：Sync 失敗點辦？**
→ 大多數係 Google Drive 授權過期，重新 Auth 一次就好

**Q：免費版有冇儲存限制？**
→ 用你個人 Google Drive 嘅空間，一般 15GB 免費，筆記好細，基本上唔會用完

---

## 想要即時 Sync？

考慮 **Obsidian Sync**（官方付費方案）：
- US$8/月 或 US$96/年
- 即時 sync，唔使手動撳
- 另有版本歷史記錄
- 直接喺 Obsidian Settings → **Sync** 開通

適合：經常喺電話同 Mac 之間切換嘅用戶
