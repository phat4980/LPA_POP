"""
Reusable CustomTkinter widgets for Phase 2 UX: toast, tooltip, PDF file cards.
No extra dependencies beyond customtkinter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

try:
    import customtkinter as ctk
    import tkinter as tk
except Exception as e:
    raise ImportError("Thiếu customtkinter. Chạy: pip install customtkinter") from e


TOAST_COLORS = {
    "info": "#1565C0",
    "success": "#2E7D32",
    "warning": "#E65100",
    "error": "#C62828",
}


class Tooltip:
    """Delayed hover hint on any Tk/CTk widget."""

    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        if not self.text:
            return
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip is not None:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return

        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass

        is_dark = True
        try:
            is_dark = ctk.get_appearance_mode().lower() == "dark"
        except Exception:
            pass
        bg = "#2D2D2D" if is_dark else "#FFFDE7"
        fg = "#F5F5F5" if is_dark else "#212121"

        tk.Label(
            tip,
            text=self.text,
            justify="left",
            background=bg,
            foreground=fg,
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            wraplength=280,
            padx=8,
            pady=6,
        ).pack()
        self._tip = tip

    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class ToastHost:
    """One non-blocking toast, bottom-right of the window."""

    def __init__(self, root):
        self.root = root
        self._frame: Optional[ctk.CTkFrame] = None
        self._hide_id: Optional[str] = None

    def show(self, message: str, level: str = "info", duration_ms: int = 3500):
        self._cancel_hide()
        if self._frame is not None:
            try:
                self._frame.destroy()
            except Exception:
                pass
            self._frame = None

        accent = TOAST_COLORS.get(level, TOAST_COLORS["info"])
        frame = ctk.CTkFrame(self.root, corner_radius=10, border_width=2, border_color=accent)
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        ctk.CTkLabel(
            inner,
            text=message,
            font=ctk.CTkFont(size=13),
            wraplength=360,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            inner, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=("gray80", "gray30"),
            command=self._destroy,
        ).pack(side="right", padx=(8, 0))

        frame.place(relx=1.0, rely=1.0, x=-18, y=-18, anchor="se")
        frame.lift()
        self._frame = frame
        self._hide_id = self.root.after(duration_ms, self._destroy)

    def _cancel_hide(self):
        if self._hide_id:
            try:
                self.root.after_cancel(self._hide_id)
            except Exception:
                pass
            self._hide_id = None

    def _destroy(self):
        self._cancel_hide()
        if self._frame is not None:
            try:
                self._frame.destroy()
            except Exception:
                pass
            self._frame = None


class PdfFileCardList(ctk.CTkFrame):
    """Scrollable compact cards: filename, size, folder, per-file remove."""

    def __init__(self, master, on_change: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self._files: List[Path] = []

        self.scroll = ctk.CTkScrollableFrame(self, height=132)
        self.scroll.pack(fill="both", expand=True)
        self.scroll.grid_columnconfigure(0, weight=1)
        self._show_empty()

    @property
    def files(self) -> List[Path]:
        return list(self._files)

    def set_files(self, files: List[Path]):
        seen = set()
        unique: List[Path] = []
        for f in files:
            key = str(f)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        self._files = unique
        self._rebuild()
        self._notify()

    def add_files(self, files: List[Path]):
        existing = {str(f) for f in self._files}
        changed = False
        for f in files:
            if str(f) not in existing:
                self._files.append(f)
                existing.add(str(f))
                changed = True
        if changed:
            self._rebuild()
            self._notify()

    def clear(self):
        self._files.clear()
        self._rebuild()
        self._notify()

    def refresh(self):
        self._rebuild()

    def _notify(self):
        if self.on_change:
            self.on_change()

    def _remove(self, path: Path):
        self._files = [f for f in self._files if f != path]
        self._rebuild()
        self._notify()

    def _show_empty(self):
        ctk.CTkLabel(
            self.scroll,
            text="Chưa có file PDF.\nDùng «Thêm File» hoặc «Thêm Thư Mục» bên dưới.",
            text_color="gray55",
            font=ctk.CTkFont(size=12),
            justify="center",
        ).grid(row=0, column=0, pady=28)

    def _rebuild(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        if not self._files:
            self._show_empty()
            return
        for i, path in enumerate(self._files):
            self._make_row(i, path)

    def _make_row(self, index: int, path: Path):
        bg = ("gray90", "gray22") if index % 2 == 0 else ("gray95", "gray17")
        row = ctk.CTkFrame(self.scroll, fg_color=bg, corner_radius=8)
        row.grid(row=index, column=0, sticky="ew", pady=2, padx=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row,
            text=f"📄  {path.name}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(8, 8), pady=(6, 0))

        ctk.CTkLabel(
            row,
            text=f"{_format_size(path)}   ·   {path.parent}",
            font=ctk.CTkFont(size=11),
            text_color="gray55",
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(28, 8), pady=(0, 6))

        rm = ctk.CTkButton(
            row, text="✕", width=32, height=28,
            fg_color="transparent",
            text_color=("#C62828", "#EF9A9A"),
            hover_color=("gray80", "gray30"),
            command=lambda p=path: self._remove(p),
        )
        rm.grid(row=0, column=2, rowspan=2, padx=(0, 6))
        Tooltip(rm, f"Gỡ {path.name} khỏi danh sách")


def _format_size(path: Path) -> str:
    try:
        kb = os.path.getsize(path) / 1024
        return f"{kb / 1024:.1f} MB" if kb > 1024 else f"{kb:.0f} KB"
    except OSError:
        return "—"
