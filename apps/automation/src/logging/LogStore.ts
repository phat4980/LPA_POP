import { openDatabase, type SqliteDatabase } from "../persistence/db.js";

export type LogLevel = "INFO" | "WARNING" | "ERROR";
export type LogEntry = { id?: number; automationJobId: string; ts: string; level: LogLevel; message: string };

export class LogStore {
  private readonly database: SqliteDatabase;
  private readonly retentionDays: number;
  private cleanupTimer: NodeJS.Timeout;

  constructor(database: SqliteDatabase | string = "../../storage/db/automation.sqlite", retentionDays = 3) {
    this.database = typeof database === "string" ? openDatabase(database) : database;
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
