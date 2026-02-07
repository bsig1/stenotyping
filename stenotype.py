import json
import os
import random
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import re


# -----------------------------
# Utilities
# -----------------------------

def tokenize_source_text(text: str) -> list[str]:
    """
    Sequential word tokenizer for quote mode.

    - Preserves punctuation attached to words (night., rage,)
    - Collapses whitespace
    """
    text = normalize_text(text)
    if not text:
        return []

    # Split on whitespace only; punctuation stays with the word
    return re.split(r"\s+", text)

def load_word_bank(path: str) -> list[str]:
    words: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            words.append(s)
    return words


def normalize_text(s: str) -> str:
    return " ".join(s.strip().split())


def load_dictionary_json(path: str) -> dict[str, list[str]]:
    """
    Supports BOTH:
      1) translation -> strokes
         { "message": ["PHEPBLG"], "cellular": "KREL/HRER" }

      2) plover style stroke -> translation
         { "PHEPBLG": "message", "KREL/HRER": "cellular" }

    Returns normalized:
      {translation: [stroke, stroke, ...]}
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("Dictionary JSON must be an object.")

    def looks_like_stroke(s: str) -> bool:
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-/*0123456789")
        return all(c in allowed for c in s) and ("/" in s or "-" in s or "*" in s)

    items = list(raw.items())
    if not items:
        return {}

    key_strokeish = sum(isinstance(k, str) and looks_like_stroke(k) for k, _ in items)
    val_stringish = sum(isinstance(v, str) for _, v in items)

    # If a lot of keys look like strokes AND values are mostly strings -> invert
    if key_strokeish >= max(1, len(items) // 4) and val_stringish >= max(1, (len(items) * 3) // 4):
        out: dict[str, list[str]] = {}
        for stroke, translation in raw.items():
            if not (isinstance(stroke, str) and isinstance(translation, str)):
                continue
            t = normalize_text(translation)
            out.setdefault(t, []).append(stroke)
        return out

    # Otherwise treat as translation->strokes
    out: dict[str, list[str]] = {}
    for translation, strokes in raw.items():
        if not isinstance(translation, str):
            continue
        t = normalize_text(translation)
        if isinstance(strokes, str):
            out[t] = [strokes]
        elif isinstance(strokes, list) and all(isinstance(x, str) for x in strokes):
            out[t] = strokes
    return out

def config_path() -> str:
    base = os.path.join(os.path.expanduser("~"), ".config", "plover_practice")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "config.json")


def save_config(word_bank_path: str | None, dict_path: str | None):
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump({"word_bank_path": word_bank_path, "dict_path": dict_path}, f, indent=2)


def load_config() -> dict:
    p = config_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


# -----------------------------
# Main App
# -----------------------------

class PloverPracticeApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self.master = master

        self.set_app_icon(self.master)

        # Data
        self.word_bank_path: str | None = None
        self.dict_path: str | None = None
        self.word_bank: list[str] = []
        self.steno_dict: dict[str, list[str]] = {}

        # Modes:
        #   "bank_random"  -> random word/phrase from file
        #   "quote_seq"    -> sequential lines from source text box
        self.source_mode = "bank_random"

        # Quote mode state
        self.quote_tokens: list[str] = []
        self.quote_idx: int = 0

        # Guard: prevents Enter + trace from double-counting/advancing
        self._pending_advance = False

        # Practice state
        self.current_word: str | None = None
        self.current_started_at: float | None = None
        self.session_started_at: float | None = None

        # Stats
        self.total_attempts = 0
        self.correct_attempts = 0
        self.total_correct_chars = 0
        self.streak = 0
        self.best_streak = 0

        self.pack(fill="both", expand=True)
        self._style()
        self._build_ui()
        self._bind_keys()
        self._tick_stats()

        self._reset_session()
        self._autoload_last_files()

    # -------------------------
    # Styling / Layout
    # -------------------------

    def set_app_icon(self, root, path="icon.png"):
        try:
            from PIL import Image, ImageTk
            icon = ImageTk.PhotoImage(Image.open(path))
            root.iconphoto(True, icon)
            root._icon_ref = icon  # prevent GC
        except Exception as e:
            print("Icon load failed:", e)

    def _style(self):
        style = ttk.Style(self.master)

        preferred = ["clam", "alt", "default"]
        for t in preferred:
            if t in style.theme_names():
                style.theme_use(t)
                break

        self.COL_BG = "#0b1220"
        self.COL_PANEL = "#101a2e"
        self.COL_TEXT = "#e6edf3"
        self.COL_MUTED = "#9fb1c7"
        self.COL_ACCENT = "#7aa2f7"
        self.COL_GOOD = "#4ade80"
        self.COL_BAD = "#fb7185"
        self.COL_BORDER = "#24324a"
        self.COL_ENTRY = "#0f172a"

        self.master.configure(bg=self.COL_BG)

        style.configure("TFrame", background=self.COL_BG)
        style.configure("Panel.TFrame", background=self.COL_PANEL)
        style.configure("TLabel", background=self.COL_BG, foreground=self.COL_TEXT)
        style.configure("Muted.TLabel", background=self.COL_BG, foreground=self.COL_MUTED)
        style.configure("Panel.TLabel", background=self.COL_PANEL, foreground=self.COL_TEXT)
        style.configure("PanelMuted.TLabel", background=self.COL_PANEL, foreground=self.COL_MUTED)

        style.configure("TButton", padding=(12, 8))
        style.map(
            "Accent.TButton",
            foreground=[("!disabled", self.COL_BG)],
            background=[("!disabled", self.COL_ACCENT)],
        )
        style.configure("Accent.TButton", background=self.COL_ACCENT)

        style.configure("Card.TFrame", background=self.COL_PANEL, relief="flat")
        style.configure("CardTitle.TLabel", background=self.COL_PANEL, foreground=self.COL_TEXT, font=("Segoe UI", 12, "bold"))

        style.configure("Big.TLabel", background=self.COL_BG, foreground=self.COL_TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("Word.TLabel", background=self.COL_BG, foreground=self.COL_TEXT, font=("Segoe UI", 28, "bold"))
        style.configure("Hint.TLabel", background=self.COL_BG, foreground=self.COL_MUTED, font=("Segoe UI", 12))

        style.configure("TEntry", padding=(10, 10))
        style.configure("EntryWrap.TFrame", background=self.COL_ENTRY)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Top bar ──────────────────────────────────────────────
        top = ttk.Frame(self, style="TFrame")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Plover Practice", style="Big.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        buttons = ttk.Frame(top)
        buttons.grid(row=0, column=1, sticky="e")

        ttk.Button(buttons, text="Load Word Bank", command=self.on_load_word_bank).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Load Dictionary JSON", command=self.on_load_dict).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Next", command=self.on_next_word).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(buttons, text="Reset Session", command=self._reset_session).grid(row=0, column=3)

        # ── Main split ───────────────────────────────────────────
        main = ttk.Frame(self)
        main.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 16))
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # ── Left pane (practice) ─────────────────────────────────
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        # spacer row (THIS pushes entry to bottom)
        left.rowconfigure(5, weight=1)

        ttk.Label(left, text="Source Text (one quote/line)", style="Muted.TLabel").grid(row=0, column=0, sticky="w")

        self.txt_source = tk.Text(
            left,
            height=6,
            wrap="word",
            bg=self.COL_ENTRY,
            fg=self.COL_TEXT,
            insertbackground=self.COL_TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.COL_BORDER,
        )
        self.txt_source.grid(row=1, column=0, sticky="ew", pady=(6, 10))

        mode_bar = ttk.Frame(left)
        mode_bar.grid(row=2, column=0, sticky="ew", pady=(0, 14))

        ttk.Button(mode_bar, text="Use Source Text (Sequential)", command=self.use_quote_mode).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(mode_bar, text="Restart Quote", command=self.restart_quote).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(mode_bar, text="Use Word Bank (Random)", command=self.use_bank_random).grid(row=0, column=2)

        self.lbl_word = ttk.Label(left, text="—", style="Word.TLabel")
        self.lbl_word.grid(row=3, column=0, sticky="w", pady=(0, 6))

        self.lbl_hint = ttk.Label(
            left,
            text="Load a word bank to begin.",
            wraplength=350,
            justify="left",
            style="Hint.TLabel",
        )
        self.lbl_hint.grid(row=4, column=0, sticky="w", pady=(0, 16))

        # ── Bottom entry (pinned) ─────────────────────────────────
        entry_wrap = ttk.Frame(left, style="EntryWrap.TFrame")
        entry_wrap.grid(row=6, column=0, sticky="ew")
        entry_wrap.columnconfigure(0, weight=1)

        self.var_input = tk.StringVar()
        self.entry = ttk.Entry(entry_wrap, textvariable=self.var_input)
        self.var_input.trace_add("write", self.on_text_change)
        self.entry.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        self.lbl_feedback = ttk.Label(left, text="Type the word/phrase…", style="Muted.TLabel")
        self.lbl_feedback.grid(row=7, column=0, sticky="w", pady=(10, 0))

        # ── Right pane (stats) ────────────────────────────────────
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        self.card_stats = self._make_card(
            right,
            title="Session Stats",
            body_lines=[
                ("WPM", "0"),
                ("Accuracy", "0%"),
                ("Correct / Attempts", "0 / 0"),
                ("Streak", "0 (best 0)"),
                ("Time", "0:00"),
            ],
        )
        self.card_stats.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self.card_files = self._make_card(
            right,
            title="Loaded Files",
            body_lines=[
                ("Word bank", "—"),
                ("Dictionary", "—"),
                ("Bank size", "0"),
                ("Dict entries", "0"),
            ],
        )
        self.card_files.grid(row=1, column=0, sticky="ew")

    def _make_card(self, parent, title: str, body_lines: list[tuple[str, str]]) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame")
        card.columnconfigure(0, weight=1)

        hdr = ttk.Label(card, text=title, style="CardTitle.TLabel")
        hdr.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        body = ttk.Frame(card, style="Panel.TFrame")
        body.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        body.columnconfigure(1, weight=1)

        if not hasattr(self, "_card_value_labels"):
            self._card_value_labels = {}

        for i, (k, v) in enumerate(body_lines):
            lk = ttk.Label(body, text=k, style="PanelMuted.TLabel")
            lv = ttk.Label(body, text=v, style="Panel.TLabel")
            lk.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=3)
            lv.grid(row=i, column=1, sticky="e", pady=3)
            self._card_value_labels[(title, k)] = lv

        return card

    def _bind_keys(self):
        # Keep Enter as a convenience, but do NOT double-count:
        # We'll make Enter just "force advance if already correct and pending isn't set".
        self.master.bind("<Return>", lambda e: self.on_submit())
        self.master.bind("<Escape>", lambda e: self.var_input.set(""))
        self.entry.focus_set()

    # -------------------------
    # Modes
    # -------------------------

    def use_quote_mode(self):
        self.source_mode = "quote_seq"
        self.restart_quote()

    def restart_quote(self):
        raw = self.txt_source.get("1.0", "end").strip()
        self.quote_tokens = tokenize_source_text(raw)
        self.quote_idx = 0

        if not self.quote_tokens:
            self.current_word = None
            self.lbl_word.configure(text="—")
            self.lbl_hint.configure(text="Paste text above (one quote/line), then press Restart Quote.")
            return

        self.session_started_at = self.session_started_at or time.time()
        self._set_current(self.quote_tokens[self.quote_idx])
        self.lbl_feedback.configure(text="Quote mode: type the line exactly.", foreground=self.COL_MUTED)

    def use_bank_random(self):
        self.source_mode = "bank_random"
        if not self.word_bank:
            self.lbl_feedback.configure(text="Load a word bank first.", foreground=self.COL_BAD)
            return
        self.session_started_at = self.session_started_at or time.time()
        self._pick_new_word_from_bank()
        self.lbl_feedback.configure(text="Word bank mode: random.", foreground=self.COL_MUTED)

    # -------------------------
    # File loading
    # -------------------------

    def on_load_word_bank(self):
        path = filedialog.askopenfilename(
            title="Select word bank (.txt)",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            words = load_word_bank(path)
            if not words:
                raise ValueError("No usable lines found (empty or commented).")
        except Exception as e:
            messagebox.showerror("Failed to load word bank", str(e))
            return

        self.word_bank_path = path
        self.word_bank = words
        self._set_card_value("Loaded Files", "Word bank", os.path.basename(path))
        self._set_card_value("Loaded Files", "Bank size", str(len(self.word_bank)))
        self._maybe_start()
        save_config(self.word_bank_path, self.dict_path)

    def on_load_dict(self):
        path = filedialog.askopenfilename(
            title="Select dictionary (.json)",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            d = load_dictionary_json(path)
        except Exception as e:
            messagebox.showerror("Failed to load dictionary JSON", str(e))
            return

        self.dict_path = path
        self.steno_dict = d
        self._set_card_value("Loaded Files", "Dictionary", os.path.basename(path))
        self._set_card_value("Loaded Files", "Dict entries", str(len(self.steno_dict)))
        self._update_hint()
        save_config(self.word_bank_path, self.dict_path)

    def _autoload_last_files(self):
        cfg = load_config()
        bank = cfg.get("word_bank_path")
        dct = cfg.get("dict_path")

        if bank and os.path.exists(bank):
            try:
                self.word_bank = load_word_bank(bank)
                self.word_bank_path = bank
                self._set_card_value("Loaded Files", "Word bank", os.path.basename(bank))
                self._set_card_value("Loaded Files", "Bank size", str(len(self.word_bank)))
            except Exception:
                pass

        if dct and os.path.exists(dct):
            try:
                self.steno_dict = load_dictionary_json(dct)
                self.dict_path = dct
                self._set_card_value("Loaded Files", "Dictionary", os.path.basename(dct))
                self._set_card_value("Loaded Files", "Dict entries", str(len(self.steno_dict)))
            except Exception:
                pass

        self._maybe_start()
        self._update_hint()

    # -------------------------
    # Practice flow
    # -------------------------

    def _set_current(self, text: str):
        self.current_word = text
        self.current_started_at = time.time()
        self.lbl_word.configure(text=self.current_word)
        self.var_input.set("")
        self._update_hint()

    def _pick_new_word_from_bank(self):
        if not self.word_bank:
            self.current_word = None
            self.lbl_word.configure(text="—")
            return
        self._set_current(random.choice(self.word_bank))

    def _maybe_start(self):
        # If nothing set yet, default to bank random (if bank loaded)
        if self.current_word is None and self.word_bank:
            self.session_started_at = time.time()
            self.source_mode = "bank_random"
            self._pick_new_word_from_bank()
            self.lbl_feedback.configure(text="Word bank mode: random.", foreground=self.COL_MUTED)
            self.entry.focus_set()

    def advance_target(self):
        self._pending_advance = False

        if self.source_mode == "quote_seq":
            if not self.quote_tokens:
                return
            if self.quote_idx < len(self.quote_tokens) - 1:
                self.quote_idx += 1
                self._set_current(self.quote_tokens[self.quote_idx])
            else:
                self.lbl_feedback.configure(
                    text="Quote complete 🎉  (Restart Quote to run again)",
                    foreground=self.COL_GOOD,
                )
                self.lbl_word.configure(text="—")
                self.current_word = None
            return

        elif self.source_mode == "bank_random":
            # called after a correct attempt in word bank mode
            if not self.word_bank:
                return
            self._pick_new_word_from_bank()
            return

        else:
            # if you add more modes later, safe default:
            if self.word_bank:
                self._pick_new_word_from_bank()


    def on_next_word(self):
        # Manual skip (does not count)
        self._pending_advance = False
        self.streak = 0

        if self.source_mode == "quote_seq":
            if not self.quote_tokens:
                return
            if self.quote_idx < len(self.quote_tokens) - 1:
                self.quote_idx += 1
                self._set_current(self.quote_tokens[self.quote_idx])
                self.lbl_feedback.configure(text="Skipped.", foreground=self.COL_BAD)
            else:
                self.lbl_feedback.configure(text="Already at end of quote list.", foreground=self.COL_MUTED)
            return

        # bank_random skip (default)
        if not self.word_bank:
            return
        self.session_started_at = self.session_started_at or time.time()
        self._pick_new_word_from_bank()
        self.lbl_feedback.configure(text="Skipped.", foreground=self.COL_BAD)


    def on_submit(self):
        # Enter convenience:
        # If the text matches and we haven't already scheduled advance, schedule it.
        if not self.current_word or self._pending_advance:
            return
        typed = normalize_text(self.var_input.get())
        target = normalize_text(self.current_word)
        if typed == target:
            self._count_correct_and_schedule_advance()

    def _count_correct_and_schedule_advance(self):
        if self._pending_advance:
            return
        self._pending_advance = True

        target = normalize_text(self.current_word or "")

        self.correct_attempts += 1
        self.total_attempts += 1
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        self.total_correct_chars += len(target)

        self.advance_target()

    def on_text_change(self, *_):
        if not self.current_word:
            return

        typed = normalize_text(self.var_input.get())
        target = normalize_text(self.current_word)

        if not typed:
            self.lbl_feedback.configure(text="Type the word/phrase…", foreground=self.COL_MUTED)
            self.lbl_word.configure(foreground=self.COL_TEXT)
            return

        # Exact match -> count + advance once
        if typed == target:
            self._count_correct_and_schedule_advance()
            return

        # Prefix match -> neutral (only really useful for word-bank single words)
        if target.startswith(typed):
            self.lbl_feedback.configure(text="…", foreground=self.COL_MUTED)
            self.lbl_word.configure(foreground=self.COL_TEXT)
            return

        # Otherwise -> incorrect so far (doesn't count as an attempt yet)
        self.lbl_feedback.configure(text="✗ Incorrect", foreground=self.COL_BAD)
        self.lbl_word.configure(foreground=self.COL_BAD)

    def _hint_for(self, word: str, max_hints=20) -> str:
        clean = word.strip(".,!?;:\"'()[]{}").lower()
        strokes = self.steno_dict.get(clean)
        if strokes:
            joined = " | ".join(strokes[:max_hints])
            if len(strokes) > max_hints:
                joined += " | …"
            return f"Steno:\n{joined}"
        return "(no steno mapping found)"

    def _update_hint(self):
        if not self.current_word:
            self.lbl_hint.configure(text="Load a word bank or paste Source Text above.")
            return
        self.lbl_hint.configure(text=self._hint_for(normalize_text(self.current_word)))

    # -------------------------
    # Stats
    # -------------------------

    def _reset_session(self):
        self._pending_advance = False

        self.current_word = None
        self.current_started_at = None
        self.session_started_at = None

        self.total_attempts = 0
        self.correct_attempts = 0
        self.total_correct_chars = 0
        self.streak = 0
        self.best_streak = 0

        self.var_input.set("")
        self.lbl_word.configure(text="—")
        self.lbl_feedback.configure(text="Type the word/phrase…", foreground=self.COL_MUTED)
        self._update_stats_labels()

        # preserve loaded word bank/dict; restart if possible
        self._maybe_start()
        self._update_hint()

    def _elapsed_seconds(self) -> int:
        if self.session_started_at is None:
            return 0
        return max(0, int(time.time() - self.session_started_at))

    def _compute_wpm(self) -> int:
        seconds = self._elapsed_seconds()
        if seconds <= 0:
            return 0
        minutes = seconds / 60.0
        words_equiv = (self.total_correct_chars / 5.0)
        return int(round(words_equiv / minutes)) if minutes > 0 else 0

    def _compute_accuracy(self) -> int:
        if self.total_attempts == 0:
            return 0
        return int(round(100.0 * (self.correct_attempts / self.total_attempts)))

    def _update_stats_labels(self):
        wpm = self._compute_wpm()
        acc = self._compute_accuracy()
        sec = self._elapsed_seconds()
        mm = sec // 60
        ss = sec % 60

        self._set_card_value("Session Stats", "WPM", str(wpm))
        self._set_card_value("Session Stats", "Accuracy", f"{acc}%")
        self._set_card_value("Session Stats", "Correct / Attempts", f"{self.correct_attempts} / {self.total_attempts}")
        self._set_card_value("Session Stats", "Streak", f"{self.streak} (best {self.best_streak})")
        self._set_card_value("Session Stats", "Time", f"{mm}:{ss:02d}")

    def _set_card_value(self, card_title: str, key: str, value: str):
        lbl = getattr(self, "_card_value_labels", {}).get((card_title, key))
        if lbl is not None:
            lbl.configure(text=value)

    def _tick_stats(self):
        self._update_stats_labels()
        self.after(250, self._tick_stats)


def main():
    root = tk.Tk()
    root.title("Plover Practice")
    root.geometry("980x640")
    root.minsize(860, 520)

    app = PloverPracticeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
