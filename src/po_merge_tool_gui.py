#!/usr/bin/env python3
"""
PO Merge Tool — GUI Module (Tkinter)

Modernized single-file GUI with:
- File listbox (add/remove individual files)
- Colored log output (INFO=blue, WARNING=orange, ERROR=red)
- Multi-step progress indicator
- Real-time field validation
- Remember last used paths
- Improved layout and visual hierarchy

Usage:
  python po_merge_tool_gui.py --gui
  python po_merge_tool_gui.py --input-folder ./pdfs --list-file stores.csv --output PO_FINAL.pdf
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

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
)
from cli import build_parser, run_cli


# ===== GUI Log Handler =====


class TkLoggerHandler(logging.Handler):
    """Logging handler that posts color-tagged messages to a Tk Text widget."""

    def __init__(self, callback: Callable[[str, str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        level = record.levelname  # INFO, WARNING, ERROR, DEBUG
        try:
            self.callback(msg + "\n", level)
        except Exception:
            pass


# ===== Step Progress Tracker =====


class StepTracker:
    """Visual multi-step progress indicator using tk.Labels."""

    STEPS = [
        ("1. Đọc file", "read"),
        ("2. Trích xuất", "extract"),
        ("3. Gộp PDF", "merge"),
        ("4. Hoàn tất", "done"),
    ]

    # States: pending, active, complete
    COLORS = {
        "pending":  {"bg": "#E0E0E0", "fg": "#9E9E9E"},
        "active":   {"bg": "#2196F3", "fg": "#FFFFFF"},
        "complete": {"bg": "#4CAF50", "fg": "#FFFFFF"},
        "error":    {"bg": "#F44336", "fg": "#FFFFFF"},
    }

    def __init__(self, parent: tk.Frame):
        self.frame = tk.Frame(parent, bg="#F5F5F5")
        self.frame.pack(fill=tk.X, pady=(6, 2))
        self.labels: List[tk.Label] = []
        self.arrows: List[tk.Label] = []

        for i, (text, _) in enumerate(self.STEPS):
            if i > 0:
                arrow = tk.Label(self.frame, text="→", font=("Arial", 12, "bold"),
                                 bg="#F5F5F5", fg="#BDBDBD")
                arrow.pack(side=tk.LEFT, padx=2)
                self.arrows.append(arrow)

            lbl = tk.Label(self.frame, text=f"  {text}  ", font=("Arial", 9, "bold"),
                           relief=tk.FLAT, padx=8, pady=4)
            lbl.pack(side=tk.LEFT, padx=2)
            self.labels.append(lbl)

        self.reset()

    def reset(self):
        for lbl in self.labels:
            c = self.COLORS["pending"]
            lbl.config(bg=c["bg"], fg=c["fg"])

    def set_step(self, step_key: str, state: str = "active"):
        """Set a step's visual state. step_key is one of: read, extract, merge, done."""
        for i, (_, key) in enumerate(self.STEPS):
            if key == step_key:
                c = self.COLORS.get(state, self.COLORS["pending"])
                self.labels[i].config(bg=c["bg"], fg=c["fg"])
                break

    def complete_step(self, step_key: str):
        self.set_step(step_key, "complete")

    def activate_step(self, step_key: str):
        self.set_step(step_key, "active")

    def error_step(self, step_key: str):
        self.set_step(step_key, "error")


# ===== Main Application =====


class POApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")

        # Load saved settings
        self.settings = AppSettings.load()
        self.geometry(f"{self.settings.window_width}x{self.settings.window_height}")
        self.minsize(800, 550)

        # Set application icon
        self._set_icon()

        # Track validation state
        self._valid_inputs = False
        self._valid_list = False

        self._build_ui()
        self._restore_settings()
        self._worker_thread: Optional[threading.Thread] = None

        # Save window size on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Save settings and close."""
        try:
            self.settings.window_width = self.winfo_width()
            self.settings.window_height = self.winfo_height()
            self.settings.save()
        except Exception:
            pass
        self.destroy()

    def _set_icon(self):
        """Set application icon from available icon files."""
        try:
            ico_path = resource_path("assets/icon/app.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
                try:
                    import ctypes
                    myappid = 'lpa.pop.merge.tool.2.0'
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except Exception:
                    pass
                return

            png_path = resource_path("assets/icon/LPA-256.png")
            if os.path.exists(png_path):
                try:
                    icon_img = tk.PhotoImage(file=png_path)
                    self.iconphoto(False, icon_img)
                    return
                except Exception:
                    pass

            print("No icon files found in assets/icon/ folder")
        except Exception as e:
            print(f"Could not set application icon: {e}")

    def _build_ui(self):
        # Main container
        main_frame = tk.Frame(self, bg="#FAFAFA")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== HEADER =====
        header = tk.Frame(main_frame, bg="#1565C0", height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"📋 {APP_NAME}", font=("Arial", 16, "bold"),
                 bg="#1565C0", fg="white").pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(header, text=f"v{APP_VERSION}", font=("Arial", 10),
                 bg="#1565C0", fg="#BBDEFB").pack(side=tk.LEFT, pady=10)

        # Content area with padding
        content = ttk.Frame(main_frame, padding=12)
        content.pack(fill=tk.BOTH, expand=True)

        # ===== SECTION 1: Input PDF Files =====
        inp_frame = tk.LabelFrame(content, text=" 📁 Chọn các file PO ",
                                  font=("Arial", 11, "bold"), padx=8, pady=6)
        inp_frame.pack(fill=tk.X, pady=(0, 6))

        # File listbox with scrollbar
        list_container = tk.Frame(inp_frame)
        list_container.pack(fill=tk.X, pady=(0, 4))

        self.file_listbox = tk.Listbox(list_container, height=4,
                                       font=("Consolas", 9),
                                       selectmode=tk.EXTENDED,
                                       bg="#FAFAFA", relief=tk.GROOVE, bd=1)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lb_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL,
                                  command=self.file_listbox.yview)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox['yscrollcommand'] = lb_scroll.set

        # Buttons row for file management
        btn_row = tk.Frame(inp_frame)
        btn_row.pack(fill=tk.X)

        self.add_file_btn = tk.Button(btn_row, text="➕ Thêm file",
                                      font=("Arial", 9), command=self._add_files,
                                      relief=tk.GROOVE, padx=8, cursor="hand2")
        self.add_file_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.add_folder_btn = tk.Button(btn_row, text="📂 Thêm folder",
                                        font=("Arial", 9), command=self._add_folder,
                                        relief=tk.GROOVE, padx=8, cursor="hand2")
        self.add_folder_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.remove_btn = tk.Button(btn_row, text="🗑 Xóa đã chọn",
                                    font=("Arial", 9), command=self._remove_selected,
                                    relief=tk.GROOVE, padx=8, fg="#D32F2F", cursor="hand2")
        self.remove_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.clear_btn = tk.Button(btn_row, text="✖ Xóa tất cả",
                                   font=("Arial", 9), command=self._clear_files,
                                   relief=tk.GROOVE, padx=8, fg="#D32F2F", cursor="hand2")
        self.clear_btn.pack(side=tk.LEFT)

        # Validation indicator for input files
        self.input_status = tk.Label(btn_row, text="", font=("Arial", 9))
        self.input_status.pack(side=tk.RIGHT, padx=4)

        # ===== SECTION 2: Store List File =====
        list_frame = tk.LabelFrame(content, text=" 📋 Danh sách mã cửa hàng (CSV/TXT) ",
                                   font=("Arial", 11, "bold"), padx=8, pady=6)
        list_frame.pack(fill=tk.X, pady=(0, 6))

        list_row = tk.Frame(list_frame)
        list_row.pack(fill=tk.X)

        self.list_var = tk.StringVar()
        self.list_var.trace_add("write", lambda *_: self._validate_list_file())
        self.list_entry = ttk.Entry(list_row, textvariable=self.list_var,
                                    font=("Consolas", 9))
        self.list_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(list_row, text="Chọn...", font=("Arial", 9),
                  command=self._choose_list, relief=tk.GROOVE,
                  padx=8, cursor="hand2").pack(side=tk.LEFT)

        self.list_status = tk.Label(list_row, text="", font=("Arial", 9))
        self.list_status.pack(side=tk.RIGHT, padx=4)

        # ===== SECTION 3: Output =====
        out_frame = tk.LabelFrame(content, text=" 💾 Chỗ lưu PO ",
                                  font=("Arial", 11, "bold"), padx=8, pady=6)
        out_frame.pack(fill=tk.X, pady=(0, 6))

        out_row = tk.Frame(out_frame)
        out_row.pack(fill=tk.X)

        today_str = datetime.datetime.now().strftime("%d%m%Y")
        default_output = os.path.join(
            os.path.expanduser("~"), "Desktop", f"PO_{today_str}.pdf"
        )
        self.output_var = tk.StringVar(value=default_output)
        self.output_entry = ttk.Entry(out_row, textvariable=self.output_var,
                                      font=("Consolas", 9))
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tk.Button(out_row, text="Chọn...", font=("Arial", 9),
                  command=self._choose_output, relief=tk.GROOVE,
                  padx=8, cursor="hand2").pack(side=tk.LEFT)

        # ===== ACTION BUTTONS =====
        btn_frame = tk.Frame(content, bg="#FAFAFA")
        btn_frame.pack(fill=tk.X, pady=(4, 6))

        self.start_btn = tk.Button(
            btn_frame, text="▶  Bắt đầu", font=("Arial", 12, "bold"),
            bg="#2E7D32", fg="white", activebackground="#1B5E20",
            activeforeground="white", command=self._on_start,
            relief=tk.RAISED, padx=20, pady=6, cursor="hand2",
            state=tk.DISABLED  # Disabled until validation passes
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_frame, text="📂 Mở thư mục PO", font=("Arial", 9),
                  command=self._open_output_dir, relief=tk.GROOVE,
                  padx=8, cursor="hand2").pack(side=tk.LEFT, padx=(0, 4))

        self.view_staff_btn = tk.Button(
            btn_frame, text="👥 Xem Staff Mapping", font=("Arial", 9),
            command=self._view_staff_mapping, state=tk.DISABLED,
            relief=tk.GROOVE, padx=8, cursor="hand2"
        )
        self.view_staff_btn.pack(side=tk.LEFT)

        # ===== STEP PROGRESS INDICATOR =====
        self.step_tracker = StepTracker(content)

        # Progress bar
        self.progress = ttk.Progressbar(
            content, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(2, 6))

        # ===== LOG VIEW =====
        log_frame = tk.LabelFrame(content, text=" 📝 Log ",
                                  font=("Arial", 11, "bold"))
        log_frame.pack(fill=tk.BOTH, expand=True)

        log_container = tk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.log_text = tk.Text(log_container, height=10, wrap=tk.NONE,
                                font=("Consolas", 9), bg="#263238", fg="#B0BEC5",
                                insertbackground="white", relief=tk.FLAT)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Vertical scrollbar
        v_scroll = ttk.Scrollbar(log_container, orient=tk.VERTICAL,
                                 command=self.log_text.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text['yscrollcommand'] = v_scroll.set

        # Horizontal scrollbar
        h_scroll = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL,
                                 command=self.log_text.xview)
        h_scroll.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.log_text['xscrollcommand'] = h_scroll.set

        # Configure color tags for log levels
        self.log_text.tag_config("INFO", foreground="#64B5F6")      # Light blue
        self.log_text.tag_config("WARNING", foreground="#FFB74D")   # Orange
        self.log_text.tag_config("ERROR", foreground="#EF5350")     # Red
        self.log_text.tag_config("DEBUG", foreground="#78909C")     # Gray
        self.log_text.tag_config("SUCCESS", foreground="#81C784")   # Green

        # Attach GUI log handler
        self.gui_log_handler = TkLoggerHandler(self._append_log)
        self.gui_log_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger("po_merge_tool").addHandler(self.gui_log_handler)

    # ===== Settings Persistence =====

    def _restore_settings(self):
        """Restore last used paths from settings."""
        if self.settings.last_input_paths:
            for p in self.settings.last_input_paths:
                if os.path.exists(p):
                    display = self._format_file_entry(p)
                    self.file_listbox.insert(tk.END, display)
            self._validate_inputs()

        if self.settings.last_list_file and os.path.exists(self.settings.last_list_file):
            self.list_var.set(self.settings.last_list_file)

        if self.settings.last_output_dir and os.path.isdir(self.settings.last_output_dir):
            today_str = datetime.datetime.now().strftime("%d%m%Y")
            self.output_var.set(
                os.path.join(self.settings.last_output_dir, f"PO_{today_str}.pdf")
            )

    def _save_current_settings(self):
        """Save current paths to settings."""
        self.settings.last_input_paths = self._get_all_paths()
        self.settings.last_list_file = self.list_var.get().strip()
        out_path = self.output_var.get().strip()
        if out_path:
            self.settings.last_output_dir = str(Path(out_path).parent)
        self.settings.save()

    # ===== File Management =====

    def _format_file_entry(self, filepath: str) -> str:
        """Format a file path for display in the listbox."""
        p = Path(filepath)
        if p.is_file():
            size_kb = p.stat().st_size / 1024
            if size_kb > 1024:
                size_str = f"{size_kb / 1024:.1f} MB"
            else:
                size_str = f"{size_kb:.0f} KB"
            return f"{p.name}  ({size_str})  [{p.parent}]"
        elif p.is_dir():
            pdf_count = len(list(p.glob("*.pdf")))
            return f"📂 {p.name}  ({pdf_count} PDFs)  [{p.parent}]"
        return str(filepath)

    def _get_all_paths(self) -> List[str]:
        """Extract original file paths from listbox display entries."""
        paths = []
        for i in range(self.file_listbox.size()):
            entry = self.file_listbox.get(i)
            # Extract path from format: "name  (size)  [parent_dir]"
            if "[" in entry and "]" in entry:
                parent = entry[entry.rfind("[") + 1:entry.rfind("]")]
                name = entry.split("  (")[0].strip()
                # Remove folder icon if present
                if name.startswith("📂 "):
                    name = name[2:].strip()
                full_path = os.path.join(parent, name)
                paths.append(full_path)
            else:
                paths.append(entry)
        return paths

    def _add_files(self):
        """Open file dialog to add PDF files."""
        files = filedialog.askopenfilenames(
            title="Chọn file PDF (có thể chọn nhiều)",
            filetypes=[("PDF files", "*.pdf")])
        if files:
            existing = set(self._get_all_paths())
            for f in files:
                if f not in existing:
                    display = self._format_file_entry(f)
                    self.file_listbox.insert(tk.END, display)
            self._validate_inputs()

    def _add_folder(self):
        """Open folder dialog to add all PDFs from a folder."""
        folder = filedialog.askdirectory(title="Chọn folder chứa PDF")
        if folder:
            existing = set(self._get_all_paths())
            if folder not in existing:
                display = self._format_file_entry(folder)
                self.file_listbox.insert(tk.END, display)
            self._validate_inputs()

    def _remove_selected(self):
        """Remove selected items from the file listbox."""
        selected = list(self.file_listbox.curselection())
        for i in reversed(selected):
            self.file_listbox.delete(i)
        self._validate_inputs()

    def _clear_files(self):
        """Clear all items from the file listbox."""
        self.file_listbox.delete(0, tk.END)
        self._validate_inputs()

    def _choose_list(self):
        f = filedialog.askopenfilename(
            title="Chọn file danh sách mã cửa hàng",
            filetypes=[("CSV/TXT", "*.csv *.txt")])
        if f:
            self.list_var.set(f)

    def _choose_output(self):
        today_str = datetime.datetime.now().strftime("%d%m%Y")
        default_name = f"PO_{today_str}.pdf"
        f = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file output",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=default_name)
        if f:
            self.output_var.set(f)

    def _open_output_dir(self):
        out = Path(self.output_var.get())
        target_dir = out.parent if out.suffix else out
        if not target_dir.exists():
            messagebox.showinfo("Info", f"Thư mục chưa tồn tại: {target_dir}")
            return
        try:
            import webbrowser
            webbrowser.open(target_dir.as_uri())
        except Exception:
            messagebox.showinfo("Info", f"Mở thư mục: {target_dir}")

    # ===== Validation =====

    def _validate_inputs(self):
        """Validate input file list and update UI indicator."""
        paths = self._get_all_paths()
        count = self.file_listbox.size()
        if count > 0:
            self._valid_inputs = True
            self.input_status.config(text=f"✅ {count} mục đã chọn", fg="#2E7D32")
        else:
            self._valid_inputs = False
            self.input_status.config(text="⚠ Chưa chọn file", fg="#E65100")
        self._update_start_button()

    def _validate_list_file(self):
        """Validate the store list file and update UI indicator."""
        path = self.list_var.get().strip()
        if path and Path(path).exists():
            try:
                from core import read_store_list
                codes = read_store_list(Path(path))
                self._valid_list = True
                self.list_status.config(
                    text=f"✅ {len(codes)} mã cửa hàng", fg="#2E7D32")
            except Exception as e:
                self._valid_list = False
                self.list_status.config(text=f"❌ Lỗi đọc file", fg="#D32F2F")
        elif path:
            self._valid_list = False
            self.list_status.config(text="❌ File không tồn tại", fg="#D32F2F")
        else:
            self._valid_list = False
            self.list_status.config(text="⚠ Chưa chọn file", fg="#E65100")
        self._update_start_button()

    def _update_start_button(self):
        """Enable/disable start button based on validation state."""
        if self._valid_inputs and self._valid_list:
            self.start_btn.config(state=tk.NORMAL)
        else:
            self.start_btn.config(state=tk.DISABLED)

    # ===== Log Output =====

    def _append_log(self, text: str, level: str = "INFO"):
        """Append colored log message to the text widget."""
        # Determine tag based on level
        tag = level if level in ("INFO", "WARNING", "ERROR", "DEBUG") else "INFO"

        # Special: mark completion messages as SUCCESS
        if "Hoàn tất" in text or "Done" in text:
            tag = "SUCCESS"

        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)

    # ===== Staff Mapping View =====

    def _view_staff_mapping(self):
        """Display staff mapping information in a new window."""
        if not hasattr(self, '_staff_mapping_data') or not self._staff_mapping_data:
            messagebox.showinfo(
                "Info", "Không có dữ liệu staff mapping để hiển thị.")
            return

        staff_window = tk.Toplevel(self)
        staff_window.title("Staff - Store Code Mapping")
        staff_window.geometry("600x500")

        text_frame = ttk.Frame(staff_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10),
                              bg="#263238", fg="#B0BEC5")
        scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget.tag_config("header", foreground="#64B5F6",
                               font=("Consolas", 11, "bold"))
        text_widget.tag_config("staff", foreground="#81C784",
                               font=("Consolas", 10, "bold"))

        text_widget.insert(tk.END, "STAFF - STORE CODE MAPPING\n", "header")
        text_widget.insert(tk.END, "=" * 50 + "\n\n")

        for staff_name, store_codes in self._staff_mapping_data.items():
            text_widget.insert(tk.END, f"Staff: {staff_name}\n", "staff")
            text_widget.insert(
                tk.END, f"Store Codes ({len(store_codes)}): {', '.join(sorted(store_codes))}\n")
            text_widget.insert(tk.END, "-" * 30 + "\n\n")

        text_widget.config(state=tk.DISABLED)

        ttk.Button(staff_window, text="Đóng",
                   command=staff_window.destroy).pack(pady=10)

    # ===== Worker Thread =====

    def _on_start(self):
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showwarning(
                "Đang chạy", "Quá trình đang chạy, vui lòng chờ.")
            return

        output_val = self.output_var.get().strip()
        if not output_val:
            messagebox.showerror("Lỗi", "Vui lòng chọn nơi lưu file output.")
            return

        # Save settings before starting
        self._save_current_settings()

        # Disable start button and reset UI
        self.start_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.log_text.delete(1.0, tk.END)
        self.step_tracker.reset()

        # Clear previous staff mapping data
        if hasattr(self, '_staff_mapping_data'):
            delattr(self, '_staff_mapping_data')
        self.view_staff_btn.config(state=tk.DISABLED)

        # Collect input paths
        inputs = self._get_all_paths()

        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_run,
            args=(inputs, self.list_var.get().strip(), output_val, DEFAULT_PATTERN),
            daemon=True
        )
        self._worker_thread.start()

    def _worker_run(self, inputs, list_file, output_file, pattern):
        log = logging.getLogger("po_merge_tool")
        try:
            # Step 1: Read files
            self.step_tracker.activate_step("read")
            log.info("Bắt đầu xử lý...")

            pdfs = collect_input_pdfs(inputs, None)
            if not pdfs:
                log.error("Không tìm thấy file PDF nào. Hãy kiểm tra input.")
                self.step_tracker.error_step("read")
                return
            log.info("Tổng file PDF: %d", len(pdfs))

            store_order = read_store_list(Path(list_file))
            log.info("Danh sách mã load xong: %d mã", len(store_order))
            self.step_tracker.complete_step("read")

            # Step 2: Extract
            self.step_tracker.activate_step("extract")

            def extract_progress(done, total):
                try:
                    pct = int((done / total) * 70) if total else 0
                    self.progress['value'] = max(self.progress['value'], pct)
                except Exception:
                    pass

            def merge_progress(done, total):
                try:
                    base = 70
                    span = 30
                    pct = base + (int((done / total) * span) if total else 0)
                    self.progress['value'] = max(self.progress['value'], pct)
                except Exception:
                    pass

            result = extract_store_pages(
                pdfs, pattern, extract_progress, logger=log)
            try:
                self.progress['value'] = max(self.progress['value'], 70)
            except Exception:
                pass

            found_codes = set(result.store_pages.keys())
            expected_codes = set([c.upper() for c in store_order])
            missing = expected_codes - found_codes
            extra = found_codes - expected_codes
            if missing:
                log.warning("Không tìm thấy mã cửa hàng (Có trong list nhưng không có trong file PDF): %s", ", ".join(
                    list(missing)[:20]) + ("" if len(missing) <= 20 else " ..."))
            if extra:
                log.warning("Dư mã cửa hàng (Có trong file PDF nhưng không có trong list): %s", ", ".join(
                    list(extra)[:20]) + ("" if len(extra) <= 20 else " ..."))

            self.step_tracker.complete_step("extract")

            # Step 3: Merge
            self.step_tracker.activate_step("merge")

            # Load optional mappings
            code_name_map: Optional[Dict[str, str]] = None
            try:
                code_name_map = read_code_name_map(Path(list_file))
            except Exception:
                code_name_map = None

            code_staff_map: Optional[Dict[str, str]] = None
            try:
                code_staff_map = read_code_staff_map(Path(list_file))
                if code_staff_map:
                    log.info("Đã load mapping staff cho %d mã cửa hàng",
                             len(code_staff_map))

                    log.info("=== MAPPING STAFF - STORE CODES ===")
                    staff_store_summary: Dict[str, List[str]] = {}
                    for store_code, staff_name in code_staff_map.items():
                        if staff_name not in staff_store_summary:
                            staff_store_summary[staff_name] = []
                        staff_store_summary[staff_name].append(store_code)

                    for staff_name in sorted(staff_store_summary.keys()):
                        store_codes = sorted(staff_store_summary[staff_name])
                        log.info("Staff '%s' quản lý %d store codes: %s",
                                 staff_name, len(store_codes), ", ".join(store_codes))
                    log.info("==================================")

                    # Store for GUI display
                    self._staff_mapping_data = staff_store_summary
            except Exception:
                code_staff_map = None

            merge_and_write(result.store_pages, store_order,
                            Path(output_file), logger=log,
                            progress_cb=merge_progress,
                            code_to_name=code_name_map,
                            code_staff_map=code_staff_map)

            self.step_tracker.complete_step("merge")

            # Step 4: Done
            self.step_tracker.complete_step("done")
            log.info("Hoàn tất. Output: %s", output_file)

            # Enable staff mapping button
            if hasattr(self, '_staff_mapping_data') and self._staff_mapping_data:
                self.view_staff_btn.config(state=tk.NORMAL)

            try:
                messagebox.showinfo(
                    "Xong", f"Hoàn tất! Kết quả:\n{output_file}")
            except Exception:
                pass
        except Exception as e:
            log.exception("Lỗi khi chạy: %s", e)
            # Mark current active step as error
            for _, key in StepTracker.STEPS:
                self.step_tracker.error_step(key)
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi:\n{e}")
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.progress['value'] = 100


# ===== Entry Point =====

def main():
    parser = build_parser()
    args = parser.parse_args()
    has_cli_inputs = any([args.input_folder, args.input_files, args.list_file])

    if args.gui:
        if not TK_AVAILABLE:
            print("Tkinter không khả dụng. Dùng --web hoặc CLI.")
            return
        try:
            from gui_modern import launch_modern_gui
            launch_modern_gui()
        except Exception as e:
            print(f"[GUI] Không mở được giao diện mới: {e}")
            logging.getLogger("po_merge_tool").warning(
                "Falling back to classic Tkinter GUI: %s", e
            )
            app = POApp()
            app.mainloop()
        return

    if args.web or not has_cli_inputs:
        from web_app import launch_web
        launch_web(open_browser=not args.no_browser)
        return

    run_cli(args)


if __name__ == "__main__":
    main()
