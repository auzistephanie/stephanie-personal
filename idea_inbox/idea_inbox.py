"""core/idea_inbox.py — Idea Inbox: save text/image ideas to Google Sheet.

Supports:
  - Plain text messages → auto-categorized and saved
  - Photo messages → vision description → auto-categorized and saved

Required env vars:
  OPENROUTER_API_KEY  — for vision + categorization
"""
from __future__ import annotations
import base64
import os
import re as _re
import requests
from datetime import datetime, timedelta

IDEA_INBOX_TAB = "Idea Inbox"
IDEA_IMAGES_FOLDER_ID = "0AJSc0dg2eFMlUk9PVA"

_CONTEXT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "stephanie_context.md")


def _stephanie_context() -> str:
    """Load Stephanie's personal context for use in LLM prompts."""
    try:
        with open(_CONTEXT_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _hkt_now() -> str:
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%d/%m/%Y %H:%M")


def get_tg_file_url(bot_token: str, file_id: str) -> str:
    """Resolve a Telegram file_id to a download URL."""
    r = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getFile",
        params={"file_id": file_id},
        timeout=10,
    )
    r.raise_for_status()
    path = r.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{bot_token}/{path}"


def _call_openrouter(messages: list, max_tokens: int = 800) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={"model": "google/gemini-2.5-flash-lite", "max_tokens": max_tokens, "messages": messages},
        timeout=30,
    )
    if not resp.ok:
        raise Exception(f"{resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def _get_deepseek_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    try:
        import pathlib, tomli
        p = pathlib.Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
        with open(p, "rb") as f:
            return tomli.load(f).get("deepseek", {}).get("api_key", "")
    except Exception:
        return ""


def _call_deepseek(messages: list, max_tokens: int = 800) -> str:
    """Fallback to DeepSeek API when OPENROUTER_API_KEY is unavailable."""
    api_key = _get_deepseek_key()
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未設定")
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "max_tokens": max_tokens, "messages": messages},
        timeout=30,
    )
    if not resp.ok:
        raise Exception(f"DeepSeek {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_llm(messages: list, max_tokens: int = 800) -> str:
    """Use OpenRouter if available, else fall back to DeepSeek."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return _call_openrouter(messages, max_tokens)
    return _call_deepseek(messages, max_tokens)


# ── Vision ────────────────────────────────────────────────────────────────────

_NOISE_PATTERNS = [
    r"\*{0,2}用戶資訊[：:].*",
    r"\*{0,2}互動數據[：:].*",
    r"\*{0,2}評論區[提示內容]*[：:].*",
    r"\*{0,2}AI\s*生成內容提示[：:].*",
    r"\*{0,2}廣告[：:].*",
    r"\*{0,2}導航[元素]*[：:].*",
]


def _clean_description(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(l for l in lines if not any(_re.search(p, l) for p in _NOISE_PATTERNS)).strip()


def vision_describe(image_url: str) -> str:
    """Detailed description of a screenshot/image for brainstorming purposes."""
    img_r = requests.get(image_url, timeout=20)
    img_r.raise_for_status()
    ct = img_r.headers.get("content-type", "").split(";")[0].strip()
    media_type = ct if ct.startswith("image/") else "image/jpeg"
    img_b64 = base64.standard_b64encode(img_r.content).decode()

    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
            {"type": "text", "text": (
                "你係一個 idea 收集助手。呢張截圖係用戶捕捉嘅 idea，之後會用嚟 brainstorm。\n"
                "輸出格式（嚴格跟從，唔好加任何前言或後記，每行唔好超過指定字數）：\n\n"
                "第一行：格式「[名稱] — [核心功能]」，≤36字。\n"
                "第二至數行：最值得留意嘅重點，用 bullet point 列出（• 開頭），每點≤36字，總共≤120字。\n"
                "最後一行：格式「難度：[低/中/高] — [原因]」，≤36字。\n\n"
                "略去：like/comment 數字、用戶資料、評論區、AI生成提示標籤、廣告、介面導航。"
            )},
        ],
    }]
    text = _call_openrouter(messages, max_tokens=240)
    return _clean_description(text)


def _get_or_create_drive_subfolder(headers: dict, category: str) -> str:
    """Return folder ID of category subfolder inside IDEA_IMAGES_FOLDER_ID, creating if needed."""
    import json as _json
    # Search for existing subfolder
    q = (f"'{IDEA_IMAGES_FOLDER_ID}' in parents and name='{category}' "
         f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    r = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={"q": q, "fields": "files(id)", "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true"},
        timeout=15,
    )
    r.raise_for_status()
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    # Create subfolder
    metadata = {"name": category, "mimeType": "application/vnd.google-apps.folder",
                "parents": [IDEA_IMAGES_FOLDER_ID]}
    r = requests.post(
        "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        headers={**headers, "Content-Type": "application/json"},
        data=_json.dumps(metadata),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def upload_image_to_drive(image_bytes: bytes, filename: str, content_type: str = "image/jpeg",
                          category: str = "Other") -> str:
    """Upload image bytes to category subfolder in the Idea Inbox Shared Drive,
    make it link-viewable, and return a shareable Drive URL. Raises on failure."""
    import json as _json
    import google.auth.transport.requests as ga_req
    from core.sheets_client import get_creds

    creds = get_creds(["https://www.googleapis.com/auth/drive"])
    creds.refresh(ga_req.Request())
    headers = {"Authorization": f"Bearer {creds.token}"}

    folder_id = _get_or_create_drive_subfolder(headers, category)

    metadata = {"name": filename, "parents": [folder_id]}
    files = {
        "metadata": ("metadata", _json.dumps(metadata), "application/json"),
        "file": (filename, image_bytes, content_type),
    }
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
        headers=headers, files=files, timeout=30,
    )
    r.raise_for_status()
    file_id = r.json()["id"]

    # Make link-viewable
    requests.post(
        f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions?supportsAllDrives=true",
        headers={**headers, "Content-Type": "application/json"},
        json={"role": "reader", "type": "anyone"},
        timeout=15,
    )
    return f"https://drive.google.com/file/d/{file_id}/view"


# ── Auto-categorize ───────────────────────────────────────────────────────────

# Canonical category list — LLM must pick from these or suggest a new CamelCase tag.
# To add a new standard category, append it here.
IDEA_CATEGORIES = [
    "Tool",         # 外部工具/平台/app
    "Automation",   # 自動化流程/script/integration
    "Content",      # 文章/教學/參考資料
    "ClaudeCode",   # Claude skill/prompt/AI workflow + Claude Code 功能/架構
    "AI",           # AI 模型/研究/趨勢（唔特定係 Claude）
    "Business",     # 商業模式/定價/策略/行銷/增長
    "Property",     # 買樓/裝修/供款/居所相關
    "PetHealth",    # 貓貓（或其他寵物）健康/獸醫/日常照顧記錄
    "Personal",     # 個人生活，非 VNX 業務、非置業
    "Other",        # 以上都唔啱
]

# Normalization map: lowercase variations → canonical
_CATEGORY_ALIASES: dict[str, str] = {
    "claude":       "ClaudeCode",
    "claudecode":   "ClaudeCode",
    "claude code":  "ClaudeCode",
    "skill":        "ClaudeCode",
    "skills":       "ClaudeCode",
    "tools":        "Tool",
    "automations":  "Automation",
    "contents":     "Content",
    "agentic":      "AI",
    "llm":          "AI",
    "tech":         "Tool",
    "marketing":    "Business",
    "ux":           "Business",
    "property":     "Property",
    "home":         "Property",
    "renovation":   "Property",
    "pet":          "PetHealth",
    "pethealth":    "PetHealth",
    "pet health":   "PetHealth",
    "cat":          "PetHealth",
    "vet":          "PetHealth",
    "research":     "Other",      # "Research" 唔係有效 category；action 先係 "research"
}
# 注：_normalize_category() 會過濾走非 A-Za-z 字元先做 lookup，所以呢個 dict 淨係放英文 key，
# 中文 alias（例如「貓」「貓貓健康」）落嚟已經俾 regex 剝晒，放咗都冧唔中，故意唔加。


def _normalize_category(raw: str) -> str:
    """Map raw LLM output to a canonical category."""
    stripped = _re.sub(r"[^A-Za-z ]", "", raw.strip()).strip()
    lower = stripped.lower()
    # Check aliases first
    if lower in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[lower]
    # Case-insensitive match against canonical list
    for cat in IDEA_CATEGORIES:
        if cat.lower() == lower:
            return cat
    # Accept as-is if looks like valid CamelCase tag (≤3 words joined)
    # Preserve existing CamelCase; capitalize each word only if all-lowercase
    words = stripped.split()
    camel = "".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words)
    camel = _re.sub(r"[^A-Za-z]", "", camel)
    return camel if camel else "Other"


def auto_categorize(text: str) -> str:
    """Classify idea into a canonical category, or a CamelCase tag if none fit."""
    cats_str = " / ".join(IDEA_CATEGORIES[:-1])  # exclude Other
    prompt = (
        f"VNX (Venturenix Lab) 係一間做 coding/AI bootcamp 教育嘅公司。\n"
        f"根據以下 idea 內容，選出最合適嘅分類。\n"
        f"優先從以下標準分類選擇：{cats_str}\n\n"
        f"「Business」只限同 VNX 自身業務（課程/定價/營運策略）有關嘅內容；"
        f"如果係銀行/按揭/理財/個人生活資訊等同 VNX 業務無關嘅內容，請選 Personal。\n"
        f"「PetHealth」淨係貓貓（或其他寵物）健康/獸醫/日常照顧相關內容。\n\n"
        f"如果以上都唔適合，請自行創造一個簡短精準嘅英文 tag（1-2個單詞，CamelCase）。\n\n"
        f"Idea：{text[:500]}\n\n"
        f"只回覆分類名，例如：Tool 或者 ClaudeCode"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        result = _call_openrouter(messages, max_tokens=20)
        return _normalize_category(result)
    except Exception:
        return "Other"


# ── Save ──────────────────────────────────────────────────────────────────────

def save_idea(gc, text: str, note: str = "", return_row: bool = False):
    """Append one idea row to the Idea Inbox sheet with auto-category.

    Columns: Date(A) | Message(B) | Status(C) | Claude Notes(D) | Action(E) | Category(F)
    Notes format: [Category] original_note

    Returns category string, or (category, row_number) if return_row=True.
    """
    from core.config import MASTER_SHEET_ID

    category = auto_categorize(text)
    full_note = f"[{category}]" + (f" {note}" if note else "")

    ws = gc.open_by_key(MASTER_SHEET_ID).worksheet(IDEA_INBOX_TAB)
    ws.append_row(
        [_hkt_now(), text, "pending", full_note, "", category],
        value_input_option="USER_ENTERED",
    )
    if return_row:
        row_num = len(ws.col_values(1))  # last row with data
        return category, row_num
    return category


# ── Research Brief + Deep Dive ────────────────────────────────────────────────

def generate_research_brief(text: str, category: str) -> str:
    """Quick 3-question brief for 'research' ideas. Saved to Col G.

    Uses Loop Engineering (max 2 rounds) to ensure brief has required structure:
    3 numbered questions + 第一步 action.
    """
    from core.loop_engine import loop_audit, AuditResult

    context = _stephanie_context()
    prompt = (
        f"{context}\n\n"
        f"你係 Mochi，整合型 AI 顧問。以下係一個標記為「research」嘅 idea。\n"
        f"參考上面 Stephanie 嘅背景，生成精簡 Research Brief（廣東話），格式（唔好加其他文字）：\n\n"
        f"❓ 核心問題\n"
        f"1. [需要 answer 嘅問題]\n"
        f"2. [需要 answer 嘅問題]\n"
        f"3. [需要 answer 嘅問題]\n\n"
        f"→ 第一步：[一個具體行動，≤25字]\n\n"
        f"Idea（{category}）：{text[:500]}"
    )
    base_messages = [{"role": "user", "content": prompt}]

    def _generate() -> str:
        try:
            return _call_llm(base_messages, max_tokens=220)
        except Exception:
            return "❓ 未能生成 Research Brief"

    def _audit(brief: str) -> list[AuditResult]:
        has_3_questions = all(f"{i}." in brief for i in range(1, 4))
        has_first_step = "第一步" in brief
        has_content = len(brief.strip()) > 20 and "未能生成" not in brief
        return [
            AuditResult("有3個核心問題（1. 2. 3.）", has_3_questions),
            AuditResult("有第一步具體行動", has_first_step),
            AuditResult("內容完整（非錯誤訊息）", has_content),
        ]

    def _fix(brief: str, fails: list[AuditResult]) -> str:
        fail_desc = "；".join(f.criterion for f in fails)
        fix_messages = base_messages + [
            {"role": "assistant", "content": brief},
            {"role": "user", "content": (
                f"請修正以下部分（只改有問題嘅，唔好重寫整個 brief）：{fail_desc}。"
                f"保持原有格式，直接輸出修正後嘅 Research Brief。"
            )},
        ]
        try:
            return _call_llm(fix_messages, max_tokens=250)
        except Exception:
            return brief  # return original on error

    result, _, _ = loop_audit(_generate, _audit, _fix, max_rounds=2)
    return result


# ── 智囊團 ────────────────────────────────────────────────────────────────────

TEAM_DESC = (
    "你嘅智囊團（6位，分工互補，詳細設定見 docs/idea_review_council.md）：\n"
    "- Eheh（前management consultant/MBB）：拆解模糊idea做1句具體問題/目標\n"
    "- Pixel（前大廠資深工程師，自動化狂人）：具體工具/做法（xlsx skill/script/template名）\n"
    "- Sage（退休私銀理財顧問，CFA）：真實數字/市場參考值、方案比較\n"
    "- Coco（前PM，PMP，時間管理狂）：實際時間/workload/依賴\n"
    "- Mochi（風險顧問+心理學背景）：總結共識 + 主動提1個盲點\n"
    "- Pace（前COO，執行力極強）：判斷project歸屬，拆1-3步next action + owner\n"
    "流程：Eheh 開路 → Pixel/Sage 評估可行性 → Coco 把關 → Mochi 總結 → Pace 收尾"
)


def generate_deep_dive(text: str, category: str, days_since: int | None = None) -> str:
    """Full deep dive analysis for a specific idea. Saved to Col G.

    days_since: how many days ago this idea was saved (if known) — lets Eheh
    judge whether an old idea is still relevant.
    """
    context = _stephanie_context()
    age_note = ""
    if days_since is not None and days_since >= 14:
        age_note = f"\n（呢個 idea 已存在 {days_since} 日 — Eheh 判斷價值時請考慮係咪仍然 relevant）\n"
    prompt = (
        f"{context}\n\n"
        f"{TEAM_DESC}\n"
        f"{age_note}\n"
        f"參考上面 Stephanie 嘅背景，對以下 idea 做完整 Deep Dive（廣東話），格式（唔好加其他文字）：\n\n"
        f"🔍 係咩：[一句話]\n"
        f"💡 對你嘅價值（Eheh）：[視乎範疇 — 新app/裝修/VNX工作/自動化學習]\n"
        f"⚙️ 點做（Pixel）：[具體步驟 2-3點，按你現有水平]\n"
        f"🔮 仲有方案？（Sage）：[1個替代/前瞻方案，定「暫時冇」]\n"
        f"⏱️ 時間成本（Coco）：[預計時間 + 會唔會持續維護]\n"
        f"✅ Mochi 建議：[📋go / 🔍deep dive / ⏸️hold / 🗄️archive + 一句理由]\n"
        f"🚩 Pace 下一步：[1-3步next action + owner（Claude/Stephanie）]\n\n"
        f"Idea（{category}）：{text[:800]}"
    )
    try:
        return _call_llm([{"role": "user", "content": prompt}], max_tokens=500)
    except Exception:
        return "❌ 未能生成 Deep Dive 分析"


# ── Quick Mochi Take ───────────────────────────────────────────────────────────

_TECH_CATEGORIES = {"Tool", "Skill", "Automation", "ClaudeCode", "AI"}
_VNX_CATEGORIES  = {"Marketing", "Business", "UX", "Content"}
_PERSONAL_KW     = ["創業", "個人", "生活", "寵物", "習慣", "健康", "startup", "副業", "pet", "按揭", "銀行", "回贈", "居屋", "利率"]


def _classify_idea_type(category: str, text: str) -> tuple[str, str]:
    """Return (type_code, type_label) for routing to the right 智囊團 mode."""
    if category in _TECH_CATEGORIES:
        return "tech", "🔧 Tech"
    if category in _VNX_CATEGORIES:
        return "vnx", "🏢 Business"
    text_lower = text.lower()
    if any(kw in text_lower for kw in _PERSONAL_KW):
        return "personal", "🧠 個人/創業"
    return "personal", "🧠 個人/創業"  # Other → personal mode


def quick_mochi_take(text: str, category: str) -> str:
    """Generate an instant Mochi Quick Take for Telegram reply after saving.

    Returns a formatted string ready to send. Fails silently — always returns
    something even if the LLM call errors.
    """
    type_code, type_label = _classify_idea_type(category, text)

    if type_code == "tech":
        role_context = "Pixel（執行）同 Sage（技術前瞻）"
    elif type_code == "vnx":
        role_context = "Eheh（範疇價值）同 Coco（時間成本）"
    else:  # personal / Other
        role_context = "5位智囊團成員整合"

    action_hint = "go / Explore / hold / archive"

    prompt = (
        f"{TEAM_DESC}\n\n"
        f"收到一個新 idea，類型：{type_label}。請從 {role_context} 出發，用廣東話寫即時 Quick Take：\n"
        f"格式（兩行，唔好加任何 emoji/前綴/多餘文字）：\n"
        f"第一行：[核心判斷，≤20字]\n"
        f"第二行：[{action_hint}中選一] — [一句理由]\n\n"
        f"Idea：{text[:400]}"
    )

    judgment, suggestion = "已收到！", ""
    try:
        result = _call_openrouter([{"role": "user", "content": prompt}], max_tokens=120)
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        if lines:
            judgment = lines[0]
        if len(lines) > 1:
            suggestion = lines[1]
    except Exception:
        pass

    out = f"🏷️ {type_label}\n\n⚖️ <b>Mochi 初步判斷：</b>{judgment}"
    if suggestion:
        out += f"\n👉 建議：{suggestion}"
    out += "\n\n📅 週四 Cowork review 詳細討論"
    return out
