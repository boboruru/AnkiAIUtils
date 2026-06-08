# Gemini API 配置與額度紀錄

> 更新日期：2026-06-07
> 資料來源：Google AI Studio「Rate limits by model」頁面（使用者帳號（個人 Google 帳號）的實際數據，非官方公告的通用數字）
> API Key 格式：`AQ.` 開頭（存於 `API_KEYS/GEMINI`，不納入版本控制）

## 重要觀念：Gemini API 沒有「每週/每月」額度

Google 的配額只用三種單位計算，**沒有週、月的概念**：

| 縮寫 | 意義 |
|---|---|
| RPM | 每分鐘可請求次數 (Requests Per Minute) |
| TPM | 每分鐘可用 token 數 (Tokens Per Minute) |
| RPD | 每日可請求次數 (Requests Per Day，每天重置) |

## 目前帳號各模型的真實額度（截自 AI Studio 儀表板）

### ✅ 可正常使用（額度 > 0）

| 模型 | RPM | TPM | RPD | 備註 |
|---|---|---|---|---|
| **Gemini 3.1 Flash Lite** | 15 | 250K | **500** | 🌟 額度最高，建議優先採用 |
| Gemini 2.5 Flash | 5 | 250K | 20 | |
| Gemini 2.5 Flash Lite | 10 | 250K | 20 | 目前 Explainer 設定使用中 |
| Gemini 3 Flash | 5 | 250K | 20 | |
| Gemini 3.5 Flash | 5 | 250K | 20 | |
| Gemini 2.5 Flash TTS | 3 | 10K | 10 | 語音合成 |
| Gemma 4 26B | 15 | 無限 | 1,500 | 開源模型，額度最寬裕 |
| Gemma 4 31B | 15 | 無限 | 1,500 | 開源模型 |
| Gemini Embedding 1 | 100 | 30K | 1,000 | 官方 embedding 模型（目前未使用，改用本地模型） |
| Imagen 4 Generate / Ultra / Fast | - | - | 25 | 圖片生成 |

### ❌ 額度為 0（完全無法使用，換時間重試也沒用）

| 模型 |
|---|
| Gemini 2 Flash |
| Gemini 2 Flash Lite |
| Gemini 2.5 Pro |
| Gemini 2.5 Pro TTS |
| Gemini 3.1 Pro |
| Nano Banana 系列（圖片模型） |

> 這些模型一律回傳 `429 RESOURCE_EXHAUSTED`，錯誤訊息中 `limit: 0`，代表 Google 從帳號層級就把免費配額設為零，並非臨時用量超標，**換時段重跑無效**。

## 目前確定的 Gemini 配置設定

### AnkiAIUtils（Explainer 工具）
- **API Key 路徑**：`D:\Parker_project\AnkiAIUtils\API_KEYS\GEMINI`（內容為 `AQ.` 開頭金鑰，無 BOM）
- **聊天/解釋模型**：`gemini/gemini-2.5-flash-lite`（建議改成 `gemini/gemini-3.1-flash-lite`，每日額度從 20 提升到 500）
- **Embedding 模型**：`local/all-MiniLM-L6-v2`（本地 sentence-transformers，完全不耗 Gemini 配額）
- **AnkiConnect Port**：`8766`（已避開 GPS Spoof 專案使用的 8765）
- **筆記類型「Parker 聽力用(2026)」**：已新增 `AnkiExplainer` 欄位供工具寫入解釋內容

### 完整可用指令（建議升級為 3.1 Flash Lite 版本）
```powershell
cd "D:\Parker_project\AnkiAIUtils"; $env:PYTHONUTF8="1"; .\env\Scripts\python explainer.py `
    --query "deck:123" `
    --field_names "Back" `
    --model "gemini/gemini-3.1-flash-lite" `
    --embedding_model "local/all-MiniLM-L6-v2" `
    --dataset_path "examples/explainer_dataset.txt" `
    --do_sync False
```

## 已知問題與排雷紀錄
1. **`limit: 0` ≠ 用量超標**：表示帳號層級配額本來就是零，永久無法使用該模型，唯一解法是換成有額度的模型（如本文件列出的 ✅ 清單）。
2. **`AnkiExplainer` 欄位不存在**：Explainer 工具要求筆記類型必須有 `AnkiExplainer` 欄位。若遇到 `KeyError: 'AnkiExplainer'`，用 AnkiConnect 的 `modelFieldAdd` 動作新增即可（安全、不影響既有資料）。
3. **`tenacity` 套件缺失**：若遇到 `No module named 'tenacity'`，執行 `.\env\Scripts\pip install tenacity` 安裝即可，讓 LiteLLM 重試機制正常運作。
4. **每日額度算法**：RPD 在台灣時間每天固定時間重置（依 Google 伺服器時區，通常為 UTC 午夜，約為台灣時間早上 8 點），規劃批次處理進度時可參考。
