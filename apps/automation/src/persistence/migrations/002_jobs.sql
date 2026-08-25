CREATE TABLE IF NOT EXISTS jobs (
    automation_job_id TEXT PRIMARY KEY,
    delivery_date TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step TEXT NOT NULL,
    progress REAL NOT NULL,
    downloaded_count INTEGER NOT NULL,
    total_count INTEGER,
    python_job_id TEXT,
    source_files TEXT NOT NULL,
    final_file TEXT,
    auto_print INTEGER NOT NULL,
    print_options TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);