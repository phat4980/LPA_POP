# PO Merge Tool GUI

Công cụ hợp nhất các file PO PDF theo danh sách mã cửa hàng, hỗ trợ giao diện đồ họa (GUI) và dòng lệnh (CLI).

---

## 1. Yêu cầu hệ thống

- Python 3.8 trở lên
- Windows (khuyến nghị)
- Các thư viện: PyPDF2, pdfplumber, pillow

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
- `--output`: Đường dẫn file PDF kết quả
- `--pattern`: Regex để nhận diện mã PO (mặc định: SGxxxx)

---

## 4. Build file EXE (Windows)

### a. Cài đặt PyInstaller

```sh
pip install pyinstaller (nếu đã có trong venv thì bỏ qua)
```

### b. Build EXE

```sh
pyinstaller --onefile --windowed po_merge_tool_gui.py
```

- File EXE sẽ nằm trong thư mục `dist`
- Nếu muốn icon riêng: thêm `--icon=icon.ico`

### c. Chạy file EXE

```sh
dist\po_merge_tool_gui.exe
```

---

## 5. Lưu ý

- File log sẽ được ghi tại `po_merge_tool.log`
- Đảm bảo các file PDF và danh sách mã cửa hàng đã đúng định dạng
- Nếu gặp lỗi về Tkinter, hãy kiểm tra lại cài đặt Python hoặc dùng CLI

---

## 6. Liên hệ & hỗ trợ

Liên hệ IT hoặc người phát triển nếu cần hỗ trợ