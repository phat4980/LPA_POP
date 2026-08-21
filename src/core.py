"""
PO Management Tool — Core Business Logic

All PDF processing logic: reading store lists, extracting pages by store code,
merging PDFs, and annotating quantities. No GUI dependencies.
"""

from __future__ import annotations

import csv
import datetime
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import fitz

from config import resource_path, LOGFILE


@dataclass
class AnnotationResult:
    total_qty: int = 0
    staff_totals: Dict[str, int] = field(default_factory=dict)
    staff_store_map: Dict[str, List[str]] = field(default_factory=dict)
    store_qty_map: Dict[str, int] = field(default_factory=dict)

# ===== Logging =====


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


# ===== Font Utilities =====


def find_font_file() -> str:
    """Find Roboto font file in various possible locations."""
    possible_paths = [
        "assets/font/Roboto-ExtraBold.ttf",
        "font/Roboto-ExtraBold.ttf",
        "Roboto-ExtraBold.ttf"
    ]
    for path in possible_paths:
        full_path = resource_path(path)
        if os.path.exists(full_path):
            return full_path

    error_msg = (
        f"Không tìm thấy font Roboto-ExtraBold.ttf. "
        f"Đã thử các đường dẫn: {', '.join(possible_paths)}. "
        f"Vui lòng đảm bảo file font tồn tại trong thư mục assets/font/"
    )
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


# ===== Store List Readers =====


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


# ===== PDF Collection =====


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


# ===== Extraction =====


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
                        text = ""
                    m = pat.search(text)
                    if m:
                        code = m.group(0).upper()
                        if current_store is None and buffer_pages:
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


# ===== Merge & Write =====


def merge_and_write(store_pages_map: Dict[str, List], store_order: List[str], output_file: Path,
                    logger: Optional[logging.Logger] = None, progress_cb: Optional[Callable[[int, int], None]] = None,
                    code_to_name: Optional[Dict[str, str]] = None, code_staff_map: Optional[Dict[str, str]] = None) -> AnnotationResult:
    """Merge pages following store_order, then annotate quantities, then export final file."""
    writer = PdfWriter()
    expected = [s.upper() for s in store_order]
    found = list(store_pages_map.keys())

    # Determine extras and count total pages to be merged
    extras = [c for c in found if c not in expected]
    expected_pages_count = sum(
        len(store_pages_map[c]) for c in expected if c in store_pages_map)
    extras_pages_count = sum(len(store_pages_map[c]) for c in extras)
    merged_pages_total = expected_pages_count + extras_pages_count

    # Progress steps
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

    # Annotate quantities on the temporary merged PDF
    annot_res = AnnotationResult()
    try:
        if logger:
            logger.info("Thêm các chú thích số lượng...")

        def on_tick():
            nonlocal current_step
            current_step += 1
            if progress_cb:
                progress_cb(current_step, total_steps)

        annot_res = annotate_quantities(tmp_merged, logger, on_tick=on_tick,
                                        store_pages_map=store_pages_map,
                                        code_staff_map=code_staff_map,
                                        store_order=store_order)
    except Exception as e:
        if logger:
            logger.error(f"Failed to add quantities: {e}")
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

    return annot_res


# ===== Quantity Annotation =====


def annotate_quantities(pdf_path: Path, logger: Optional[logging.Logger] = None,
                        on_tick: Optional[Callable[[], None]] = None,
                        store_pages_map: Optional[Dict[str, List]] = None,
                        code_staff_map: Optional[Dict[str, str]] = None,
                        store_order: Optional[List[str]] = None) -> AnnotationResult:
    """Extract and annotate order quantities on each page."""
    if logger is None:
        logger = logging.getLogger("po_merge_tool")

    annot_result = AnnotationResult()

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

            # Log total quantity after division by 2
            try:
                total_qty_after_div2 = sum(
                    q for q in qty_values if q is not None)
                annot_result.total_qty = total_qty_after_div2
                date_str = datetime.datetime.now().strftime("%d/%m/%Y")
                logger.info("Tổng số lượng ngày %s: %d",
                            date_str, total_qty_after_div2)

                # Calculate and log quantities by staff if mapping is available
                if store_pages_map and code_staff_map:
                    staff_totals: Dict[str, int] = {}
                    staff_store_mapping: Dict[str, List[str]] = {}

                    current_page = 0
                    store_qty_map: Dict[str, int] = {}

                    for store_code, pages in store_pages_map.items():
                        store_total = 0
                        for i in range(len(pages)):
                            if current_page < len(qty_values) and qty_values[current_page] is not None:
                                store_total += qty_values[current_page]
                            current_page += 1

                        if store_total > 0:
                            store_qty_map[store_code] = store_total
                            staff_name = code_staff_map.get(
                                store_code, "Unknown Staff")
                            if staff_name not in staff_totals:
                                staff_totals[staff_name] = 0
                                staff_store_mapping[staff_name] = []
                            staff_totals[staff_name] += store_total
                            staff_store_mapping[staff_name].append(store_code)

                    annot_result.staff_totals = staff_totals
                    annot_result.staff_store_map = staff_store_mapping
                    annot_result.store_qty_map = store_qty_map

                    # Enhanced logging: Staff details
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

                        # Summary statistics
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

                    # Log store code totals
                    if store_qty_map:
                        logger.info("=== TỔNG QUANTITY THEO MÃ CỬA HÀNG ===")
                        if store_order:
                            for store_code in store_order:
                                if store_code in store_qty_map:
                                    total = store_qty_map[store_code]
                                    staff_name = code_staff_map.get(
                                        store_code, "Unknown")
                                    logger.info("%s (Staff: %s): %d", store_code,
                                                staff_name, total)
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
                            for store_code, total in sorted(store_qty_map.items()):
                                staff_name = code_staff_map.get(
                                    store_code, "Unknown")
                                logger.info("%s (Staff: %s): %d", store_code,
                                            staff_name, total)
                        logger.info("=======================================")

            except Exception:
                pass

        # Annotate PDF with fitz
        with fitz.open(str(pdf_path)) as doc:
            roboto_path = Path(find_font_file())
            roboto_font_name = "RobotoExtraBold"

            for i, (page, qty) in enumerate(zip(doc, qty_values)):
                if qty is not None:
                    text = str(qty)
                    x, y = page.rect.width - 40, page.rect.height - 1
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

        return annot_result

    except Exception as e:
        logger.error(f"Failed to process quantities: {e}")
        raise
