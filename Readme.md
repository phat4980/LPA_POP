# PO Management Tool

Công cụ hợp nhất các file PO PDF theo danh sách mã cửa hàng. Có **Web UI + REST API** (mặc định), GUI desktop, và CLI.

---

## 1. Yêu cầu hệ thống

- Python 3.10 trở lên (khuyến nghị)
- Windows
- Thư viện: xem `requirements.txt` (PyPDF2, pdfplumber, PyMuPDF, FastAPI, CustomTkinter, …)

---

## 2. Cài đặt

```sh
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Chạy

### a. Web UI (mặc định) — Approach C

```sh
python src/po_merge_tool_gui.py
python src/web_app.py
```

Mở `http://127.0.0.1:8088` (bind localhost). Web 2 hiện có hai chế độ:

- **Upload**: kéo thả PDF + CSV trên trình duyệt
- **Đường dẫn máy**: trỏ folder/file trên disk — dùng cho automation

Không mở browser:

```sh
python src/po_merge_tool_gui.py --web --no-browser
```

### b. Desktop GUI (CustomTkinter)

```sh
python src/po_merge_tool_gui.py --gui
```

### c. CLI

```sh
python src/po_merge_tool_gui.py --input-folder ./pdfs --list-file stores.csv --output PO_FINAL.pdf
```

---

## 4. API (automation)

Server chỉ lắng nghe `127.0.0.1:8088`.

Tạo job bằng path trên máy (không upload):

```sh
curl -X POST http://127.0.0.1:8088/api/jobs -H "Content-Type: application/json" -d "{\"pdf_folder\":\"D:/PO/inbox\",\"list_file\":\"D:/PO/MCH.csv\",\"output\":\"D:/PO/out/PO.pdf\"}"
```

| Method | Path | Mô tả |
|--------|------|--------|
| POST | `/api/jobs` | Job path mode (JSON) |
| POST | `/api/jobs/upload` | Job upload PDF + CSV |
| GET | `/api/jobs/{id}` | Trạng thái + summary |
| GET | `/api/jobs/{id}/events` | SSE progress |
| GET | `/api/jobs/{id}/pdf` | Tải PDF kết quả |
| GET/PUT | `/api/settings` | Default list / folder / output / regex |
| GET | `/api/staff` | Tra cứu staff từ CSV |

---

## 5. Build EXE (desktop)

```sh
compile\build.bat
```

EXE hiện tại vẫn là GUI Tk. Web EXE (bundle uvicorn) làm bước sau.

---

## 6. Lưu ý

- Log file: `po_merge_tool.log`. Settings: `%APPDATA%\LPA_POP\settings.json`.
- CSV 1–3 cột: mã, tên cửa hàng, staff.
- Merge xong: cảnh báo mã thiếu/dư, ghi qty (đã chia 2) lên từng trang.

---

## 1. Yêu cầu hệ thống

- Python 3.8 trở lên
- Windows
- Các thư viện: PyPDF2, pdfplumber, pillow, PyMuPDF (fitz)

---

## 2. Cài đặt môi trường

### a. Tạo môi trường ảo

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

### a. Sử dụng file build.bat

```sh
compile\build.bat
```

File build.bat sẽ tự động:

- Cài đặt PyInstaller nếu chưa có
- Xóa build cũ
- Build EXE với icon và font
- Refresh Windows icon cache
- Tạo file EXE trong thư mục `dist`

### b. Build thủ công (nếu cần tùy chỉnh)

```sh
pyinstaller --onefile --windowed --name "PO Management Tool" --icon "assets/icon/app.ico" src/po_merge_tool_gui.py --add-data "assets/font/Roboto-ExtraBold.ttf;font" --add-data "assets/icon;icon" --clean
```

### c. Chạy file EXE

```sh
dist\PO Management Tool.exe
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
