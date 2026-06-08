"""
Anki 複習小幫手 GUI — 單卡即時分析佇列工具

邊複習邊把目前看到的卡片加入佇列，背景慢慢用 Gemini 產生
「翻譯＋文法解析＋詞彙表」，完成後自動寫回筆記欄位。

使用方式：
    cd D:\\Parker_project\\AnkiAIUtils
    .\\env\\Scripts\\python review_helper_gui.py
"""
import os
import re
import sys
import json
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, timezone

import markdown

# 確保可以用相對路徑載入 utils/ 與 examples/（不論從哪裡執行此腳本）
os.chdir(Path(__file__).resolve().parent)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.anki import anki, updatenote
from utils.llm import load_api_keys, chat
from utils.datasets import load_dataset

MODEL = "gemini/gemini-3.1-flash-lite"
DATASET_PATH = "examples/toeic_dataset.txt"
LISTENING_NOTE_TYPE = "Parker 聽力用(2026)"
POLL_INTERVAL_MS = 800
RESULT_DRAIN_MS = 200

USAGE_FILE = "usage_count.json"
DAILY_LIMIT = 500  # gemini-3.1-flash-lite 的 RPD 上限，見 GEMINI_QUOTA.md

WINDOW_GEOMETRY_FILE = "window_geometry.json"
DEFAULT_GEOMETRY = "640x420"

STATUS_LABELS = {
    "pending": "⏳ 待處理",
    "processing": "⚙️ 處理中",
    "done": "✅ 完成",
    "error": "❌ 錯誤",
}

SOUND_RE = re.compile(r"\[sound:[^\]]+\]")
HTML_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

# LLM 偶爾不會主動把這些固定標籤加粗，這裡強制統一成粗體，避免每次輸出風格不一致
LABEL_RE = re.compile(
    r"(^|\n)(\s*-\s*)\**(意思|文法要點|文法重點|多益考點|考點|翻譯)\**(：|:)\**",
    re.M,
)


def bold_fixed_labels(text: str) -> str:
    """把『- 意思：』『- 文法要點：』『- 多益考點：』等固定標籤統一轉成粗體 markdown。"""
    return LABEL_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}**{m.group(3)}{m.group(4)}**", text)


def _quota_date() -> str:
    """回傳目前的「額度日」字串（UTC 日期，因為 Gemini RPD 在 UTC 午夜重置）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_usage() -> tuple[str, int]:
    """讀取本機累計的呼叫次數；若日期已跨過額度重置點則歸零重算。"""
    today = _quota_date()
    try:
        data = json.loads(Path(USAGE_FILE).read_text(encoding="utf-8"))
        if data.get("date") == today:
            return today, int(data.get("count", 0))
    except (FileNotFoundError, ValueError, OSError):
        pass
    return today, 0


def save_usage(date: str, count: int) -> None:
    Path(USAGE_FILE).write_text(
        json.dumps({"date": date, "count": count}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_window_geometry() -> str:
    """讀取上次關閉視窗時記錄的大小與位置；沒有紀錄則用預設值。"""
    try:
        data = json.loads(Path(WINDOW_GEOMETRY_FILE).read_text(encoding="utf-8"))
        geometry = data.get("geometry")
        if geometry:
            return geometry
    except (FileNotFoundError, ValueError, OSError):
        pass
    return DEFAULT_GEOMETRY


def save_window_geometry(geometry: str) -> None:
    Path(WINDOW_GEOMETRY_FILE).write_text(
        json.dumps({"geometry": geometry}, ensure_ascii=False),
        encoding="utf-8",
    )


def build_card_content(card_info: dict) -> str:
    """從卡片欄位中擷取要送給 LLM 的純文字內容（去除音檔標記與 HTML）。"""
    parts = [
        card_info["fields"][f]["value"].strip()
        for f in ("Front", "Back")
        if card_info["fields"].get(f, {}).get("value", "").strip()
    ]
    content = "\n".join(parts)
    content = SOUND_RE.sub("", content)
    content = HTML_RE.sub(" ", content)
    return WHITESPACE_RE.sub(" ", content).strip()


def make_preview(text: str, length: int = 40) -> str:
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length] + "…"


# 載入一次即可重複使用
load_api_keys()
_dataset = load_dataset(DATASET_PATH)


def analyze_card(item: dict) -> str:
    """呼叫 LLM，回傳產生的解析內容（純文字/markdown）。"""
    messages = _dataset + [{"role": "user", "content": item["card_content"]}]
    response = chat(model=MODEL, messages=messages, temperature=1.0, num_retries=3)
    return response["choices"][0]["message"]["content"]


def write_explanation_to_card(item: dict, explanation: str) -> None:
    """依照欄位規則把解析結果寫回筆記，並清空 AnkiExplainer 欄位。"""
    nid = item["noteId"]
    fields = item["note_fields"]
    explanation = bold_fixed_labels(explanation)
    html = markdown.markdown(explanation, extensions=["tables", "nl2br"])
    if item["modelName"] == LISTENING_NOTE_TYPE:
        zh = fields.get("中文", {}).get("value", "").strip()
        target = "中文" if not zh else "文法結構"
        updatenote(nid, fields={target: html, "AnkiExplainer": ""})
    else:
        updatenote(nid, fields={"AnkiExplainer": html})


class ReviewHelperGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anki 複習小幫手")
        self.geometry(load_window_geometry())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.current_card = None
        self.items = []  # list of queue-item dicts, in queue order

        self.work_q = queue.Queue()
        self.result_q = queue.Queue()

        self.usage_lock = threading.Lock()
        self.usage_date, self.usage_count = load_usage()

        self._build_widgets()
        self._update_counts_label()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self.after(100, self.poll_current_card)
        self.after(RESULT_DRAIN_MS, self.drain_results)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        self.queue_button = ttk.Button(
            top, text="📥 加入分析佇列", command=self.on_queue_button_click
        )
        self.queue_button.pack(side="left")

        self.preview_var = tk.StringVar(value="（未在複習中）")
        ttk.Label(top, textvariable=self.preview_var, foreground="gray").pack(
            side="left", padx=12
        )

        self.topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top,
            text="📌 always on top",
            variable=self.topmost_var,
            command=lambda: self.wm_attributes("-topmost", self.topmost_var.get()),
        ).pack(side="right")
        self.wm_attributes("-topmost", self.topmost_var.get())

        # 狀態列釘在最底部、優先保留自己的空間；中間的表格之後縮放時才會被壓縮
        self.status_var = tk.StringVar(value="待處理 0｜已完成 0")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=8).pack(
            side="bottom", fill="x"
        )

        columns = ("status", "deck", "preview", "queued_at", "elapsed")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        for col, label, width in (
            ("status", "狀態", 80),
            ("deck", "牌組", 100),
            ("preview", "預覽", 260),
            ("queued_at", "加入時間", 90),
            ("elapsed", "耗時", 70),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)

    # ------------------------------------------------------------------
    # Window lifecycle — 記住關閉前的大小與位置
    # ------------------------------------------------------------------
    def _on_close(self):
        save_window_geometry(self.geometry())
        self.destroy()

    # ------------------------------------------------------------------
    # Polling currently-reviewed card
    # ------------------------------------------------------------------
    def poll_current_card(self):
        try:
            card = anki(action="guiCurrentCard")
        except Exception:
            card = None
        self.current_card = card
        self._update_preview_label(card)
        self.after(POLL_INTERVAL_MS, self.poll_current_card)

    def _update_preview_label(self, card):
        if not card:
            self.preview_var.set("（未在複習中）")
            return
        content = build_card_content(card)
        self.preview_var.set(f"目前卡片：{make_preview(content, 50)}")

    # ------------------------------------------------------------------
    # Queue button handler
    # ------------------------------------------------------------------
    def on_queue_button_click(self):
        card = self.current_card
        if card is None:
            self._flash_status("目前不在複習畫面中，無法加入佇列")
            return

        cid = card["cardId"]
        existing = next((it for it in self.items if it["cardId"] == cid), None)
        if existing:
            if existing["status"] in ("pending", "processing"):
                self._flash_status(
                    f"這張卡片已在佇列中（{STATUS_LABELS[existing['status']]}）"
                )
                return
            if existing["status"] == "done":
                if not messagebox.askyesno(
                    "已分析過", "這張卡片已經分析完成，要重新分析嗎？"
                ):
                    return

        content = build_card_content(card)
        note_id = anki(action="cardsToNotes", cards=[cid])[0]
        item = {
            "cardId": cid,
            "noteId": note_id,
            "deckName": card.get("deckName", ""),
            "modelName": card.get("modelName", ""),
            "card_content": content,
            "note_fields": card["fields"],
            "preview": make_preview(content),
            "status": "pending",
            "queued_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "error_msg": None,
        }
        self.items.append(item)
        self._refresh_treeview()
        self.work_q.put(item)
        self._flash_status("已加入分析佇列")

    def _flash_status(self, message: str):
        self.status_var.set(message)
        self.after(2500, self._update_counts_label)

    # ------------------------------------------------------------------
    # Local usage counter（本機估算，不耗費任何 API/Cloud token）
    # ------------------------------------------------------------------
    def _record_usage(self):
        """每次實際呼叫 LLM 後記一次帳；額度日跨日時自動歸零。"""
        with self.usage_lock:
            today = _quota_date()
            if today != self.usage_date:
                self.usage_date = today
                self.usage_count = 0
            self.usage_count += 1
            save_usage(self.usage_date, self.usage_count)
        self.after(0, self._update_counts_label)

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------
    def _worker_loop(self):
        while True:
            item = self.work_q.get()
            if item is None:
                break
            self.result_q.put({"cardId": item["cardId"], "status": "processing"})
            try:
                explanation = analyze_card(item)
                self._record_usage()
                if not explanation or not explanation.strip():
                    raise RuntimeError("LLM 回傳空白內容（可能被安全過濾或暫時性錯誤），未寫入筆記，請重新分析")
                write_explanation_to_card(item, explanation)
                self.result_q.put({"cardId": item["cardId"], "status": "done"})
            except Exception as e:
                self.result_q.put(
                    {"cardId": item["cardId"], "status": "error", "error_msg": str(e)}
                )

    def drain_results(self):
        try:
            while True:
                update = self.result_q.get_nowait()
                self._apply_result_update(update)
        except queue.Empty:
            pass
        self.after(RESULT_DRAIN_MS, self.drain_results)

    def _apply_result_update(self, update: dict):
        item = next((it for it in self.items if it["cardId"] == update["cardId"]), None)
        if item is None:
            return
        item["status"] = update["status"]
        now = time.time()
        if update["status"] == "processing":
            item["started_at"] = now
        elif update["status"] in ("done", "error"):
            item["finished_at"] = now
            if update["status"] == "error":
                item["error_msg"] = update.get("error_msg")
        self._refresh_treeview()
        self._update_counts_label()

    # ------------------------------------------------------------------
    # Treeview / status bar rendering
    # ------------------------------------------------------------------
    def _refresh_treeview(self):
        self.tree.delete(*self.tree.get_children())
        for item in self.items:
            queued_str = time.strftime("%H:%M:%S", time.localtime(item["queued_at"]))
            elapsed_str = self._format_elapsed(item)
            self.tree.insert(
                "",
                "end",
                iid=str(item["cardId"]),
                values=(
                    STATUS_LABELS[item["status"]],
                    item["deckName"],
                    item["preview"],
                    queued_str,
                    elapsed_str,
                ),
            )

    def _format_elapsed(self, item) -> str:
        if item["started_at"] is None:
            return ""
        end = item["finished_at"] if item["finished_at"] is not None else time.time()
        return f"{end - item['started_at']:.0f}s"

    def _update_counts_label(self):
        pending = sum(1 for it in self.items if it["status"] == "pending")
        processing = sum(1 for it in self.items if it["status"] == "processing")
        done = sum(1 for it in self.items if it["status"] == "done")
        error = sum(1 for it in self.items if it["status"] == "error")
        self.status_var.set(
            f"待處理 {pending}｜處理中 {processing}｜已完成 {done}｜錯誤 {error}"
            f"　|　📊 今日已用 {self.usage_count}/{DAILY_LIMIT} 次（本機估算）"
        )


if __name__ == "__main__":
    app = ReviewHelperGUI()
    app.mainloop()
