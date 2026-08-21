"""
PO Management Tool — CLI Entry Point

Command-line interface for power users. Supports all features
available in the GUI without requiring Tkinter.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import DEFAULT_PATTERN, LOGFILE
from core import (
    setup_logging,
    collect_input_pdfs,
    read_store_list,
    read_code_name_map,
    read_code_staff_map,
    extract_store_pages,
    merge_and_write,
)


def run_cli(args: argparse.Namespace) -> None:
    """Execute the merge workflow from CLI arguments."""
    logger = setup_logging()

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

    # Simple text progress for CLI
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

    # Load optional mappings
    code_name_map: Optional[Dict[str, str]] = None
    try:
        code_name_map = read_code_name_map(Path(args.list_file))
    except Exception:
        code_name_map = None

    code_staff_map: Optional[Dict[str, str]] = None
    try:
        code_staff_map = read_code_staff_map(Path(args.list_file))
        if code_staff_map:
            logger.info("Staff mapping loaded for %d store codes",
                        len(code_staff_map))

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
    except Exception:
        code_staff_map = None

    merge_and_write(result.store_pages, store_order,
                    Path(args.output), logger=logger,
                    code_to_name=code_name_map,
                    code_staff_map=code_staff_map)
    logger.info("Done. Logfile: %s", LOGFILE)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
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
    return parser
