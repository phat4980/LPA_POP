"""
PO Management Tool — Modern UI (CustomTkinter)

Sidebar: merge, dashboard, staff lookup, settings.
File cards, toast notices, hover tooltips — no extra UI libraries.
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, ttk

try:
    # pyrefly: ignore [missing-import]
    import customtkinter as ctk
except ImportError as e:
    raise ImportError(
        "Thiếu thư viện customtkinter. Trong venv hãy chạy: pip install customtkinter"
    ) from e

from config import (
    APP_NAME, APP_VERSION, DEFAULT_PATTERN,
    resource_path, AppSettings,
)
from core import (
    setup_logging,
    collect_input_pdfs,
    read_store_list,
    read_code_name_map,
    read_code_staff_map,
    extract_store_pages,
    merge_and_write,
    AnnotationResult,
)
from ui_widgets import Tooltip, ToastHost, PdfFileCardList


# ===== Data Models for Dashboard =====

@dataclass
class ProcessingSummary:
    timestamp: str = ""
    total_pdfs: int = 0
    total_pages: int = 0
    total_qty: int = 0
    total_codes_expected: int = 0
    total_codes_found: int = 0
    missing_codes: List[str] = field(default_factory=list)
    extra_codes: List[str] = field(default_factory=list)
    staff_totals: Dict[str, int] = field(default_factory=dict)
    staff_store_map: Dict[str, List[str]] = field(default_factory=dict)
    store_qty_map: Dict[str, int] = field(default_factory=dict)
    code_name_map: Dict[str, str] = field(default_factory=dict)
    code_staff_map: Dict[str, str] = field(default_factory=dict)
    output_path: str = ""


# ===== GUI Log Handler =====

class CtkLogHandler(logging.Handler):
    """Logging handler that posts color-tagged messages to a Tk Text widget."""

    def __init__(self, callback: Callable[[str, str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        level = record.levelname
        try:
            self.callback(msg + "\n", level)
        except Exception:
            pass


# ===== Step Progress Indicator Component =====

class ModernStepTracker(ctk.CTkFrame):
    """Visual multi-step progress bar with 4 distinct phases."""

    STEPS = [
        ("1. Đọc file", "read"),
        ("2. Trích xuất PO", "extract"),
        ("3. Gộp PDF & Ghi Qty", "merge"),
        ("4. Hoàn tất", "done"),
    ]

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.step_widgets: List[ctk.CTkLabel] = []
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for i, (text, _) in enumerate(self.STEPS):
            lbl = ctk.CTkLabel(
                self,
                text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=("gray85", "gray25"),
                text_color=("gray40", "gray70"),
                corner_radius=8,
                height=32
            )
            lbl.grid(row=0, column=i, padx=4, sticky="ew")
            self.step_widgets.append(lbl)

    def reset(self):
        for lbl in self.step_widgets:
            lbl.configure(
                fg_color=("gray85", "gray25"),
                text_color=("gray40", "gray70")
            )

    def set_active(self, step_idx: int):
        for i, lbl in enumerate(self.step_widgets):
            if i < step_idx:
                lbl.configure(
                    fg_color=("#4CAF50", "#2E7D32"),
                    text_color="#FFFFFF"
                )
            elif i == step_idx:
                lbl.configure(
                    fg_color=("#2196F3", "#1976D2"),
                    text_color="#FFFFFF"
                )
            else:
                lbl.configure(
                    fg_color=("gray85", "gray25"),
                    text_color=("gray40", "gray70")
                )

    def set_complete(self):
        for lbl in self.step_widgets:
            lbl.configure(
                fg_color=("#4CAF50", "#2E7D32"),
                text_color="#FFFFFF"
            )

    def set_error(self, step_idx: int):
        if 0 <= step_idx < len(self.step_widgets):
            self.step_widgets[step_idx].configure(
                fg_color=("#F44336", "#C62828"),
                text_color="#FFFFFF"
            )


# ===== Modern PO App Main Window =====

class ModernPOApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Load persisted settings
        self.settings = AppSettings.load()
        ctk.set_appearance_mode(self.settings.theme_mode)
        ctk.set_default_color_theme(self.settings.color_theme)

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{self.settings.window_width}x{self.settings.window_height}")
        self.minsize(1000, 700)

        # Set App Icon
        self._set_icon()

        # State variables
        self.summary_data: Optional[ProcessingSummary] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._input_files: List[Path] = []
        self._current_view_name = "merge"
        self._search_debounce_timer: Optional[str] = None
        self._dash_search_debounce: Optional[str] = None
        self.toast = ToastHost(self)

        # Build Theme & Styles
        self._setup_treeview_styles()

        # Build Layout
        self._build_layout()
        self._restore_settings()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        """Set window and taskbar icons."""
        try:
            ico_path = resource_path("assets/icon/app.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('lpa.pop.merge.tool.2.0')
                except Exception:
                    pass
        except Exception:
            pass

    def _setup_treeview_styles(self):
        """Configure modern styles for all ttk.Treeview widgets with consistent text color."""
        self.ttk_style = ttk.Style()
        is_dark = ctk.get_appearance_mode().lower() == "dark"

        bg_main = "#1E1E1E" if is_dark else "#FFFFFF"
        fg_main = "#E0E0E0" if is_dark else "#212121"
        bg_head = "#2D2D2D" if is_dark else "#E0E0E0"
        fg_head = "#FFFFFF" if is_dark else "#000000"
        bg_sel = "#1976D2" if is_dark else "#2196F3"

        self.ttk_style.theme_use("clam")

        self.ttk_style.configure(
            "Modern.Treeview",
            background=bg_main,
            foreground=fg_main,
            fieldbackground=bg_main,
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
            relief="flat"
        )
        self.ttk_style.map(
            "Modern.Treeview",
            background=[("selected", bg_sel)],
            foreground=[("selected", "#FFFFFF")]
        )

        self.ttk_style.configure(
            "Modern.Treeview.Heading",
            background=bg_head,
            foreground=fg_head,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 4)
        )
        self.ttk_style.map(
            "Modern.Treeview.Heading",
            background=[("active", "#3E3E3E" if is_dark else "#D0D0D0")]
        )

        # Apply consistent row tags if trees are initialized
        self._apply_tree_tags()

    def _apply_tree_tags(self):
        """Apply unified color palette to all treeviews."""
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        even_bg = "#242424" if is_dark else "#F7F7F7"
        odd_bg = "#1E1E1E" if is_dark else "#FFFFFF"
        fg_col = "#E0E0E0" if is_dark else "#212121"

        trees = []
        if hasattr(self, "dash_tree"):
            trees.append(self.dash_tree)
        if hasattr(self, "staff_tree"):
            trees.append(self.staff_tree)

        for tree in trees:
            tree.tag_configure("row_even", background=even_bg, foreground=fg_col)
            tree.tag_configure("row_odd", background=odd_bg, foreground=fg_col)

        if hasattr(self, "dash_tree"):
            self.dash_tree.tag_configure("merged", foreground="#66BB6A")
            self.dash_tree.tag_configure("missing", foreground="#EF5350")
            self.dash_tree.tag_configure("extra", foreground="#FFA726")
            self.dash_tree.tag_configure("standard", foreground="#42A5F5")

    def _on_close(self):
        """Persist settings on close."""
        try:
            self.settings.window_width = self.winfo_width()
            self.settings.window_height = self.winfo_height()
            self.settings.save()
        except Exception:
            pass
        self.destroy()

    # ===== Layout Architecture =====

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Left Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        # Sidebar Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="📑 LPA PO Merge",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.ver_label = ctk.CTkLabel(
            self.sidebar_frame,
            text=f"Phiên bản {APP_VERSION}",
            font=ctk.CTkFont(size=11),
            text_color="gray60"
        )
        self.ver_label.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Navigation Buttons
        self.nav_btns: Dict[str, ctk.CTkButton] = {}

        nav_items = [
            ("merge", "📑  Xử lý PO", "Chọn PDF, danh sách mã, rồi gộp thành 1 file PO"),
            ("dashboard", "📊  Thống kê & Báo cáo", "KPI, mã thiếu/dư, qty theo staff sau khi merge"),
            ("staff", "👥  Tra cứu Staff", "Tìm cửa hàng theo nhân viên từ file CSV"),
            ("settings", "⚙️  Cài đặt", "Regex mã cửa hàng và tone màu giao diện"),
        ]

        for i, (key, label, hint) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                command=lambda k=key: self._show_view(k)
            )
            btn.grid(row=i, column=0, padx=12, pady=4, sticky="ew")
            self.nav_btns[key] = btn
            Tooltip(btn, hint)

        # 2. Main Content Container
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)

        # Views
        self.views: Dict[str, ctk.CTkFrame] = {}
        self._init_merge_view()
        self._init_dashboard_view()
        self._init_staff_view()
        self._init_settings_view()

        # Grid all views in the same content cell once at startup for instant tab switching
        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

        # Apply unified treeview colors
        self._apply_tree_tags()

        # Show default view
        self._show_view("merge")

    def _show_view(self, view_name: str):
        """Switch between sidebar tabs instantaneously (0ms lag) using tkraise()."""
        self._current_view_name = view_name

        # Auto-load staff directory if switching to staff tab and not loaded yet
        if view_name == "staff":
            if not hasattr(self, "_staff_directory_data") or not self._staff_directory_data:
                list_file = self.list_entry.get().strip()
                if list_file and Path(list_file).exists():
                    self._load_staff_directory(Path(list_file))
                elif self.settings.last_list_file and Path(self.settings.last_list_file).exists():
                    self._load_staff_directory(Path(self.settings.last_list_file))

        # Instantaneous tab raise without tearing down or rebuilding geometry
        if view_name in self.views:
            self.views[view_name].tkraise()

        # Update button active state
        for k, btn in self.nav_btns.items():
            if k == view_name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

    # ===== VIEW 1: PO MERGE WORKSPACE =====

    def _init_merge_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(4, weight=1)  # Log panel expands

        # 1. PDF file cards
        pdf_card = ctk.CTkFrame(view)
        pdf_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        pdf_card.grid_columnconfigure(0, weight=1)

        pdf_header = ctk.CTkFrame(pdf_card, fg_color="transparent")
        pdf_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        ctk.CTkLabel(
            pdf_header,
            text="📁 1. Danh sách file PDF Purchase Order",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        self.pdf_count_badge = ctk.CTkLabel(
            pdf_header,
            text="0 file được chọn",
            font=ctk.CTkFont(size=11),
            text_color="gray60"
        )
        self.pdf_count_badge.pack(side="right")

        self.pdf_list = PdfFileCardList(pdf_card, on_change=self._on_pdf_list_changed)
        self.pdf_list.grid(row=1, column=0, sticky="ew", padx=12, pady=4)

        btn_bar = ctk.CTkFrame(pdf_card, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 8))

        add_files_btn = ctk.CTkButton(
            btn_bar, text="➕ Thêm File", width=100, height=30,
            command=self._choose_pdf_files
        )
        add_files_btn.pack(side="left", padx=(0, 6))
        Tooltip(add_files_btn, "Chọn một hoặc nhiều file PDF Purchase Order")

        add_folder_btn = ctk.CTkButton(
            btn_bar, text="📂 Thêm Thư Mục", width=120, height=30,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=self._choose_pdf_folder
        )
        add_folder_btn.pack(side="left", padx=(0, 6))
        Tooltip(add_folder_btn, "Thêm tất cả file .pdf trong một thư mục (không đệ quy)")

        clear_btn = ctk.CTkButton(
            btn_bar, text="✖ Xóa Hết", width=90, height=30,
            fg_color="#D32F2F", hover_color="#B71C1C",
            command=self._clear_all_pdfs
        )
        clear_btn.pack(side="left")
        Tooltip(clear_btn, "Xóa toàn bộ PDF đã chọn")

        # 3. Section: Store List & Output Paths
        meta_card = ctk.CTkFrame(view)
        meta_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        meta_card.grid_columnconfigure(1, weight=1)

        # Store List Row
        ctk.CTkLabel(
            meta_card, text="📋 Danh sách mã (CSV/TXT):",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.list_entry = ctk.CTkEntry(
            meta_card, placeholder_text="Chọn file ListMCH.csv hoặc stores.txt..."
        )
        self.list_entry.grid(row=0, column=1, padx=(0, 8), pady=(10, 4), sticky="ew")
        self.list_entry.bind("<KeyRelease>", lambda _e: self._refresh_ready_state())
        Tooltip(self.list_entry, "CSV/TXT chứa mã cửa hàng (SG####). Cột tên và staff là tùy chọn.")

        list_btn = ctk.CTkButton(
            meta_card, text="Chọn...", width=80, height=30,
            command=self._choose_list_file
        )
        list_btn.grid(row=0, column=2, padx=(0, 12), pady=(10, 4))
        Tooltip(list_btn, "Chọn file danh sách mã cửa hàng")

        # Output Path Row
        ctk.CTkLabel(
            meta_card, text="💾 Nơi lưu file PO gộp:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=1, column=0, padx=12, pady=(4, 10), sticky="w")

        today_str = datetime.datetime.now().strftime("%d%m%Y")
        default_out = os.path.join(os.path.expanduser("~"), "Desktop", f"PO_{today_str}.pdf")
        self.out_entry = ctk.CTkEntry(meta_card)
        self.out_entry.insert(0, default_out)
        self.out_entry.grid(row=1, column=1, padx=(0, 8), pady=(4, 10), sticky="ew")
        self.out_entry.bind("<KeyRelease>", lambda _e: self._refresh_ready_state())
        Tooltip(self.out_entry, "Đường dẫn file PDF kết quả. Nên chọn Desktop hoặc thư mục dễ tìm.")

        out_btn = ctk.CTkButton(
            meta_card, text="Chọn...", width=80, height=30,
            command=self._choose_output_path
        )
        out_btn.grid(row=1, column=2, padx=(0, 12), pady=(4, 10))
        Tooltip(out_btn, "Chọn nơi lưu file PO đã gộp")

        # 4. Action Bar (Start, Open Dir, View Report, Progress)
        action_card = ctk.CTkFrame(view, fg_color="transparent")
        action_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        action_card.grid_columnconfigure(0, weight=1)

        ctrl_row = ctk.CTkFrame(action_card, fg_color="transparent")
        ctrl_row.pack(fill="x", pady=(0, 6))

        self.start_btn = ctk.CTkButton(
            ctrl_row, text="▶  BẮT ĐẦU XỬ LÝ",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2E7D32", hover_color="#1B5E20",
            height=40, width=180,
            command=self._on_start_processing
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        Tooltip(self.start_btn, "Cần đủ 3 thứ: PDF + danh sách mã + đường dẫn lưu, rồi bấm để gộp PO.")

        self.open_dir_btn = ctk.CTkButton(
            ctrl_row, text="📂 Mở Thư Mục Chứa",
            height=40, fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self._open_output_dir
        )
        self.open_dir_btn.pack(side="left", padx=(0, 8))
        Tooltip(self.open_dir_btn, "Mở thư mục chứa file PDF kết quả")

        self.view_report_btn = ctk.CTkButton(
            ctrl_row, text="📊 Xem Báo Cáo Thống Kê",
            height=40, fg_color="#1565C0", hover_color="#0D47A1",
            state="disabled", command=lambda: self._show_view("dashboard")
        )
        self.view_report_btn.pack(side="left")
        Tooltip(self.view_report_btn, "Bật sau khi xử lý xong — xem mã thiếu/dư và qty theo staff")

        self.ready_hint = ctk.CTkLabel(
            ctrl_row, text="", font=ctk.CTkFont(size=12), text_color="gray55"
        )
        self.ready_hint.pack(side="right", padx=8)

        self.progress_bar = ctk.CTkProgressBar(action_card, height=10)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.step_tracker = ModernStepTracker(view)
        self.step_tracker.grid(row=3, column=0, sticky="ew", pady=(0, 6))

        # Log console
        log_frame = ctk.CTkFrame(view)
        log_frame.grid(row=4, column=0, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        log_head = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_head.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 2))
        ctk.CTkLabel(
            log_head, text="📝 Nhật ký xử lý (Log Output)",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            log_head, text="Xóa log", width=60, height=22, font=ctk.CTkFont(size=10),
            fg_color=("gray75", "gray35"), hover_color=("gray65", "gray45"),
            command=self._clear_log
        ).pack(side="right")

        log_container = tk.Frame(log_frame, bg="#1E1E1E")
        log_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        log_container.grid_columnconfigure(0, weight=1)
        log_container.grid_rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_container, bg="#1E1E1E", fg="#D4D4D4",
            insertbackground="white", font=("Consolas", 9),
            wrap=tk.NONE, relief=tk.FLAT, bd=0
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(log_container, orient=tk.VERTICAL, command=self.log_text.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text['yscrollcommand'] = v_scroll.set

        h_scroll = ttk.Scrollbar(log_container, orient=tk.HORIZONTAL, command=self.log_text.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.log_text['xscrollcommand'] = h_scroll.set

        # Color tags
        self.log_text.tag_config("INFO", foreground="#64B5F6")
        self.log_text.tag_config("WARNING", foreground="#FFB74D")
        self.log_text.tag_config("ERROR", foreground="#EF5350")
        self.log_text.tag_config("SUCCESS", foreground="#81C784")

        # Attach logging handler
        self.log_handler = CtkLogHandler(self._append_log)
        self.log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger("po_merge_tool").addHandler(self.log_handler)

        self.views["merge"] = view

    # ===== VIEW 2: DASHBOARD & SUMMARY VIEW (HIGH-PERFORMANCE) =====

    def _init_dashboard_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)  # Table expands

        # Top Bar
        head_frame = ctk.CTkFrame(view, fg_color="transparent")
        head_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            head_frame, text="📊 Dashboard Báo Cáo & Thống Kê",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        self.export_report_btn = ctk.CTkButton(
            head_frame, text="📥 Xuất Báo Cáo (Export)",
            fg_color="#00897B", hover_color="#00695C",
            command=self._export_report_file
        )
        self.export_report_btn.pack(side="right")
        Tooltip(self.export_report_btn, "Lưu báo cáo thiếu/dư mã và phân bổ staff ra file TXT")

        # 1. KPI Cards Row
        kpi_grid = ctk.CTkFrame(view, fg_color="transparent")
        kpi_grid.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        kpi_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.kpi_widgets: Dict[str, Tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        cards_def = [
            ("total_po", "Tổng PDF / Trang", "0 / 0", "#1976D2"),
            ("total_qty", "Tổng Số Lượng (Qty)", "0", "#388E3C"),
            ("coverage", "Độ Phủ Cửa Hàng", "0 / 0", "#7B1FA2"),
            ("issues", "Mã Thiếu / Dư", "0 / 0", "#F57C00"),
        ]

        for i, (key, title, val, accent) in enumerate(cards_def):
            card = ctk.CTkFrame(kpi_grid)
            card.grid(row=0, column=i, padx=4, sticky="ew")

            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11), text_color="gray60"
            ).pack(anchor="w", padx=12, pady=(10, 2))

            val_lbl = ctk.CTkLabel(
                card, text=val, font=ctk.CTkFont(size=20, weight="bold"),
                text_color=accent
            )
            val_lbl.pack(anchor="w", padx=12, pady=(0, 10))
            self.kpi_widgets[key] = (val_lbl, card)

        # 2. Main Content: Split into Staff Summary & Store Codes Treeview Table
        main_sec = ctk.CTkFrame(view)
        main_sec.grid(row=2, column=0, sticky="nsew")
        main_sec.grid_columnconfigure(0, weight=1)
        main_sec.grid_rowconfigure(2, weight=1)

        # Filter & Search Control Bar
        ctrl_bar = ctk.CTkFrame(main_sec, fg_color="transparent")
        ctrl_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        ctk.CTkLabel(
            ctrl_bar, text="🔍 Chi tiết Mã Cửa Hàng & Phân bổ Staff:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        self.dash_search_entry = ctk.CTkEntry(
            ctrl_bar, placeholder_text="🔎 Lọc nhanh mã, tên CH, staff...", width=240
        )
        self.dash_search_entry.pack(side="right", padx=(8, 0))
        self.dash_search_entry.bind("<KeyRelease>", lambda e: self._debounce_dash_search())

        self.code_filter_seg = ctk.CTkSegmentedButton(
            ctrl_bar, values=["Tất cả", "Thiếu mã", "Dư mã"],
            command=lambda v: self._render_filtered_codes(v)
        )
        self.code_filter_seg.pack(side="right")
        self.code_filter_seg.set("Tất cả")

        # Staff Breakdown Summary Badges Container (Fast horizontal chips)
        self.staff_chips_container = ctk.CTkScrollableFrame(main_sec, height=55, orientation="horizontal")
        self.staff_chips_container.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        # Virtualized Store Codes Table (ttk.Treeview)
        table_container = tk.Frame(main_sec, bg="#1E1E1E")
        table_container.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        dash_cols = ("code", "staff", "qty", "name", "status")
        self.dash_tree = ttk.Treeview(
            table_container, columns=dash_cols, show="headings",
            style="Modern.Treeview", selectmode="browse"
        )

        self.dash_tree.heading("code", text="Mã Cửa Hàng")
        self.dash_tree.heading("staff", text="Nhân Viên")
        self.dash_tree.heading("qty", text="Số Lượng (Qty)")
        self.dash_tree.heading("name", text="Tên & Địa Chỉ Cửa Hàng")
        self.dash_tree.heading("status", text="Trạng Thái")

        self.dash_tree.column("code", width=120, anchor="center")
        self.dash_tree.column("staff", width=140, anchor="center")
        self.dash_tree.column("qty", width=120, anchor="center")
        self.dash_tree.column("name", width=420, stretch=True)
        self.dash_tree.column("status", width=130, anchor="center")

        self.dash_tree.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=self.dash_tree.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.dash_tree.configure(yscrollcommand=v_scroll.set)

        # Tags for colored styling in Treeview
        self.dash_tree.tag_configure("merged", foreground="#66BB6A")
        self.dash_tree.tag_configure("missing", foreground="#EF5350")
        self.dash_tree.tag_configure("extra", foreground="#FFA726")
        self.dash_tree.tag_configure("standard", foreground="#42A5F5")
        self.dash_tree.tag_configure("row_even", background="#242424")
        self.dash_tree.tag_configure("row_odd", background="#1E1E1E")

        self.views["dashboard"] = view

    # ===== VIEW 3: STAFF MAPPING DIRECTORY (HIGH-PERFORMANCE) =====

    def _init_staff_view(self):
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(1, weight=1)

        # Search Bar Header
        search_card = ctk.CTkFrame(view)
        search_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_card.grid_columnconfigure(0, weight=1)

        search_row = ctk.CTkFrame(search_card, fg_color="transparent")
        search_row.pack(fill="x", padx=12, pady=10)

        self.staff_search_entry = ctk.CTkEntry(
            search_row, placeholder_text="🔎 Tìm kiếm theo tên Staff, mã cửa hàng, hoặc địa chỉ..."
        )
        self.staff_search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.staff_search_entry.bind("<KeyRelease>", lambda e: self._debounce_staff_search())

        self.staff_count_badge = ctk.CTkLabel(
            search_row, text="0 cửa hàng", font=ctk.CTkFont(size=11), text_color="gray60"
        )
        self.staff_count_badge.pack(side="right", padx=6)

        # Virtualized Treeview Table for Staff Directory
        table_card = ctk.CTkFrame(view)
        table_card.grid(row=1, column=0, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(0, weight=1)

        table_frame = tk.Frame(table_card, bg="#1E1E1E")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        staff_cols = ("staff", "code", "name")
        self.staff_tree = ttk.Treeview(
            table_frame, columns=staff_cols, show="headings",
            style="Modern.Treeview", selectmode="browse"
        )

        self.staff_tree.heading("staff", text="Nhân Viên Phụ Trách")
        self.staff_tree.heading("code", text="Mã Cửa Hàng")
        self.staff_tree.heading("name", text="Tên & Địa Chỉ Cửa Hàng")

        self.staff_tree.column("staff", width=160, anchor="center")
        self.staff_tree.column("code", width=120, anchor="center")
        self.staff_tree.column("name", width=550, stretch=True)

        self.staff_tree.grid(row=0, column=0, sticky="nsew")

        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.staff_tree.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.staff_tree.configure(yscrollcommand=v_scroll.set)

        self.staff_tree.tag_configure("row_even", background="#242424")
        self.staff_tree.tag_configure("row_odd", background="#1E1E1E")

        self.views["staff"] = view

    # ===== VIEW 4: SETTINGS VIEW =====

    def _init_settings_view(self):
        # Regular frame (not CTkScrollableFrame) so tkraise() can show this tab.
        view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(view)
        card.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            card, text="⚙️ Cài đặt Ứng Dụng",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=16, pady=(16, 12))

        p_row = ctk.CTkFrame(card, fg_color="transparent")
        p_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(p_row, text="Regex Pattern nhận diện mã:", width=220, anchor="w").pack(side="left")
        self.pattern_entry = ctk.CTkEntry(p_row, width=250)
        self.pattern_entry.insert(0, self.settings.custom_pattern)
        self.pattern_entry.pack(side="left", padx=8)
        Tooltip(self.pattern_entry, "Regex tìm mã cửa hàng trong PDF. Mặc định: SG + 4 chữ số.")
        ctk.CTkButton(
            p_row, text="Mặc định", width=80,
            command=lambda: (self.pattern_entry.delete(0, "end"), self.pattern_entry.insert(0, DEFAULT_PATTERN))
        ).pack(side="left")

        mode_row = ctk.CTkFrame(card, fg_color="transparent")
        mode_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(mode_row, text="Giao diện (sáng / tối):", width=220, anchor="w").pack(side="left")
        self.theme_option = ctk.CTkOptionMenu(
            mode_row,
            values=["Dark", "Light", "System"],
            command=self._change_theme_mode,
            width=160,
        )
        self.theme_option.set(self.settings.theme_mode.capitalize())
        self.theme_option.pack(side="left", padx=8)
        Tooltip(self.theme_option, "Dark / Light / theo hệ thống. Đổi ngay lập tức.")

        t_row = ctk.CTkFrame(card, fg_color="transparent")
        t_row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(t_row, text="Tone màu nút:", width=220, anchor="w").pack(side="left")
        self.color_theme_menu = ctk.CTkOptionMenu(
            t_row, values=["blue", "green", "dark-blue"],
            command=self._change_color_theme,
            width=160,
        )
        self.color_theme_menu.set(self.settings.color_theme)
        self.color_theme_menu.pack(side="left", padx=8)
        Tooltip(self.color_theme_menu, "Màu accent của nút. Cần mở lại app để áp dụng đầy đủ.")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(16, 16))
        ctk.CTkButton(
            btn_row, text="💾 Lưu Cài Đặt", fg_color="#2E7D32", hover_color="#1B5E20",
            command=self._save_settings_btn
        ).pack(side="left")

        self.save_status_lbl = ctk.CTkLabel(btn_row, text="", text_color="#4CAF50")
        self.save_status_lbl.pack(side="left", padx=12)

        self.views["settings"] = view

    # ===== Theme & Settings Actions =====

    def _change_theme_mode(self, mode: str):
        ctk.set_appearance_mode(mode.lower())
        self.settings.theme_mode = mode.lower()
        self.settings.save()
        if hasattr(self, "pdf_list"):
            self.pdf_list.refresh()
        self._setup_treeview_styles()

    def _change_color_theme(self, theme: str):
        self.settings.color_theme = theme
        self.settings.save()
        self.toast.show("Tone màu sẽ áp dụng đầy đủ khi mở lại app.", "info")

    def _save_settings_btn(self):
        pat = self.pattern_entry.get().strip() or DEFAULT_PATTERN
        self.settings.custom_pattern = pat
        self.settings.theme_mode = self.theme_option.get().lower()
        self.settings.color_theme = self.color_theme_menu.get()
        self.settings.save()
        self.save_status_lbl.configure(text="✅ Đã lưu cấu hình!")
        self.toast.show("Đã lưu cài đặt.", "success", 2200)
        self.after(2500, lambda: self.save_status_lbl.configure(text=""))

    def _restore_settings(self):
        restored: List[Path] = []
        if self.settings.last_input_paths:
            for p in self.settings.last_input_paths:
                path_obj = Path(p)
                if path_obj.exists():
                    if path_obj.is_dir():
                        restored.extend(sorted(path_obj.glob("*.pdf")))
                    elif path_obj.suffix.lower() == ".pdf":
                        restored.append(path_obj)
            if restored:
                self.pdf_list.set_files(restored)

        if self.settings.last_list_file and os.path.exists(self.settings.last_list_file):
            self.list_entry.delete(0, "end")
            self.list_entry.insert(0, self.settings.last_list_file)
            self._load_staff_directory(Path(self.settings.last_list_file))

        if self.settings.last_output_dir and os.path.isdir(self.settings.last_output_dir):
            today_str = datetime.datetime.now().strftime("%d%m%Y")
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, os.path.join(self.settings.last_output_dir, f"PO_{today_str}.pdf"))

        self._refresh_ready_state()

    # ===== File Selection Methods =====

    def _on_pdf_list_changed(self):
        self._input_files = self.pdf_list.files
        self._refresh_ready_state()

    def _choose_pdf_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn các file PDF PO", filetypes=[("PDF files", "*.pdf")]
        )
        if files:
            self.pdf_list.add_files([Path(f) for f in files])

    def _choose_pdf_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục chứa file PDF")
        if folder:
            found = sorted(Path(folder).glob("*.pdf"))
            if not found:
                self.toast.show("Thư mục không có file PDF.", "warning")
                return
            self.pdf_list.add_files(found)

    def _clear_all_pdfs(self):
        self.pdf_list.clear()

    def _refresh_ready_state(self):
        """Live validation: border color + hint, no popups while filling the form."""
        n_pdf = len(self._input_files)
        self.pdf_count_badge.configure(text=f"{n_pdf} file PDF đã chọn")

        ok_pdf = n_pdf > 0
        list_file = self.list_entry.get().strip()
        ok_list = bool(list_file) and os.path.isfile(list_file)
        out_file = self.out_entry.get().strip()
        ok_out = bool(out_file)

        ok_color = ("#2E7D32", "#81C784")
        bad_color = ("#C62828", "#EF9A9A")
        try:
            self.list_entry.configure(border_color=ok_color if ok_list else bad_color)
            self.out_entry.configure(border_color=ok_color if ok_out else bad_color)
        except Exception:
            pass

        missing = []
        if not ok_pdf:
            missing.append("PDF")
        if not ok_list:
            missing.append("danh sách mã")
        if not ok_out:
            missing.append("nơi lưu")

        if missing:
            self.ready_hint.configure(
                text="Còn thiếu: " + " · ".join(missing),
                text_color="#E65100",
            )
        else:
            self.ready_hint.configure(text="Sẵn sàng xử lý", text_color="#2E7D32")

    def _choose_list_file(self):
        f = filedialog.askopenfilename(
            title="Chọn file danh sách mã cửa hàng",
            filetypes=[("CSV/TXT files", "*.csv *.txt")]
        )
        if f:
            self.list_entry.delete(0, "end")
            self.list_entry.insert(0, f)
            self._load_staff_directory(Path(f))
            self._refresh_ready_state()

    def _choose_output_path(self):
        today_str = datetime.datetime.now().strftime("%d%m%Y")
        f = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file PO kết quả",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"PO_{today_str}.pdf"
        )
        if f:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, f)
            self._refresh_ready_state()

    def _open_output_dir(self):
        out = self.out_entry.get().strip()
        if not out:
            return
        p = Path(out)
        target = p.parent if p.suffix else p
        if not target.exists():
            self.toast.show(f"Thư mục chưa tồn tại:\n{target}", "warning")
            return
        try:
            import webbrowser
            webbrowser.open(target.as_uri())
        except Exception:
            pass

    # ===== Log Callback =====

    def _append_log(self, text: str, level: str = "INFO"):
        tag = level if level in ("INFO", "WARNING", "ERROR", "DEBUG") else "INFO"
        if "Hoàn tất" in text or "Done" in text:
            tag = "SUCCESS"
        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.delete(1.0, tk.END)

    # ===== Processing Worker =====

    def _on_start_processing(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self.toast.show("Đang xử lý — vui lòng chờ xong rồi chạy lại.", "warning")
            return

        if not self._input_files:
            self.toast.show("Chọn ít nhất một file PDF.", "error")
            return

        list_file = self.list_entry.get().strip()
        if not list_file or not os.path.exists(list_file):
            self.toast.show("Chọn file danh sách mã cửa hàng hợp lệ.", "error")
            return

        out_file = self.out_entry.get().strip()
        if not out_file:
            self.toast.show("Chọn đường dẫn lưu file kết quả.", "error")
            return

        # Save paths to settings
        self.settings.last_input_paths = [str(f) for f in self._input_files]
        self.settings.last_list_file = list_file
        self.settings.last_output_dir = str(Path(out_file).parent)
        self.settings.save()

        # Reset UI
        self.start_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self._clear_log()
        self.step_tracker.reset()
        self.view_report_btn.configure(state="disabled", fg_color="#1565C0", text="📊 Xem Báo Cáo Thống Kê")
        self.open_dir_btn.configure(
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            text="📂 Mở Thư Mục Chứa"
        )

        pattern = self.settings.custom_pattern or DEFAULT_PATTERN

        self._worker_thread = threading.Thread(
            target=self._worker_run,
            args=(self._input_files, list_file, out_file, pattern),
            daemon=True
        )
        self._worker_thread.start()

    def _worker_run(self, pdf_paths: List[Path], list_file_str: str, out_file_str: str, pattern: str):
        log = logging.getLogger("po_merge_tool")
        summary = ProcessingSummary()
        summary.timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        summary.output_path = out_file_str

        try:
            # 1. Step 1: Read Files
            self.step_tracker.set_active(0)
            log.info("Bắt đầu xử lý %d file PDF...", len(pdf_paths))
            summary.total_pdfs = len(pdf_paths)

            list_path = Path(list_file_str)
            store_order = read_store_list(list_path)
            summary.total_codes_expected = len(store_order)
            log.info("Đã tải danh sách cửa hàng: %d mã", len(store_order))

            # Mappings
            try:
                summary.code_name_map = read_code_name_map(list_path)
            except Exception:
                summary.code_name_map = {}

            try:
                summary.code_staff_map = read_code_staff_map(list_path)
            except Exception:
                summary.code_staff_map = {}

            # 2. Step 2: Extract
            self.step_tracker.set_active(1)

            def extract_progress(done, total):
                try:
                    pct = (done / total) * 0.7 if total else 0
                    self.progress_bar.set(pct)
                except Exception:
                    pass

            result = extract_store_pages(pdf_paths, pattern, extract_progress, logger=log)
            summary.total_pages = result.total_pages

            found_codes = set(result.store_pages.keys())
            expected_codes = set(c.upper() for c in store_order)
            summary.missing_codes = sorted(list(expected_codes - found_codes))
            summary.extra_codes = sorted(list(found_codes - expected_codes))
            summary.total_codes_found = len(found_codes)

            if summary.missing_codes:
                log.warning("Thiếu PO cho %d mã cửa hàng: %s",
                            len(summary.missing_codes), ", ".join(summary.missing_codes[:15]))
            if summary.extra_codes:
                log.warning("Dư %d mã không có trong danh sách: %s",
                            len(summary.extra_codes), ", ".join(summary.extra_codes[:15]))

            # 3. Step 3: Merge & Annotate
            self.step_tracker.set_active(2)

            def merge_progress(done, total):
                try:
                    pct = 0.7 + ((done / total) * 0.3 if total else 0)
                    self.progress_bar.set(min(pct, 0.99))
                except Exception:
                    pass

            annot_res = merge_and_write(
                result.store_pages,
                store_order,
                Path(out_file_str),
                logger=log,
                progress_cb=merge_progress,
                code_to_name=summary.code_name_map,
                code_staff_map=summary.code_staff_map
            )

            # Record quantities & staff breakdown
            summary.total_qty = annot_res.total_qty
            summary.staff_totals = annot_res.staff_totals
            summary.staff_store_map = annot_res.staff_store_map
            summary.store_qty_map = annot_res.store_qty_map

            # 4. Step 4: Complete
            self.step_tracker.set_complete()
            self.progress_bar.set(1.0)
            log.info("Hoàn tất xuất file: %s", out_file_str)

            self.summary_data = summary

            # Update UI on main thread
            self.after(0, self._on_processing_complete)

        except Exception as e:
            log.exception("Lỗi trong quá trình xử lý: %s", e)
            self.step_tracker.set_error(2)
            self.after(0, lambda err=str(e): self.toast.show(f"Lỗi xử lý:\n{err}", "error", 6000))
        finally:
            self.after(0, lambda: self.start_btn.configure(state="normal"))

    def _on_processing_complete(self):
        """Called when merge succeeds."""
        self.open_dir_btn.configure(
            fg_color="#00897B", hover_color="#00695C",
            text="📂 Mở Thư Mục Kết Quả"
        )
        self.view_report_btn.configure(
            state="normal",
            fg_color="#1565C0", hover_color="#0D47A1",
            text="📊 Xem Báo Cáo Thống Kê"
        )
        if "dashboard" in self.nav_btns:
            self.nav_btns["dashboard"].configure(text="📊  Thống kê & Báo cáo")

        self._render_dashboard()
        qty = self.summary_data.total_qty if self.summary_data else 0
        missing = len(self.summary_data.missing_codes) if self.summary_data else 0
        extra = len(self.summary_data.extra_codes) if self.summary_data else 0
        qty_txt = f"{qty:,}".replace(",", ".")
        self.toast.show(
            f"Hoàn tất — Qty {qty_txt}  ·  thiếu {missing}  ·  dư {extra}\n"
            "Mở tab Thống kê để xem chi tiết.",
            "success",
            5000,
        )

    # ===== Dashboard Rendering (Ultra Fast) =====

    def _render_dashboard(self):
        if not self.summary_data:
            return

        s = self.summary_data

        # Update KPI Cards
        self.kpi_widgets["total_po"][0].configure(text=f"{s.total_pdfs} files / {s.total_pages} trang")
        formatted_qty = f"{s.total_qty:,}".replace(",", ".")
        self.kpi_widgets["total_qty"][0].configure(text=formatted_qty)
        self.kpi_widgets["coverage"][0].configure(text=f"{s.total_codes_found} / {s.total_codes_expected} mã")
        self.kpi_widgets["issues"][0].configure(text=f"Thiếu {len(s.missing_codes)} / Dư {len(s.extra_codes)}")

        # Render Staff Chips (horizontal row)
        for w in self.staff_chips_container.winfo_children():
            w.destroy()

        if s.staff_store_map:
            for staff_name in sorted(s.staff_store_map.keys()):
                codes = s.staff_store_map[staff_name]
                staff_qty = s.staff_totals.get(staff_name, 0)
                chip = ctk.CTkFrame(self.staff_chips_container, fg_color=("gray85", "gray25"), corner_radius=6)
                chip.pack(side="left", padx=4, pady=2)

                ctk.CTkLabel(
                    chip, text=f"👤 {staff_name} : {staff_qty:,} Qty ({len(codes)} CH)".replace(",", "."),
                    font=ctk.CTkFont(size=11, weight="bold"), padx=8, pady=4
                ).pack()

        # Render Store codes in Treeview
        self._render_filtered_codes(self.code_filter_seg.get())

    def _debounce_dash_search(self):
        if self._dash_search_debounce:
            self.after_cancel(self._dash_search_debounce)
        self._dash_search_debounce = self.after(150, lambda: self._render_filtered_codes(self.code_filter_seg.get()))

    def _render_filtered_codes(self, filter_mode: str = "Tất cả"):
        if not self.summary_data:
            return

        s = self.summary_data
        self.dash_tree.delete(*self.dash_tree.get_children())

        if filter_mode == "Thiếu mã":
            codes_to_show = s.missing_codes
        elif filter_mode == "Dư mã":
            codes_to_show = s.extra_codes
        else:
            all_codes = list(s.code_name_map.keys())
            for c in s.extra_codes:
                if c not in all_codes:
                    all_codes.append(c)
            codes_to_show = all_codes if all_codes else list(s.store_qty_map.keys())

        query = self.dash_search_entry.get().strip().lower()

        # Batch insert into Treeview (extremely fast, zero lag)
        row_idx = 0
        for code in codes_to_show:
            name = s.code_name_map.get(code, "")
            staff = s.code_staff_map.get(code, "Chưa phân công")
            qty = s.store_qty_map.get(code, 0)

            # Search query filter
            if query:
                if query not in code.lower() and query not in name.lower() and query not in staff.lower():
                    continue

            # Determine status & tag
            if code in s.missing_codes:
                status_text = "⚠️ Thiếu PO"
                status_tag = "missing"
            elif code in s.extra_codes:
                status_text = "➕ Dư PO"
                status_tag = "extra"
            elif qty > 0:
                status_text = "✅ Đã gộp"
                status_tag = "merged"
            else:
                status_text = "ℹ️ Chuẩn"
                status_tag = "standard"

            stripe_tag = "row_even" if row_idx % 2 == 0 else "row_odd"
            row_idx += 1

            qty_display = str(qty) if qty > 0 else "-"
            self.dash_tree.insert(
                "", "end",
                values=(code, staff, qty_display, name, status_text),
                tags=(status_tag, stripe_tag)
            )

    # ===== Export Report =====

    def _export_report_file(self):
        if not self.summary_data:
            self.toast.show("Chưa có dữ liệu để xuất báo cáo. Hãy chạy merge trước.", "warning")
            return

        s = self.summary_data
        today_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        f = filedialog.asksaveasfilename(
            title="Lưu Báo Cáo Thống Kê",
            defaultextension=".txt",
            filetypes=[("Text Report", "*.txt"), ("CSV File", "*.csv")],
            initialfile=f"PO_Report_{today_str}.txt"
        )
        if not f:
            return

        try:
            with open(f, "w", encoding="utf-8") as out:
                out.write("====================================================\n")
                out.write(f"           BÁO CÁO XỬ LÝ PO - {s.timestamp}\n")
                out.write("====================================================\n\n")
                out.write(f"- Tổng số file PDF input: {s.total_pdfs}\n")
                out.write(f"- Tổng số trang xử lý: {s.total_pages}\n")
                out.write(f"- Tổng số lượng (Qty sau chia 2): {s.total_qty}\n")
                out.write(f"- Tổng số mã chuẩn: {s.total_codes_expected}\n")
                out.write(f"- Tổng số mã tìm thấy: {s.total_codes_found}\n")
                out.write(f"- File output kết quả: {s.output_path}\n\n")

                out.write("--- DANH SÁCH MÃ THIẾU PO ---\n")
                if s.missing_codes:
                    for c in s.missing_codes:
                        name = s.code_name_map.get(c, "")
                        staff = s.code_staff_map.get(c, "")
                        out.write(f"  • {c} (Staff: {staff}) - {name}\n")
                else:
                    out.write("  (Không có mã nào thiếu)\n")

                out.write("\n--- DANH SÁCH MÃ DƯ PO ---\n")
                if s.extra_codes:
                    for c in s.extra_codes:
                        out.write(f"  • {c}\n")
                else:
                    out.write("  (Không có mã nào dư)\n")

                out.write("\n--- PHÂN BỔ THEO STAFF ---\n")
                for staff_name, codes in sorted(s.staff_store_map.items()):
                    staff_qty = s.staff_totals.get(staff_name, 0)
                    out.write(f"\nStaff: {staff_name} (Tổng Qty: {staff_qty} | {len(codes)} cửa hàng):\n")
                    out.write(f"  Codes: {', '.join(codes)}\n")

            self.toast.show(f"Đã xuất báo cáo:\n{f}", "success")
        except Exception as e:
            self.toast.show(f"Không ghi được file báo cáo:\n{e}", "error", 5000)

    # ===== Staff Directory Search (Ultra Fast) =====

    def _load_staff_directory(self, path: Path):
        try:
            if not path or not path.exists():
                return

            try:
                code_name = read_code_name_map(path)
            except Exception:
                code_name = {}

            try:
                code_staff = read_code_staff_map(path)
            except Exception:
                code_staff = {}

            if not code_name and not code_staff:
                try:
                    plain_codes = read_store_list(path)
                    code_name = {c: "" for c in plain_codes}
                except Exception:
                    pass

            staff_group: Dict[str, List[Tuple[str, str]]] = {}
            if code_staff:
                for code, staff in code_staff.items():
                    if staff not in staff_group:
                        staff_group[staff] = []
                    staff_group[staff].append((code, code_name.get(code, "")))

                unassigned = [c for c in code_name.keys() if c not in code_staff]
                if unassigned:
                    staff_group["Chưa phân công"] = [(c, code_name.get(c, "")) for c in unassigned]
            elif code_name:
                staff_group["Tất cả cửa hàng"] = [(c, code_name.get(c, "")) for c in sorted(code_name.keys())]

            self._staff_directory_data = staff_group
            self._filter_staff_directory()
        except Exception as e:
            logging.getLogger("po_merge_tool").error("Error loading staff directory: %s", e)

    def _debounce_staff_search(self):
        if self._search_debounce_timer:
            self.after_cancel(self._search_debounce_timer)
        self._search_debounce_timer = self.after(150, self._filter_staff_directory)

    def _filter_staff_directory(self):
        self.staff_tree.delete(*self.staff_tree.get_children())

        if not hasattr(self, "_staff_directory_data") or not self._staff_directory_data:
            self.staff_count_badge.configure(text="Chưa có dữ liệu (hãy chọn file CSV)")
            return

        query = self.staff_search_entry.get().strip().lower()
        total_matched = 0
        total_staff_count = set()

        row_idx = 0
        for staff_name, stores in sorted(self._staff_directory_data.items()):
            for code, name in stores:
                if not query or query in staff_name.lower() or query in code.lower() or query in name.lower():
                    total_matched += 1
                    total_staff_count.add(staff_name)

                    stripe_tag = "row_even" if row_idx % 2 == 0 else "row_odd"
                    row_idx += 1

                    self.staff_tree.insert(
                        "", "end",
                        values=(staff_name, code, name),
                        tags=(stripe_tag,)
                    )

        self.staff_count_badge.configure(
            text=f"Hiển thị {total_matched} cửa hàng ({len(total_staff_count)} nhân viên)"
        )


# ===== Entrypoint for Modern GUI =====

def launch_modern_gui():
    app = ModernPOApp()
    app.mainloop()


if __name__ == "__main__":
    launch_modern_gui()
