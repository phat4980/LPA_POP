import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createRequire } from "node:module";

export type LogLevel = "INFO" | "WARNING" | "ERROR";
export type LogEntry = { id?: number; automationJobId: string; ts: string; level: LogLevel; message: string };

type SqliteDatabase = { exec(sql: string): void; prepare(sql: string): { run(...params: unknown[]): void; all(...params: unknown[]): unknown[] }; close(): void };

export class LogStore {
  private readonly database: SqliteDatabase;
  private readonly retentionDays: number;
  private cleanupTimer: NodeJS.Timeout;

  constructor(databasePath = "automation.sqlite", retentionDays = 3) {
    const DatabaseSync = (createRequire(import.meta.url)("node:sqlite") as { DatabaseSync: new (path: string) => SqliteDatabase }).DatabaseSync;
    const path = resolve(databasePath);
    mkdirSync(dirname(path), { recursive: true });
    this.database = new DatabaseSync(path);
    this.database.exec("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, automation_job_id TEXT NOT NULL, ts TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL)");
    this.database.exec("CREATE INDEX IF NOT EXISTS idx_logs_job_ts ON logs (automation_job_id, ts)");
    this.retentionDays = retentionDays;
    this.cleanup();
    this.cleanupTimer = setInterval(() => this.cleanup(), 24 * 60 * 60 * 1000);
    this.cleanupTimer.unref();
  }

  append(entry: LogEntry): void {
    this.database.prepare("INSERT INTO logs (automation_job_id, ts, level, message) VALUES (?, ?, ?, ?)").run(entry.automationJobId, entry.ts, entry.level, entry.message);
  }

  list(automationJobId: string): LogEntry[] {
    return this.database.prepare("SELECT id, automation_job_id as automationJobId, ts, level, message FROM logs WHERE automation_job_id = ? ORDER BY id").all(automationJobId) as LogEntry[];
  }

  cleanup(): void {
    const cutoff = new Date(Date.now() - this.retentionDays * 24 * 60 * 60 * 1000).toISOString();
    this.database.prepare("DELETE FROM logs WHERE ts < ?").run(cutoff);
  }

  close(): void { clearInterval(this.cleanupTimer); this.database.close(); }
}
