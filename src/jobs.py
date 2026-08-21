"""
Background merge jobs for the web API and future automation.

Runs the same core.py pipeline as the desktop GUI, with step/progress/log callbacks.
"""

from __future__ import annotations

import datetime
import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import DEFAULT_PATTERN, JOBS_DIR, AppSettings
from core import (
    collect_input_pdfs,
    extract_store_pages,
    merge_and_write,
    read_code_name_map,
    read_code_staff_map,
    read_store_list,
    setup_logging,
)

STEPS = ["read", "extract", "merge", "done"]


def _now() -> str:
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    step: str = "read"
    progress: float = 0.0
    logs: List[Dict[str, str]] = field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    output_path: str = ""
    created_at: str = field(default_factory=_now)
    pdf_count: int = 0
    list_file: str = ""
    subscribers: List[queue.Queue] = field(default_factory=list)

    def to_public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "step": self.step,
            "progress": round(self.progress, 4),
            "logs": self.logs[-200:],
            "summary": self.summary,
            "error": self.error,
            "output_path": self.output_path,
            "created_at": self.created_at,
            "pdf_count": self.pdf_count,
            "list_file": self.list_file,
        }


class JobLogHandler(logging.Handler):
    def __init__(self, emit_fn: Callable[[str, str], None]):
        super().__init__()
        self.emit_fn = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.emit_fn(self.format(record), record.levelname)
        except Exception:
            pass


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.to_public() for j in jobs[:30]]

    def subscribe(self, job_id: str) -> Optional[queue.Queue]:
        job = self.get(job_id)
        if not job:
            return None
        q: queue.Queue = queue.Queue()
        with self._lock:
            job.subscribers.append(q)
        q.put({"type": "snapshot", "job": job.to_public()})
        return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        job = self.get(job_id)
        if not job:
            return
        with self._lock:
            if q in job.subscribers:
                job.subscribers.remove(q)

    def _broadcast(self, job: Job, payload: Dict[str, Any]) -> None:
        for q in list(job.subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

    def _log(self, job: Job, message: str, level: str = "INFO") -> None:
        entry = {"time": _now(), "level": level, "message": message}
        with self._lock:
            job.logs.append(entry)
        self._broadcast(job, {"type": "log", "entry": entry, "job": job.to_public()})

    def _set_progress(self, job: Job, step: str, progress: float) -> None:
        with self._lock:
            job.step = step
            job.progress = min(max(progress, 0.0), 1.0)
        self._broadcast(job, {"type": "progress", "job": job.to_public()})

    def create_path_job(
        self,
        pdf_paths: Optional[List[str]],
        pdf_folder: Optional[str],
        list_file: str,
        output: str,
        pattern: Optional[str] = None,
    ) -> Job:
        pdfs = collect_input_pdfs(pdf_paths, pdf_folder)
        if not pdfs:
            raise ValueError("Không tìm thấy file PDF. Kiểm tra pdf_paths / pdf_folder.")
        if not list_file or not Path(list_file).exists():
            raise ValueError("list_file không tồn tại.")
        if not output:
            raise ValueError("Thiếu đường dẫn output.")

        job = Job(
            id=uuid.uuid4().hex[:12],
            output_path=str(Path(output)),
            pdf_count=len(pdfs),
            list_file=str(Path(list_file)),
        )
        with self._lock:
            self._jobs[job.id] = job
        settings = AppSettings.load()
        settings.last_input_paths = [str(p) for p in pdfs]
        settings.last_list_file = str(Path(list_file))
        settings.last_output_dir = str(Path(output).parent)
        if pdf_folder:
            settings.default_pdf_folder = pdf_folder
        settings.save()

        thread = threading.Thread(
            target=self._run_job,
            args=(job, pdfs, Path(list_file), Path(output), pattern or settings.custom_pattern or DEFAULT_PATTERN),
            daemon=True,
        )
        thread.start()
        return job

    def create_upload_job(
        self,
        pdf_files: List[tuple],
        list_filename: str,
        list_bytes: bytes,
        output: Optional[str],
        pattern: Optional[str] = None,
    ) -> Job:
        if not pdf_files:
            raise ValueError("Cần ít nhất một file PDF.")
        if not list_bytes:
            raise ValueError("Cần file danh sách mã cửa hàng.")

        job_id = uuid.uuid4().hex[:12]
        work = Path(JOBS_DIR) / job_id
        work.mkdir(parents=True, exist_ok=True)
        pdf_dir = work / "pdfs"
        pdf_dir.mkdir(exist_ok=True)

        saved: List[Path] = []
        for name, data in pdf_files:
            safe = Path(name).name or "input.pdf"
            dest = pdf_dir / safe
            dest.write_bytes(data)
            saved.append(dest)

        list_path = work / (Path(list_filename).name or "stores.csv")
        list_path.write_bytes(list_bytes)

        settings = AppSettings.load()
        if output:
            out_path = Path(output)
        elif settings.last_output_dir:
            today = datetime.datetime.now().strftime("%d%m%Y")
            out_path = Path(settings.last_output_dir) / f"PO_{today}.pdf"
        else:
            out_path = work / "PO_output.pdf"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        job = Job(
            id=job_id,
            output_path=str(out_path),
            pdf_count=len(saved),
            list_file=str(list_path),
        )
        with self._lock:
            self._jobs[job.id] = job

        settings.last_output_dir = str(out_path.parent)
        settings.save()

        thread = threading.Thread(
            target=self._run_job,
            args=(job, saved, list_path, out_path, pattern or settings.custom_pattern or DEFAULT_PATTERN),
            daemon=True,
        )
        thread.start()
        return job

    def _run_job(
        self,
        job: Job,
        pdf_paths: List[Path],
        list_path: Path,
        out_path: Path,
        pattern: str,
    ) -> None:
        log = setup_logging()
        handler = JobLogHandler(lambda msg, level: self._log(job, msg, level))
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)

        with self._run_lock:
            try:
                with self._lock:
                    job.status = "running"
                self._set_progress(job, "read", 0.02)
                self._log(job, f"Bắt đầu xử lý {len(pdf_paths)} file PDF...", "INFO")

                store_order = read_store_list(list_path)
                self._log(job, f"Đã tải danh sách cửa hàng: {len(store_order)} mã", "INFO")

                try:
                    code_name_map = read_code_name_map(list_path)
                except Exception:
                    code_name_map = {}
                try:
                    code_staff_map = read_code_staff_map(list_path)
                except Exception:
                    code_staff_map = {}

                self._set_progress(job, "extract", 0.05)

                def extract_progress(done, total):
                    pct = (done / total) * 0.7 if total else 0
                    self._set_progress(job, "extract", pct)

                result = extract_store_pages(pdf_paths, pattern, extract_progress, logger=log)
                found_codes = set(result.store_pages.keys())
                expected_codes = set(c.upper() for c in store_order)
                missing = sorted(list(expected_codes - found_codes))
                extra = sorted(list(found_codes - expected_codes))

                if missing:
                    self._log(job, f"Thiếu PO cho {len(missing)} mã: {', '.join(missing[:15])}", "WARNING")
                if extra:
                    self._log(job, f"Dư {len(extra)} mã không có trong danh sách: {', '.join(extra[:15])}", "WARNING")

                self._set_progress(job, "merge", 0.72)

                def merge_progress(done, total):
                    pct = 0.7 + ((done / total) * 0.28 if total else 0)
                    self._set_progress(job, "merge", min(pct, 0.98))

                annot = merge_and_write(
                    result.store_pages,
                    store_order,
                    out_path,
                    logger=log,
                    progress_cb=merge_progress,
                    code_to_name=code_name_map,
                    code_staff_map=code_staff_map,
                )

                summary = {
                    "timestamp": _now(),
                    "total_pdfs": len(pdf_paths),
                    "total_pages": result.total_pages,
                    "total_qty": annot.total_qty,
                    "total_codes_expected": len(store_order),
                    "total_codes_found": len(found_codes),
                    "missing_codes": missing,
                    "extra_codes": extra,
                    "staff_totals": annot.staff_totals,
                    "staff_store_map": annot.staff_store_map,
                    "store_qty_map": annot.store_qty_map,
                    "code_name_map": code_name_map,
                    "code_staff_map": code_staff_map,
                    "output_path": str(out_path),
                }
                with self._lock:
                    job.summary = summary
                    job.status = "done"
                    job.output_path = str(out_path)
                self._set_progress(job, "done", 1.0)
                self._log(job, f"Hoàn tất xuất file: {out_path}", "INFO")
                self._broadcast(job, {"type": "done", "job": job.to_public()})
            except Exception as e:
                log.exception("Job failed: %s", e)
                with self._lock:
                    job.status = "error"
                    job.error = str(e)
                self._log(job, f"Lỗi: {e}", "ERROR")
                self._broadcast(job, {"type": "error", "job": job.to_public()})
            finally:
                log.removeHandler(handler)


manager = JobManager()


def staff_directory(list_file: str) -> Dict[str, Any]:
    path = Path(list_file)
    if not path.exists():
        raise FileNotFoundError(list_file)
    try:
        code_name = read_code_name_map(path)
    except Exception:
        code_name = {}
    try:
        code_staff = read_code_staff_map(path)
    except Exception:
        code_staff = {}
    if not code_name and not code_staff:
        codes = read_store_list(path)
        code_name = {c: "" for c in codes}

    rows = []
    for code, name in sorted(code_name.items()):
        rows.append({
            "code": code,
            "name": name,
            "staff": code_staff.get(code, "Chưa phân công"),
        })
    for code, staff in code_staff.items():
        if code not in code_name:
            rows.append({"code": code, "name": "", "staff": staff})
    return {"count": len(rows), "rows": rows}
