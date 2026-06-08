# 交接檔：Anki 複習小幫手 GUI 開發進度

> 寫於 2026-06-07，給接手的新 Claude 視窗閱讀

## 1. 現在的現況

### 已完成
- **新檔案已建立並通過初步驗證**：`D:\Parker_project\AnkiAIUtils\review_helper_gui.py`
  - 一個 tkinter GUI 小工具，讓使用者（Parker）在 Anki 複習時，把目前看到的卡片加入分析佇列，背景用 Gemini 產生「翻譯＋文法解析＋詞彙表」並自動寫回筆記欄位
  - 完整設計藍圖在 `C:\Users\Lenovo\.claude\plans\vectorized-moseying-wall.md`（已核准的方案文件，內容含完整程式架構說明）
- **核心邏輯已用 REPL smoke test 驗證成功**：對卡片 `cid:1769245719100` 跑過 `analyze_card()` + `write_explanation_to_card()`，確認：
  - LLM 能正確產生繁體中文「翻譯/文法解析/詞彙表」格式內容（用 `examples/toeic_dataset.txt` 範本）
  - 寫回邏輯正確：因為該卡「中文」欄位原本是空的，內容成功寫入「中文」欄位（1080 字），且 `AnkiExplainer` 欄位已清空
- **GUI 視窗目前正在執行中**：
  - 程序名稱「Anki 複習小幫手」，已用正確指令啟動：
    ```powershell
    cd "D:\Parker_project\AnkiAIUtils"
    $env:PYTHONUTF8="1"
    .\env\Scripts\python.exe review_helper_gui.py
    ```
  - **重要**：一定要用 `.\env\Scripts\python.exe`（專案虛擬環境），**不能**用系統 Python（`C:\Program Files\Python312\python.exe`），否則會報 `ModuleNotFoundError: No module named 'py_ankiconnect'`
  - 剛剛發現使用者一開始沒看到視窗，是因為視窗開在畫面外/被擋住，已用 PowerShell `SetForegroundWindow` + `MoveWindow` 把它拉到 (100,100) 位置、640x420 大小並帶到最前面

### 尚未完成 / 進行中
- **使用者尚未完成完整的 GUI 端到端互動測試**（按鈕點擊、清單顯示、狀態變化、欄位寫回）。前一次測試只確認視窗能啟動，program 本身已驗證過邏輯但 GUI 互動流程還沒被使用者實際操作過一輪
- **使用者新提出的需求：要做一份「記錄檔」**，記錄「哪一天分析了哪些題目（含題組、題號）」。已查證：
  - 卡片有「題目編號」欄位（值如 `10`、`11`、`12`）→ 對應使用者說的「題號」
  - 音檔檔名格式為 `42_TOEIC_Listening_10.mp3`，前面的 `42` 看起來像「題組」編號（但尚未跟使用者確認這個判斷是否正確）
  - 已經向使用者提出三個待確認問題（記錄欄位設計、題組判斷方式、檔案格式 CSV vs 純文字/Markdown），**目前還在等使用者回覆，記錄功能尚未開始實作**

### 重要設定值（寫死在 `review_helper_gui.py` 開頭）
```python
MODEL = "gemini/gemini-3.1-flash-lite"          # 每日額度 500，目前帳號可用模型中最高
DATASET_PATH = "examples/toeic_dataset.txt"     # 多益專屬範本，不要用預設的 explainer_dataset.txt（醫學內容會汙染輸出）
LISTENING_NOTE_TYPE = "Parker 聽力用(2026)"
POLL_INTERVAL_MS = 800
```
寫回欄位規則（已內嵌在 `write_explanation_to_card()`）：
- 「中文」欄位是空的 → 寫入「中文」
- 「中文」欄位已有內容 → 改寫入「文法結構」
- 寫入後一律清空 `AnkiExplainer` 欄位

### 使用者偏好（務必注意）
- **對話請全程使用繁體中文**，避免英文說明造成閱讀負擔（已記錄在 memory：`feedback-communication-language`）
- 使用者習慣直接請 Claude 幫忙啟動程式（不想自己打指令），之後若要重啟 GUI，直接用上面那段 PowerShell 指令在背景啟動即可

## 2. 接下來要做的測試

依照已核准方案中的端到端測試清單，逐一確認：

1. 開始複習「Parker 聽力用(2026)」筆記類型、且「中文」欄位是空的卡片，確認 GUI 上方的預覽文字約 1 秒內更新顯示該卡內容
2. 點擊「📥 加入分析佇列」，確認清單出現新項目（⏳ 待處理 → ⚙️ 處理中），下方狀態列顯示處理中數量
3. 等待約 1～1.5 分鐘，確認狀態變成 ✅ 完成、耗時欄位顯示秒數
4. 回到 Anki 重新整理該卡，確認「中文」欄位已寫入「翻譯＋文法解析＋詞彙表」格式內容，且「AnkiExplainer」欄位已清空
5. 換一張「中文」欄位已有內容的卡測試，確認改寫進「文法結構」欄位、「中文」維持不動
6. 重複點擊同一張卡（待處理/處理中狀態），確認被擋下並顯示提示，不會重複加入
7. 對已完成的卡再次點擊，確認跳出確認對話框（要不要重新分析）
8. 切到牌組列表（離開複習畫面），確認預覽顯示「（未在複習中）」、按鈕點擊有適當提示且不崩潰
9. 「📌 always on top」勾選框切換是否正常生效（視窗能蓋在 Anki 上方）
10. （選做）處理中關閉視窗，確認程式正常結束、無例外堆疊輸出

## 3. 監控項目

進行測試與後續使用時，請留意以下幾點：

- **每日額度（RPD）**：`gemini-3.1-flash-lite` 每天只有 **500 次請求**額度，重置時間約為台灣時間早上 8 點（依 Google 伺服器 UTC 午夜換算）。完整配額資訊在 `D:\Parker_project\AnkiAIUtils\GEMINI_QUOTA.md`
- **單張卡片處理時間**：約 1～1.5 分鐘／張，這是 LLM 延遲為主，目前刻意設計成單一 worker thread 循序處理（不平行），避免撞到瞬時速率限制（RPM 15）
- **欄位寫回正確性**：每次完成後務必抽查 Anki 卡片的「中文」/「文法結構」欄位內容是否正確、`AnkiExplainer` 是否已清空（不應該殘留內容）
- **錯誤處理**：若某張卡處理失敗（額度用盡、網路錯誤等），清單上該項目應顯示 ❌ 錯誤，且不影響佇列中其他項目繼續處理
- **GUI 與背景執行緒穩定性**：長時間掛著使用時，留意視窗是否會卡頓、佇列清單更新是否即時（每 200ms 從結果佇列拉取更新）
- **記錄檔功能**：等使用者回覆三個澄清問題後才開始實作，**不要自行假設欄位格式直接動手寫**——使用者尚未確認「題組」的判斷方式（從音檔檔名 `42_xxx_10.mp3` 抓開頭數字）是否正確

## 相關檔案位置一覽
- 主程式：`D:\Parker_project\AnkiAIUtils\review_helper_gui.py`
- 已核准的設計方案：`C:\Users\Lenovo\.claude\plans\vectorized-moseying-wall.md`
- 多益專屬 prompt 範本：`D:\Parker_project\AnkiAIUtils\examples\toeic_dataset.txt`
- Gemini 配額完整紀錄：`D:\Parker_project\AnkiAIUtils\GEMINI_QUOTA.md`
- Memory（專案狀態 + 溝通偏好）：
  - `C:\Users\Lenovo\.claude\projects\d--Parker-project\memory\project_ankiaiutils_status.md`
  - `C:\Users\Lenovo\.claude\projects\d--Parker-project\memory\feedback_communication_language.md`
