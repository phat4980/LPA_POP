# PO Merge Tool GUI

Công cụ hợp nhất các file PO PDF theo danh sách mã cửa hàng, hỗ trợ giao diện đồ họa (GUI) và dòng lệnh (CLI).

---

## 1. Yêu cầu hệ thống

- Python 3.8 trở lên
- Windows (khuyến nghị)
- Các thư viện: PyPDF2, pdfplumber, pillow, PyMuPDF (fitz)

---

## 2. Cài đặt môi trường

### a. Tạo môi trường ảo (khuyến nghị)

```sh
python -m venv .venv
.venv\Scripts\activate
```

### b. Cài đặt các thư viện cần thiết

```sh
pip install -r requirements.txt
```

---

## 3. Sử dụng script

### a. Chạy bằng giao diện đồ họa (GUI)

```sh
python po_merge_tool_gui.py --gui
```

### b. Chạy bằng dòng lệnh (CLI)

```sh
python po_merge_tool_gui.py --input-folder ./pdfs --list-file stores.csv --output PO_FINAL.pdf
```

**Tham số:**
- `--input-folder`: Thư mục chứa các file PDF cần hợp nhất
- `--input-files`: Danh sách file PDF hoặc thư mục (có thể truyền nhiều)
- `--list-file`: File danh sách mã cửa hàng (CSV hoặc TXT)
  - CSV có thể 1 cột (mỗi dòng 1 mã) hoặc 2 cột (cột 1: mã, cột 2: tên cửa hàng). Nếu có tên, log thiếu mã theo từng mã sẽ kèm tên.
- `--output`: Đường dẫn file PDF kết quả
- `--pattern`: Regex để nhận diện mã PO (mặc định: `SG\d{4}`)

Gợi ý: có thể truyền nhiều file theo `--input-files` hoặc chỉ định 1 thư mục qua `--input-folder`.

---

## 4. Build file EXE (Windows)

### a. Cài đặt PyInstaller

```sh
pip install pyinstaller  # nếu đã có trong venv thì bỏ qua
```

### b. Build EXE

```sh
pyinstaller --onefile --windowed po_merge_tool_gui.py
```

- File EXE sẽ nằm trong thư mục `dist`
- Nếu muốn icon riêng: thêm `--icon=assets/app.ico`

### c. Chạy file EXE

```sh
dist\po_merge_tool_gui.exe
```

---

## 5. Lưu ý

- File log sẽ được ghi tại `po_merge_tool.log`.
- Danh sách mã (`--list-file`) có thể là TXT (mỗi dòng 1 mã) hoặc CSV (1 hoặc 2 cột). Khi CSV có 2 cột, log thiếu mã theo từng mã sẽ hiển thị "mã - tên".
- Khi hợp nhất xong, công cụ sẽ: (1) cảnh báo "thiếu" và "dư" mã, (2) cộng tổng số lượng sau chia 2 và log theo định dạng: `Tổng số lượng ngày DD/MM/YYYY: <tổng>`.
- Công cụ thêm số lượng (đã chia 2) vào góc phải dưới của từng trang bằng font hệ thống `helv`.
- Nếu gặp lỗi về Tkinter, hãy kiểm tra lại cài đặt Python hoặc dùng CLI.

---

## 6. Liên hệ & hỗ trợ

Liên hệ IT hoặc người phát triển nếu cần hỗ trợ