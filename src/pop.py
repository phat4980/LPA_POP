"""
POP - Sample code to process PDF files containing Purchase Orders (POs).
It extracts POs based on store codes, checks for missing or extra POs,
and merges them into a final PDF in the specified order.

CLI only, no GUI.
"""

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import re
import os
from tqdm import tqdm


# ===== CONFIG =====
input_pdfs = ["PO/PO-BatchDetailsReport.pdf", "PO/PO-BatchDetailsReport1.pdf",
              "PO/PO-BatchDetailsReport2.pdf"]  # Các file gốc
store_list_file = "ListMCH.csv"  # Danh sách mã cửa hàng chuẩn (mỗi dòng 1 mã)
output_file = "PO/PO_FINAL.pdf"
pattern = r"SG\d{4}"

# ===== LOAD STORE LIST =====
with open(store_list_file, "r", encoding="utf-8") as f:
    store_order = [line.strip() for line in f if line.strip()]

# ===== HÀM TÁCH PO =====


def split_pos_from_pdfs(pdf_files):
    """Trả về dict {ma_cua_hang: [list_page_objects]}"""
    store_pages = {}
    current_store = None

    for pdf_file in pdf_files:
        reader = PdfReader(pdf_file)
        with pdfplumber.open(pdf_file) as plumber_pdf:
            for i in tqdm(range(len(reader.pages)), desc=f"Đang xử lý {pdf_file}"):
                page_text = plumber_pdf.pages[i].extract_text() or ""
                match = re.search(pattern, page_text)

                if match:  # Nếu thấy mã mới => PO mới
                    current_store = match.group(0)
                    if current_store not in store_pages:
                        store_pages[current_store] = []
                if current_store:  # Gán page này cho PO hiện tại
                    store_pages[current_store].append(reader.pages[i])

    return store_pages


# ===== XỬ LÝ =====
print("Tách PO từ các file PDF...")
store_pages_map = split_pos_from_pdfs(input_pdfs)

# ===== CẢNH BÁO THIẾU / DƯ =====
found_codes = set(store_pages_map.keys())
expected_codes = set(store_order)

missing = expected_codes - found_codes
extra = found_codes - expected_codes

if missing:
    print(f"[CẢNH BÁO] Thiếu PO cho mã: {', '.join(missing)}")
if extra:
    print(f"[CẢNH BÁO] Có mã không có trong danh sách: {', '.join(extra)}")

# ===== SẮP XẾP & MERGE =====
print("Sắp xếp và gộp PDF...")
final_writer = PdfWriter()
for code in store_order:
    if code in store_pages_map:
        for page in store_pages_map[code]:
            final_writer.add_page(page)

with open(output_file, "wb") as f_out:
    final_writer.write(f_out)

print(f"Hoàn tất! File gộp: {output_file}")
