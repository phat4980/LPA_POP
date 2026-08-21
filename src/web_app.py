"""
PO Management Tool — local web API + UI (Approach C).

Bind 127.0.0.1 only. Same merge pipeline as the desktop app (core.py).
"""

from __future__ import annotations

import asyncio
import json
import queue
import webbrowser
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (
    APP_NAME, APP_VERSION, DEFAULT_PATTERN,
    WEB_HOST, WEB_PORT, resource_path, AppSettings,
)
from jobs import manager, staff_directory

WEB_DIR = Path(resource_path("web"))

app = FastAPI(title=APP_NAME, version=APP_VERSION)
if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


class PathJobRequest(BaseModel):
    pdf_paths: Optional[List[str]] = None
    pdf_folder: Optional[str] = None
    list_file: str
    output: str
    pattern: Optional[str] = None


class SettingsUpdate(BaseModel):
    last_list_file: Optional[str] = None
    last_output_dir: Optional[str] = None
    default_pdf_folder: Optional[str] = None
    last_input_paths: Optional[List[str]] = None
    custom_pattern: Optional[str] = Field(default=None)
    theme_mode: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def index():
    page = WEB_DIR / "index.html"
    if not page.exists():
        raise HTTPException(500, "Thiếu web/index.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"ok": True, "name": APP_NAME, "version": APP_VERSION}


@app.get("/api/settings")
def get_settings():
    s = AppSettings.load()
    today = __import__("datetime").datetime.now().strftime("%d%m%Y")
    default_out = ""
    if s.last_output_dir:
        default_out = str(Path(s.last_output_dir) / f"PO_{today}.pdf")
    else:
        default_out = str(Path.home() / "Desktop" / f"PO_{today}.pdf")
    return {
        "last_list_file": s.last_list_file,
        "last_output_dir": s.last_output_dir,
        "default_pdf_folder": s.default_pdf_folder,
        "last_input_paths": s.last_input_paths,
        "custom_pattern": s.custom_pattern or DEFAULT_PATTERN,
        "theme_mode": s.theme_mode,
        "suggested_output": default_out,
        "version": APP_VERSION,
    }


@app.put("/api/settings")
def put_settings(body: SettingsUpdate):
    s = AppSettings.load()
    if body.last_list_file is not None:
        s.last_list_file = body.last_list_file
    if body.last_output_dir is not None:
        s.last_output_dir = body.last_output_dir
    if body.default_pdf_folder is not None:
        s.default_pdf_folder = body.default_pdf_folder
    if body.last_input_paths is not None:
        s.last_input_paths = body.last_input_paths
    if body.custom_pattern is not None:
        s.custom_pattern = body.custom_pattern or DEFAULT_PATTERN
    if body.theme_mode is not None:
        s.theme_mode = body.theme_mode
    s.save()
    return get_settings()


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": manager.list_jobs()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    return job.to_public()


@app.post("/api/jobs")
def create_path_job(body: PathJobRequest):
    """Automation-friendly: local filesystem paths, no file upload."""
    try:
        job = manager.create_path_job(
            pdf_paths=body.pdf_paths,
            pdf_folder=body.pdf_folder,
            list_file=body.list_file,
            output=body.output,
            pattern=body.pattern,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return job.to_public()


@app.post("/api/jobs/upload")
async def create_upload_job(
    pdfs: List[UploadFile] = File(...),
    list_file: UploadFile = File(...),
    output: Optional[str] = Form(None),
    pattern: Optional[str] = Form(None),
):
    pdf_payload = []
    for f in pdfs:
        data = await f.read()
        pdf_payload.append((f.filename or "input.pdf", data))
    list_bytes = await list_file.read()
    try:
        job = manager.create_upload_job(
            pdf_files=pdf_payload,
            list_filename=list_file.filename or "stores.csv",
            list_bytes=list_bytes,
            output=output,
            pattern=pattern,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return job.to_public()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    q = manager.subscribe(job_id)
    if q is None:
        raise HTTPException(404, "Job không tồn tại")

    async def gen():
        try:
            while True:
                def _pull():
                    try:
                        return q.get(timeout=1.0)
                    except queue.Empty:
                        return None

                msg = await asyncio.to_thread(_pull)
                if msg is None:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("type") in ("done", "error"):
                    break
        finally:
            manager.unsubscribe(job_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/pdf")
def download_pdf(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    if job.status != "done" or not job.output_path:
        raise HTTPException(400, "PDF chưa sẵn sàng")
    path = Path(job.output_path)
    if not path.exists():
        raise HTTPException(404, "Không tìm thấy file PDF trên đĩa")
    return FileResponse(path, filename=path.name, media_type="application/pdf")


@app.get("/api/staff")
def get_staff(list_file: Optional[str] = None):
    path = list_file or AppSettings.load().last_list_file
    if not path:
        raise HTTPException(400, "Chưa có file danh sách mã")
    try:
        return staff_directory(path)
    except FileNotFoundError:
        raise HTTPException(404, f"Không tìm thấy: {path}")


def launch_web(open_browser: bool = True, host: str = WEB_HOST, port: int = WEB_PORT) -> None:
    import uvicorn

    url = f"http://{host}:{port}"
    print(f"{APP_NAME} v{APP_VERSION} — Web UI: {url}")
    if open_browser:
        threading_open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")


def threading_open(url: str) -> None:
    import threading

    def _open():
        import time
        time.sleep(0.8)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    launch_web()
