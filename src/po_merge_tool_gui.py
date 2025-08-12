#!/usr/bin/env python3
"""
PO Merge Tool - Modernized single-file script with optional Tkinter GUI
- Clean code, type hints, better logging
- Threaded GUI so it won't freeze
- CLI mode retained for power users

Usage:
  # GUI (recommended for non-IT):
  python po_merge_tool_gui.py --gui

  # CLI example:
  python po_merge_tool_gui.py --input-folder ./pdfs --list-file stores.csv --output PO_FINAL.pdf

Requirements (install with pip):
  pip install PyPDF2 pdfplumber pillow

"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, Dict, Iterable, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import fitz  # Add this with other imports

LOGFILE = "po_merge_tool.log"
DEFAULT_PATTERN = r"\bSG\d{4}\b"


def resource_path(rel_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, rel_path)


def find_font_file() -> str:
    """Find Roboto font file in various possible locations."""
    # Try multiple possible paths for the font
    possible_paths = [
        "assets/font/Roboto-ExtraBold.ttf",
        "font/Roboto-ExtraBold.ttf",  # Fallback for old builds
        "Roboto-ExtraBold.ttf"        # Direct fallback
    ]

    # Log the search process for debugging
    # logger = logging.getLogger("po_merge_tool")
    # logger.info("Tìm kiếm font Roboto-ExtraBold.ttf...")

    for path in possible_paths:
        full_path = resource_path(path)
        # logger.debug(f"Thử đường dẫn: {full_path}")
        if os.path.exists(full_path):
            # logger.info(f"Tìm thấy font tại: {full_path}")
            return full_path
        else:
            logger.debug(f"Không tìm thấy tại: {full_path}")

    # If none found, raise error with helpful message
    error_msg = (
        f"Không tìm thấy font Roboto-ExtraBold.ttf. "
        f"Đã thử các đường dẫn: {', '.join(possible_paths)}. "
        f"Vui lòng đảm bảo file font tồn tại trong thư mục assets/font/"
    )
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


def setup_logging(logfile: str = LOGFILE) -> logging.Logger:
    logger = logging.getLogger("po_merge_tool")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger


logger = setup_logging()


def read_store_list(path: Path) -> List[str]:
    """Read CSV or plain text list of PO/store codes. Returns uppercase trimmed codes in order."""
    if not path.exists():
        raise FileNotFoundError(path)
    codes: List[str] = []
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            rdr = csv.reader(f)
            for row in rdr:
                if not row:
                    continue
                code = str(row[0]).strip()
                if code:
                    codes.append(code.upper())
    else:
        with path.open(encoding="utf-8") as f:
            for line in f:
                code = line.strip()
                if code:
                    codes.append(code.upper())
    return codes


def read_code_name_map(path: Path) -> Dict[str, str]:
    """Read CSV with two columns: store code, store name.

    Returns a mapping code -> name. Codes are normalized to uppercase and trimmed.
    If the file does not exist, raises FileNotFoundError.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    mapping: Dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        for row in rdr:
            if not row:
                continue
            code = str(row[0]).strip().upper() if len(row) >= 1 else ""
            name = str(row[1]).strip() if len(row) >= 2 else ""
            if code:
                mapping[code] = name
    return mapping


def read_code_staff_map(path: Path) -> Dict[str, str]:
    """Read CSV with store code and staff columns.

    Expected format: store_code, store_name, staff_name
    Returns a mapping code -> staff. Codes are normalized to uppercase and trimmed.
    If the file does not exist, raises FileNotFoundError.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    mapping: Dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        for row in rdr:
            if not row or len(row) < 3:
                continue
            code = str(row[0]).strip().upper()
            staff = str(row[2]).strip()
            if code and staff:
                mapping[code] = staff
    return mapping


# def create_staff_report(code_staff_map: Dict[str, str], output_dir: Path, logger: Optional[logging.Logger] = None) -> Path:
#     """Create a comprehensive staff report showing store code mappings.

#     Args:
#         code_staff_map: Mapping of store codes to staff names
#         output_dir: Directory to save the report
#         logger: Logger instance for logging

#     Returns:
#         Path to the created report file
#     """
#     if logger is None:
#         logger = logging.getLogger("po_merge_tool")

#     # Group by staff
#     staff_store_summary: Dict[str, List[str]] = {}
#     for store_code, staff_name in code_staff_map.items():
#         if staff_name not in staff_store_summary:
#             staff_store_summary[staff_name] = []
#         staff_store_summary[staff_name].append(store_code)

#     # Create report filename with timestamp
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#     report_file = output_dir / f"staff_store_mapping_report_{timestamp}.txt"

#     try:
#         with report_file.open("w", encoding="utf-8") as f:
#             f.write("STAFF STORE CODE MAPPING REPORT\n")
#             f.write("=" * 50 + "\n")
#             f.write(
#                 f"Generated: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
#             f.write(f"Total Staff Members: {len(staff_store_summary)}\n")
#             f.write(f"Total Store Codes: {len(code_staff_map)}\n")
#             f.write("=" * 50 + "\n\n")

#             # Summary by staff
#             f.write("SUMMARY BY STAFF MEMBER:\n")
#             f.write("-" * 30 + "\n")
#             for staff_name in sorted(staff_store_summary.keys()):
#                 store_codes = sorted(staff_store_summary[staff_name])
#                 f.write(f"Staff: {staff_name}\n")
#                 f.write(f"  Store Codes: {len(store_codes)}\n")
#                 f.write(f"  Codes: {', '.join(store_codes)}\n\n")

#             # Detailed mapping
#             f.write("DETAILED MAPPING:\n")
#             f.write("-" * 30 + "\n")
#             for store_code in sorted(code_staff_map.keys()):
#                 staff_name = code_staff_map[store_code]
#                 f.write(f"{store_code} -> {staff_name}\n")

#         return report_file

#     except Exception as e:
#         logger.error("Failed to create staff report: %s", e)
#         raise


def collect_input_pdfs(input_files: Optional[Iterable[str]], input_folder: Optional[str]) -> List[Path]:
    files: List[Path] = []
    if input_folder:
        p = Path(input_folder)
        if p.exists() and p.is_dir():
            files += sorted([x for x in p.glob("*.pdf")])
    if input_files:
        for f in input_files:
            p = Path(f)
            if p.exists():
                if p.is_dir():
                    files += sorted([x for x in p.glob("*.pdf")])
                elif p.suffix.lower() == ".pdf":
                    files.append(p)
    # dedupe while preserving order
    seen = set()
    res: List[Path] = []
    for f in files:
        fs = str(f)
        if fs not in seen:
            seen.add(fs)
            res.append(f)
    return res


@dataclass
class ExtractResult:
    # map store_code -> list of PdfReader.PageObject
    store_pages: Dict[str, List]
    total_pages: int
    initial_buffer_pages: int


def extract_store_pages(pdf_files: List[Path], pattern: str, progress_cb: Optional[Callable[[int, int], None]] = None,
                        logger: Optional[logging.Logger] = None) -> ExtractResult:
    """Scan PDFs, extract pages per detected store code.

    Returns ExtractResult containing mapping and page counts.
    """
    if logger is None:
        logger = logging.getLogger("po_merge_tool")
    pat = re.compile(pattern, re.IGNORECASE)
    store_pages: Dict[str, List] = {}
    current_store: Optional[str] = None

    buffer_pages: List = []
    total_pages = 0
    # first pass: count pages for progress
    readers: List[Tuple[Path, int]] = []
    for pdf_file in pdf_files:
        try:
            r = PdfReader(str(pdf_file))
            readers.append((pdf_file, len(r.pages)))
            total_pages += len(r.pages)
        except Exception as e:
            logger.error("Failed reading %s: %s", pdf_file, e)
    processed = 0
    for pdf_file, page_count in readers:
        try:
            reader = PdfReader(str(pdf_file))
            with pdfplumber.open(str(pdf_file)) as plumber_pdf:
                for i in range(len(reader.pages)):
                    page_obj = reader.pages[i]
                    try:
                        text = plumber_pdf.pages[i].extract_text() or ""
                    except Exception:
                        # extraction may fail for some pages -> fallback to empty string
                        text = ""
                    m = pat.search(text)
                    if m:
                        code = m.group(0).upper()
                        if current_store is None and buffer_pages:
                            # assign buffer to this first discovered code
                            store_pages.setdefault(
                                code, []).extend(buffer_pages)
                            buffer_pages = []
                        current_store = code
                        store_pages.setdefault(
                            current_store, []).append(page_obj)
                    else:
                        if current_store is None:
                            buffer_pages.append(page_obj)
                        else:
                            store_pages.setdefault(
                                current_store, []).append(page_obj)
                    processed += 1
                    if progress_cb:
                        progress_cb(processed, total_pages)
        except Exception as e:
            logger.exception("Error processing %s: %s", pdf_file, e)

    if buffer_pages:
        logger.warning(
            "There are %d pages before the first detected code.", len(buffer_pages))
        if store_pages:
            first_code = next(iter(store_pages))
            logger.info(
                "Appending those initial pages to first detected code: %s", first_code)
            store_pages[first_code] = buffer_pages + store_pages[first_code]
        else:
            logger.error("No PO code found at all in input PDFs.")

    return ExtractResult(store_pages=store_pages, total_pages=total_pages, initial_buffer_pages=len(buffer_pages))


def merge_and_write(store_pages_map: Dict[str, List], store_order: List[str], output_file: Path,
                    logger: Optional[logging.Logger] = None, progress_cb: Optional[Callable[[int, int], None]] = None,
                    code_to_name: Optional[Dict[str, str]] = None, code_staff_map: Optional[Dict[str, str]] = None) -> None:
    """Merge pages following store_order, then annotate quantities, then export final file.

    The merged content is first written to a temporary PDF. Quantities are annotated
    onto that temporary file. Only after successful annotation will the result be
    moved to the requested output path. If annotation fails, no final output file
    is produced.

    Args:
        store_pages_map: Mapping of store codes to page objects
        store_order: List of store codes in desired order
        output_file: Path for the final output PDF
        logger: Logger instance for logging
        progress_cb: Callback function for progress updates
        code_to_name: Optional mapping of store codes to store names
        code_staff_map: Optional mapping of store codes to staff names for staff-based quantity totals
    """
    writer = PdfWriter()
    expected = [s.upper() for s in store_order]
    found = list(store_pages_map.keys())

    # Determine extras and count total pages to be merged
    extras = [c for c in found if c not in expected]
    expected_pages_count = sum(
        len(store_pages_map[c]) for c in expected if c in store_pages_map)
    extras_pages_count = sum(len(store_pages_map[c]) for c in extras)
    merged_pages_total = expected_pages_count + extras_pages_count

    # Progress steps: per-code merge ticks + 1 (write temp) + per-page annotate ticks (2x pages) + 1 (finalize)
    annotate_ticks = merged_pages_total * 2
    total_steps = len(expected) + len(extras) + 1 + annotate_ticks + 1
    current_step = 0

    # Merge in expected order
    for code in expected:
        if code in store_pages_map:
            for p in store_pages_map[code]:
                writer.add_page(p)
        else:
            if logger:
                store_name = (code_to_name or {}).get(code)
                if store_name:
                    logger.warning(
                        "Không có mã cửa hàng: %s - %s", code, store_name)
                else:
                    logger.warning("Không có mã cửa hàng: %s", code)
        current_step += 1
        if progress_cb:
            progress_cb(current_step, total_steps)

    # Append extras at the end
    if extras and logger:
        logger.info("Appending %d extra detected codes at end: %s", len(
            extras), ", ".join(extras[:10]) + ("..." if len(extras) > 10 else ""))
    for code in extras:
        for p in store_pages_map[code]:
            writer.add_page(p)
        current_step += 1
        if progress_cb:
            progress_cb(current_step, total_steps)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write merged PDF to a temporary file first
    tmp_merged = output_file.parent / \
        f"{output_file.stem}__merged_tmp{output_file.suffix}"
    with tmp_merged.open("wb") as f:
        writer.write(f)
    if logger:
        logger.info("Đã hợp nhất vào file tạm: %s", tmp_merged)

    current_step += 1
    if progress_cb:
        progress_cb(current_step, total_steps)

    # Annotate quantities on the temporary merged PDF (with per-page progress)
    try:
        if logger:
            logger.info("Thêm các chú thích số lượng...")

        def on_tick():
            nonlocal current_step
            current_step += 1
            if progress_cb:
                progress_cb(current_step, total_steps)

        annotate_quantities(tmp_merged, logger, on_tick=on_tick,
                            store_pages_map=store_pages_map,
                            code_staff_map=code_staff_map,
                            store_order=store_order)
    except Exception as e:
        if logger:
            logger.error(f"Failed to add quantities: {e}")
        # Do not export final file if annotation fails
        raise

    current_step += 1
    if progress_cb:
        progress_cb(current_step, total_steps)

    # Move annotated temp file to final output path
    tmp_merged.replace(output_file)
    if logger:
        logger.info("Xuất file PDF cuối cùng: %s", output_file)

    current_step += 1
    if progress_cb:
        progress_cb(current_step, total_steps)


# Thêm function này sau các functions hiện có và trước class POApp
def annotate_quantities(pdf_path: Path, logger: Optional[logging.Logger] = None,
                        on_tick: Optional[Callable[[], None]] = None,
                        store_pages_map: Optional[Dict[str, List]] = None,
                        code_staff_map: Optional[Dict[str, str]] = None,
                        store_order: Optional[List[str]] = None) -> None:
    """Extract and annotate order quantities on each page.

    Args:
        pdf_path: Path to the PDF file to annotate
        logger: Logger instance for logging
        on_tick: Callback function for progress updates
        store_pages_map: Mapping of store codes to page objects (from extract_store_pages)
        code_staff_map: Mapping of store codes to staff names
        store_order: List of store codes in the desired order for logging
    """
    if logger is None:
        logger = logging.getLogger("po_merge_tool")

    def get_qty_from_table(page) -> Optional[int]:
        try:
            table = page.extract_table()
            if table:
                for row in table:
                    if not row or "order" in str(row).lower():
                        continue
                    try:
                        qty = int(row[7])  # column 8 (index 7)
                        return qty // 2
                    except (ValueError, IndexError, TypeError):
                        continue
        except Exception as e:
            logger.debug(f"Failed extracting table from page: {e}")
        return None

    try:
        tmp_path = pdf_path.with_stem(pdf_path.stem + "_tmp")
        with pdfplumber.open(str(pdf_path)) as pdf:
            total_pages = len(pdf.pages)
            qty_values = []

            # Extract quantities
            for i, page in enumerate(pdf.pages):
                qty = get_qty_from_table(page)
                qty_values.append(qty)
                if on_tick:
                    try:
                        on_tick()
                    except Exception:
                        pass

            # Log total quantity after division by 2 (ignoring pages without quantity)
            try:
                total_qty_after_div2 = sum(
                    q for q in qty_values if q is not None)
                date_str = datetime.datetime.now().strftime("%d/%m/%Y")
                logger.info("Tổng số lượng ngày %s: %d",
                            date_str, total_qty_after_div2)

                # Calculate and log quantities by staff if mapping is available
                if store_pages_map and code_staff_map:
                    staff_totals: Dict[str, int] = {}
                    staff_store_mapping: Dict[str, List[str]] = {}

                    # Calculate quantities per store code
                    # We need to track which pages belong to which store codes
                    # Since pages are merged in order, we can calculate this
                    current_page = 0
                    store_qty_map: Dict[str, int] = {}

                    for store_code, pages in store_pages_map.items():
                        store_total = 0
                        # Calculate total quantity for this store code
                        for i in range(len(pages)):
                            if current_page < len(qty_values) and qty_values[current_page] is not None:
                                store_total += qty_values[current_page]
                            current_page += 1

                        if store_total > 0:
                            store_qty_map[store_code] = store_total

                            # Add to staff total and track store codes
                            staff_name = code_staff_map.get(
                                store_code, "Unknown Staff")
                            if staff_name not in staff_totals:
                                staff_totals[staff_name] = 0
                                staff_store_mapping[staff_name] = []
                            staff_totals[staff_name] += store_total
                            staff_store_mapping[staff_name].append(store_code)

                    # Enhanced logging: Staff details with store code mappings
                    if staff_totals:
                        logger.info("=== CHI TIẾT STAFF VÀ STORE CODES ===")
                        logger.info(
                            "Đang xử lý dữ liệu cho %d staff members...", len(staff_totals))

                        for staff_name in sorted(staff_totals.keys()):
                            total_qty = staff_totals[staff_name]
                            store_codes = sorted(
                                staff_store_mapping[staff_name])
                            store_count = len(store_codes)

                            logger.info("Staff: %s", staff_name)
                            logger.info("  - Tổng quantity: %d", total_qty)
                            logger.info("  - Số store codes: %d", store_count)
                            logger.info("  - Store codes: %s",
                                        ", ".join(store_codes))
                            logger.info(
                                "  - Trung bình/Store: %.1f", total_qty / store_count if store_count > 0 else 0)
                            logger.info("")

                        logger.info("=== TỔNG QUANTITY THEO STAFF ===")
                        for staff_name, total in sorted(staff_totals.items()):
                            logger.info("Staff %s: %d", staff_name, total)
                        logger.info("================================")

                        # Log summary statistics
                        total_staff = len(staff_totals)
                        total_stores = sum(len(codes)
                                           for codes in staff_store_mapping.values())
                        avg_stores_per_staff = total_stores / total_staff if total_staff > 0 else 0
                        logger.info("=== THỐNG KÊ TỔNG QUAN ===")
                        logger.info("Tổng số staff: %d", total_staff)
                        logger.info("Tổng số store codes: %d", total_stores)
                        logger.info(
                            "Trung bình store codes/staff: %.1f", avg_stores_per_staff)
                        logger.info("==========================")

                    # Log store code totals for debugging
                    if store_qty_map:
                        logger.info("=== TỔNG QUANTITY THEO MÃ CỬA HÀNG ===")
                        # Log in the order of the store code list, not alphabetically
                        if store_order:
                            for store_code in store_order:
                                if store_code in store_qty_map:
                                    total = store_qty_map[store_code]
                                    staff_name = code_staff_map.get(
                                        store_code, "Unknown")
                                    logger.info("%s (Staff: %s): %d", store_code,
                                                staff_name, total)

                            # Log any extra codes that weren't in the original list
                            extra_codes = [
                                code for code in store_qty_map.keys() if code not in store_order]
                            if extra_codes:
                                logger.info(
                                    "--- Extra codes found in PDFs ---")
                                for store_code in sorted(extra_codes):
                                    total = store_qty_map[store_code]
                                    staff_name = code_staff_map.get(
                                        store_code, "Unknown")
                                    logger.info("%s (Staff: %s): %d", store_code,
                                                staff_name, total)
                        else:
                            # Fallback to alphabetical order if no store_order provided
                            for store_code, total in sorted(store_qty_map.items()):
                                staff_name = code_staff_map.get(
                                    store_code, "Unknown")
                                logger.info("%s (Staff: %s): %d", store_code,
                                            staff_name, total)

                        logger.info("=======================================")

            except Exception:
                # Avoid breaking flow due to logging calculation
                pass

        # Annotate PDF
        with fitz.open(str(pdf_path)) as doc:
            # Find Roboto font file using the enhanced finder
            roboto_path = Path(find_font_file())
            roboto_font_name = "RobotoExtraBold"

            for i, (page, qty) in enumerate(zip(doc, qty_values)):
                if qty is not None:
                    text = str(qty)
                    x, y = page.rect.width - 40, page.rect.height - 1
                    # Ensure custom font is available on this page
                    page.insert_font(fontname=roboto_font_name,
                                     fontfile=str(roboto_path))
                    page.insert_text((x, y), text, fontsize=20,
                                     color=(1, 0, 0), fontname=roboto_font_name)
                if on_tick:
                    try:
                        on_tick()
                    except Exception:
                        pass
            doc.save(str(tmp_path))

        # Replace original with annotated version
        tmp_path.replace(pdf_path)
        logger.info("Đã thêm chú thích số lượng vào trong file PO")

    except Exception as e:
        logger.error(f"Failed to process quantities: {e}")
        raise


# -----------------------
# Minimal Tkinter GUI for non-IT users
# -----------------------

class TkLoggerHandler(logging.Handler):
    """Logging handler that posts messages to a callback (used by GUI)."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        try:
            self.callback(msg + "\n")
        except Exception:
            pass


class POApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PO Management Tool")
        self.geometry("900x600")

        # Set application icon
        self._set_icon()

        self._build_ui()
        self._worker_thread: Optional[threading.Thread] = None

    def _set_icon(self):
        """Set application icon from available icon files using PyInstaller-compatible paths."""
        try:
            # Set icon .ico (Windows) - highest priority
            ico_path = resource_path("assets/icon/app.ico")
            if os.path.exists(ico_path):
                print(f"Setting ICO icon from: {ico_path}")
                self.iconbitmap(ico_path)
                # Also try to set taskbar icon explicitly
                try:
                    import ctypes
                    myappid = 'lpa.pop.merge.tool.1.0'  # arbitrary string
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        myappid)
                except Exception as e:
                    print(f"Could not set taskbar icon ID: {e}")
                return

            # Set icon PNG (cross-platform) - fallback
            png_path = resource_path("assets/icon/LPA-256.png")
            if os.path.exists(png_path):
                try:
                    print(f"Setting PNG icon from: {png_path}")
                    icon_img = tk.PhotoImage(file=png_path)
                    self.iconphoto(False, icon_img)
                    return
                except Exception as e:
                    print(f"Could not load PNG icon: {e}")

            # If no icons found, continue without setting icon
            print("No icon files found in assets/icon/ folder")

        except Exception as e:
            # Log error but don't crash the application
            print(f"Could not set application icon: {e}")

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # Row 1 - inputs
        inp_frame = tk.LabelFrame(
            frm, text="Chọn các file PO", font=("Arial", 12, "bold"))
        inp_frame.pack(fill=tk.X, pady=4)
        self.input_paths_var = tk.StringVar(value="")
        inp_row = ttk.Frame(inp_frame)
        inp_row.pack(fill=tk.X, padx=6, pady=6)
        self.input_entry = ttk.Entry(
            inp_row, textvariable=self.input_paths_var)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(inp_row, text="Chọn file/folder",
                   command=self._choose_input).pack(side=tk.LEFT, padx=6)

        # Row 2 - list file
        list_frame = ttk.Frame(frm)
        list_frame.pack(fill=tk.X, pady=4)
        tk.Label(list_frame, text="Danh sách mã cửa hàng (CSV/TXT):",
                 font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        self.list_var = tk.StringVar()
        self.list_entry = ttk.Entry(list_frame, textvariable=self.list_var)
        self.list_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(list_frame, text="Chọn...",
                   command=self._choose_list).pack(side=tk.LEFT)

        # Row 3 - output
        out_frame = ttk.Frame(frm)
        out_frame.pack(fill=tk.X, pady=4)
        tk.Label(out_frame, text="Chỗ lưu PO:", font=(
            "Arial", 12, "bold")).pack(side=tk.LEFT)
        # Tạo tên file theo ngày hiện tại, format PO_DDMMYYYY.pdf
        today_str = datetime.datetime.now().strftime("%d%m%Y")
        default_output_name = f"PO_{today_str}.pdf"
        self.output_var = tk.StringVar(value=default_output_name)
        self.output_entry = ttk.Entry(out_frame, textvariable=self.output_var)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(out_frame, text="Chọn...",
                   command=self._choose_output).pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=6)
        self.start_btn = tk.Button(
            btn_frame, text="Bắt đầu", font=("Arial", 8, "bold"), command=self._on_start)
        self.start_btn.pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Mở thư mục PO", font=("Arial", 8, "bold"),
                  command=self._open_output_dir).pack(side=tk.LEFT, padx=6)
        self.view_staff_btn = tk.Button(btn_frame, text="Xem Staff Mapping", font=("Arial", 8, "bold"),
                                        command=self._view_staff_mapping, state=tk.DISABLED)
        self.view_staff_btn.pack(side=tk.LEFT, padx=6)

        # Progress
        self.progress = ttk.Progressbar(
            frm, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.pack(fill=tk.X, pady=6)

        # Log view
        log_frame = ttk.LabelFrame(frm, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log_text = tk.Text(log_frame, height=12, wrap=tk.NONE)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text['yscrollcommand'] = scroll.set

        # attach a GUI log handler
        self.gui_log_handler = TkLoggerHandler(self._append_log)
        self.gui_log_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s"))
        logging.getLogger("po_merge_tool").addHandler(self.gui_log_handler)

    def _append_log(self, text: str):
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _choose_input(self):
        files = filedialog.askopenfilenames(
            title="Chọn file PDF (có thể chọn nhiều)", filetypes=[("PDF files", "*.pdf")])
        if files:
            # allow mixing files and folder by letting user input comma-separated values
            self.input_paths_var.set(",".join(files))
        else:
            folder = filedialog.askdirectory(title="Hoặc chọn folder chứa PDF")
            if folder:
                self.input_paths_var.set(folder)

    def _choose_list(self):
        f = filedialog.askopenfilename(title="Chọn ListMCH.csv hoặc .txt", filetypes=[
                                       ("CSV/TXT", "*.csv *.txt")])
        if f:
            self.list_var.set(f)

    def _choose_output(self):
        today_str = datetime.datetime.now().strftime("%d%m%Y")
        default_output_name = f"PO_{today_str}.pdf"
        f = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file output",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=default_output_name  # Luôn cập nhật tên theo ngày hiện tại
        )
        if f:
            self.output_var.set(f)

    def _open_output_dir(self):
        out = Path(self.output_var.get())
        if not out.exists():
            messagebox.showinfo(
                "Info", "File output chưa tồn tại: %s" % str(out))
            return
        try:
            import webbrowser
            webbrowser.open(out.parent.as_uri())
        except Exception:
            messagebox.showinfo("Info", f"Mở thư mục: {out.parent}")

    def _view_staff_mapping(self):
        """Display staff mapping information in a new window."""
        if not hasattr(self, '_staff_mapping_data') or not self._staff_mapping_data:
            messagebox.showinfo(
                "Info", "Không có dữ liệu staff mapping để hiển thị.")
            return

        # Create a new window to display staff mapping
        staff_window = tk.Toplevel(self)
        staff_window.title("Staff - Store Code Mapping")
        staff_window.geometry("600x500")

        # Create text widget with scrollbar
        text_frame = ttk.Frame(staff_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate with staff mapping data
        text_widget.insert(tk.END, "STAFF - STORE CODE MAPPING\n")
        text_widget.insert(tk.END, "=" * 50 + "\n\n")

        for staff_name, store_codes in self._staff_mapping_data.items():
            text_widget.insert(tk.END, f"Staff: {staff_name}\n")
            text_widget.insert(
                tk.END, f"Store Codes ({len(store_codes)}): {', '.join(sorted(store_codes))}\n")
            text_widget.insert(tk.END, "-" * 30 + "\n\n")

        text_widget.config(state=tk.DISABLED)  # Make read-only

        # Add close button
        ttk.Button(staff_window, text="Đóng",
                   command=staff_window.destroy).pack(pady=10)

    def _on_start(self):
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showwarning(
                "Đang chạy", "Quá trình đang chạy, vui lòng chờ.")
            return
        # basic validation
        input_val = self.input_paths_var.get().strip()
        list_val = self.list_var.get().strip()
        output_val = self.output_var.get().strip()
        pattern = DEFAULT_PATTERN
        if not input_val:
            messagebox.showerror("Lỗi", "Vui lòng chọn file/folder chứa PDF.")
            return
        if not list_val or not Path(list_val).exists():
            messagebox.showerror(
                "Lỗi", "Vui lòng chọn file danh sách mã cửa hàng (CSV/TXT) hợp lệ.")
            return
        # disable start button during work
        self.start_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.log_text.delete(1.0, tk.END)

        # Clear previous staff mapping data and disable button
        if hasattr(self, '_staff_mapping_data'):
            delattr(self, '_staff_mapping_data')
        self.view_staff_btn.config(state=tk.DISABLED)

        # prepare input files list
        inputs = [p.strip() for p in input_val.split(",") if p.strip()]

        # start worker thread
        self._worker_thread = threading.Thread(target=self._worker_run, args=(
            inputs, list_val, output_val, pattern), daemon=True)
        self._worker_thread.start()

    def _worker_run(self, inputs, list_file, output_file, pattern):
        log = logging.getLogger("po_merge_tool")
        try:
            log.info("Bắt đầu xử lý...")
            pdfs = collect_input_pdfs(inputs, None)
            if not pdfs:
                log.error("Không tìm thấy file PDF nào. Hãy kiểm tra input.")
                return
            log.info("Tổng file PDF: %d", len(pdfs))
            store_order = read_store_list(Path(list_file))
            log.info("Danh sách mã load xong: %d mã", len(store_order))

            # Progress mapping: extraction 0-70%, merge+annotate+finalize 70-100%
            def extract_progress(done, total):
                try:
                    pct = int((done / total) * 70) if total else 0
                    self.progress['value'] = max(self.progress['value'], pct)
                except Exception:
                    pass

            def merge_progress(done, total):
                try:
                    # Map merge/write/annotate/finalize to 70-100 based on relative steps
                    base = 70
                    span = 30
                    pct = base + (int((done / total) * span) if total else 0)
                    self.progress['value'] = max(self.progress['value'], pct)
                except Exception:
                    pass

            result = extract_store_pages(
                pdfs, pattern, extract_progress, logger=log)
            # Ensure we land at 70% after extraction
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

            # Load optional code->name mapping from the selected list file (supports 1 or 2 columns)
            code_name_map: Optional[Dict[str, str]] = None
            try:
                code_name_map = read_code_name_map(Path(list_file))
            except Exception:
                code_name_map = None

            # Load staff mapping if available
            code_staff_map: Optional[Dict[str, str]] = None
            try:
                code_staff_map = read_code_staff_map(Path(list_file))
                if code_staff_map:
                    log.info("Đã load mapping staff cho %d mã cửa hàng",
                             len(code_staff_map))

                    # Log detailed staff-store code mapping
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

                    # Store staff mapping data for GUI display
                    self._staff_mapping_data = staff_store_summary

                    # Create staff report file
                    # try:
                    #     output_path = Path(output_file)
                    #     staff_report = create_staff_report(
                    #         code_staff_map, output_path.parent, log)
                    #     log.info("Báo cáo staff đã được tạo: %s", staff_report)
                    # except Exception as e:
                    #     log.warning("Không thể tạo báo cáo staff: %s", e)
            except Exception:
                code_staff_map = None

            merge_and_write(result.store_pages, store_order,
                            Path(output_file), logger=log,
                            progress_cb=merge_progress,
                            code_to_name=code_name_map,
                            code_staff_map=code_staff_map)

            log.info("Hoàn tất. Output: %s", output_file)

            # Enable staff mapping button if data is available
            if hasattr(self, '_staff_mapping_data') and self._staff_mapping_data:
                self.view_staff_btn.config(state=tk.NORMAL)

            try:
                messagebox.showinfo(
                    "Xong", f"Hoàn tất! Kết quả: {output_file}")
            except Exception:
                pass
        except Exception as e:
            log.exception("Lỗi khi chạy: %s", e)
            messagebox.showerror("Lỗi", f"Đã xảy ra lỗi: {e}")
        finally:
            self.start_btn.config(state=tk.NORMAL)
            self.progress['value'] = 100


def main():
    parser = argparse.ArgumentParser(
        description="PO Merge Tool - Trích xuất và hợp nhất Purchase Order theo thứ tự")
    parser.add_argument(
        "--input-folder", help="Folder chứa các PDF (tất cả .pdf trong folder sẽ theo thứ tự alpha)")
    parser.add_argument("--input-files", nargs="*",
                        help="Các file pdf (hoặc folder) -- có thể truyền nhiều")
    parser.add_argument(
        "--list-file", help="File danh sách mã cửa hàng (CSV hoặc TXT)")
    parser.add_argument(
        "--output", help="Đường dẫn file PDF output hoặc thư mục để lưu file", default="PO_FINAL.pdf")
    parser.add_argument(
        "--pattern", help="Regex pattern để tìm mã (mặc định: SG\\d{4})", default=DEFAULT_PATTERN)
    parser.add_argument("--gui", action="store_true",
                        help="Mở giao diện đồ họa (GUI)")
    args = parser.parse_args()

    if args.gui or (not any([args.input_folder, args.input_files, args.list_file]) and TK_AVAILABLE):
        if not TK_AVAILABLE:
            print(
                "Tkinter không khả dụng trên hệ thống này. Hãy chạy không dùng --gui hoặc cài tkinter.")
            return
        app = POApp()
        app.mainloop()
        return

    # CLI mode
    inp = collect_input_pdfs(args.input_files, args.input_folder)
    if not inp:
        logger.error(
            "No input PDFs found. Provide --input-folder or --input-files.")
        return
    if not args.list_file or not Path(args.list_file).exists():
        logger.error("List file not found. Provide --list-file.")
        return

    logger.info("Input pdfs: %s", ", ".join(map(str, inp)))
    logger.info("Store list: %s", args.list_file)

    store_order = read_store_list(Path(args.list_file))
    logger.info("Store list loaded: %d codes", len(store_order))

    # progress bar in CLI: simple text
    def cli_progress(done, total):
        pct = int(done / total * 100) if total else 0
        print(f"Progress: {pct}% ({done}/{total})", end="\r")

    result = extract_store_pages(
        inp, args.pattern, progress_cb=cli_progress, logger=logger)
    print()
    found_codes = set(result.store_pages.keys())
    expected_codes = set([c.upper() for c in store_order])
    missing = expected_codes - found_codes
    extra = found_codes - expected_codes
    if missing:
        logger.warning("Missing codes (in list but not found in PDFs): %s", ", ".join(
            list(missing)[:20]) + ("" if len(missing) <= 20 else " ..."))
    if extra:
        logger.warning("Extra detected codes (found in PDFs but not in list): %s", ", ".join(
            list(extra)[:20]) + ("" if len(extra) <= 20 else " ..."))

    # Load optional code->name mapping from the provided list file (supports 1 or 2 columns)
    code_name_map: Optional[Dict[str, str]] = None
    try:
        code_name_map = read_code_name_map(Path(args.list_file))
    except Exception:
        code_name_map = None

    # Load optional staff mapping from the provided list file (supports 3 columns: code, name, staff)
    code_staff_map: Optional[Dict[str, str]] = None
    try:
        code_staff_map = read_code_staff_map(Path(args.list_file))
        if code_staff_map:
            logger.info("Staff mapping loaded for %d store codes",
                        len(code_staff_map))

            # Log detailed staff-store code mapping
            logger.info("=== MAPPING STAFF - STORE CODES ===")
            staff_store_summary: Dict[str, List[str]] = {}
            for store_code, staff_name in code_staff_map.items():
                if staff_name not in staff_store_summary:
                    staff_store_summary[staff_name] = []
                staff_store_summary[staff_name].append(store_code)

            for staff_name in sorted(staff_store_summary.keys()):
                store_codes = sorted(staff_store_summary[staff_name])
                logger.info("Staff '%s' manages %d store codes: %s",
                            staff_name, len(store_codes), ", ".join(store_codes))
            logger.info("==================================")

            # # Create staff report file
            # try:
            #     output_path = Path(args.output)
            #     staff_report = create_staff_report(
            #         code_staff_map, output_path.parent, logger)
            #     logger.info("Staff report created: %s", staff_report)
            # except Exception as e:
            #     logger.warning("Could not create staff report: %s", e)
    except Exception:
        code_staff_map = None

    merge_and_write(result.store_pages, store_order,
                    Path(args.output), logger=logger,
                    code_to_name=code_name_map,
                    code_staff_map=code_staff_map)
    logger.info("Done. Logfile: %s", LOGFILE)


if __name__ == "__main__":
    main()
