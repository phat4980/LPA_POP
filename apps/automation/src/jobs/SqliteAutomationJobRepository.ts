import type { SqliteDatabase } from "../persistence/db.js";
import type { AutomationJob, AutomationJobStatus, AutomationSourceFile, AutomationFinalFile } from "./AutomationJob.js";
import type { AutomationJobRepository } from "./AutomationJobRepository.js";
import type { AutomationJobEvent } from "./AutomationJobEvent.js";
import { AutomationJobStatus as Status } from "./AutomationJob.js";

export type PersistenceErrorSink = (jobId: string, step: string, error: unknown) => void;

type JobRow = {
  automation_job_id: string; delivery_date: string; status: string; current_step: string;
  progress: number; downloaded_count: number; total_count: number | null;
  python_job_id: string | null; source_files: string; final_file: string | null;
  auto_print: number; print_options: string | null; error: string | null;
  created_at: string; started_at: string | null; completed_at: string | null;
};

export class SqliteAutomationJobRepository implements AutomationJobRepository {
  private readonly events = new Map<string, AutomationJobEvent[]>();

  constructor(private readonly database: SqliteDatabase, private readonly onPersistenceError?: PersistenceErrorSink) {}

  create(job: AutomationJob): AutomationJob {
    try {
      this.database.prepare(`INSERT INTO jobs (
        automation_job_id, delivery_date, status, current_step, progress,
        downloaded_count, total_count, python_job_id, source_files, final_file,
        auto_print, print_options, error, created_at, started_at, completed_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
        .run(...jobParams(job));
    } catch (error) { this.report(job, "create", error); }
    this.events.set(job.automationJobId, []);
    return cloneJob(job);
  }

  getById(automationJobId: string): AutomationJob | undefined {
    const row = this.database.prepare("SELECT * FROM jobs WHERE automation_job_id = ?").get(automationJobId) as JobRow | undefined;
    return row ? fromRow(row) : undefined;
  }

  update(job: AutomationJob): AutomationJob {
    try {
      this.database.prepare(`UPDATE jobs SET
        delivery_date = ?, status = ?, current_step = ?, progress = ?,
        downloaded_count = ?, total_count = ?, python_job_id = ?, source_files = ?,
        final_file = ?, auto_print = ?, print_options = ?, error = ?,
        created_at = ?, started_at = ?, completed_at = ?
        WHERE automation_job_id = ?`).run(...jobParams(job).slice(1), job.automationJobId);
    } catch (error) { this.report(job, job.currentStep, error); }
    return cloneJob(job);
  }

  addEvent(event: AutomationJobEvent): AutomationJobEvent {
    if (!this.getById(event.automationJobId)) throw new Error(`Automation job was not found: ${event.automationJobId}.`);
    const events = this.events.get(event.automationJobId) ?? [];
    events.push({ ...event }); this.events.set(event.automationJobId, events);
    return { ...event };
  }

  listEvents(automationJobId: string): AutomationJobEvent[] | undefined {
    if (!this.getById(automationJobId)) return undefined;
    return (this.events.get(automationJobId) ?? []).map((event) => ({ ...event }));
  }

  recoverInterruptedJobs(now = new Date()): AutomationJob[] {
    const rows = this.database.prepare("SELECT * FROM jobs WHERE status NOT IN (?, ?, ?, ?)").all(
      Status.FINAL_READY, Status.COMPLETED, Status.FAILED, Status.PRINT_FAILED,
    ) as JobRow[];
    return rows.map((row) => {
      this.database.prepare("UPDATE jobs SET status = ?, current_step = ?, error = ?, completed_at = ? WHERE automation_job_id = ?")
        .run(Status.FAILED, "FAILED", "Service restarted mid-job", now.toISOString(), row.automation_job_id);
      return this.getById(row.automation_job_id)!;
    });
  }

  private report(job: AutomationJob, step: string, error: unknown): void { this.onPersistenceError?.(job.automationJobId, step, error); }
}

function jobParams(job: AutomationJob): unknown[] {
  return [job.automationJobId, job.deliveryDate, job.status, job.currentStep, job.progress,
    job.downloadedCount, job.totalCount, job.pythonJobId, JSON.stringify(job.sourceFiles),
    job.finalFile ? JSON.stringify(job.finalFile) : null, job.autoPrint ? 1 : 0,
    job.printOptions ? JSON.stringify(job.printOptions) : null, job.error,
    job.createdAt, job.startedAt, job.completedAt];
}

function fromRow(row: JobRow): AutomationJob {
  return { automationJobId: row.automation_job_id, deliveryDate: row.delivery_date,
    status: row.status as AutomationJobStatus, currentStep: row.current_step as AutomationJob["currentStep"],
    progress: row.progress, downloadedCount: row.downloaded_count, totalCount: row.total_count,
    pythonJobId: row.python_job_id, sourceFiles: JSON.parse(row.source_files) as AutomationSourceFile[],
    finalFile: row.final_file ? JSON.parse(row.final_file) as AutomationFinalFile : null,
    autoPrint: row.auto_print === 1, ...(row.print_options ? { printOptions: JSON.parse(row.print_options) } : {}),
    error: row.error, createdAt: row.created_at, startedAt: row.started_at, completedAt: row.completed_at };
}

function cloneJob(job: AutomationJob): AutomationJob {
  return { ...job, sourceFiles: job.sourceFiles.map((file) => ({ ...file })),
    finalFile: job.finalFile ? { ...job.finalFile } : null,
    ...(job.printOptions ? { printOptions: { ...job.printOptions } } : {}) };
}
