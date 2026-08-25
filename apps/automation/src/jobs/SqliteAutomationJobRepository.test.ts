import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { openDatabase, type SqliteDatabase } from "../persistence/db.js";
import { AutomationJobStatus, createAutomationJob } from "./AutomationJob.js";
import { SqliteAutomationJobRepository } from "./SqliteAutomationJobRepository.js";

async function withDatabase(run: (database: SqliteDatabase, repository: SqliteAutomationJobRepository) => void): Promise<void> {
  const directory = await mkdtemp(join(tmpdir(), "lpa-jobs-"));
  const database = openDatabase(join(directory, "automation.sqlite"));
  const repository = new SqliteAutomationJobRepository(database);
  try { run(database, repository); } finally { database.close(); }
}

test("persists jobs and round-trips JSON fields", async () => withDatabase((database, repository) => {
  const created = createAutomationJob({ automationJobId: "persisted", deliveryDate: "2026-08-25", autoPrint: true, printOptions: { copies: 2, paperSize: "A5" } });
  const stored = repository.create({ ...created, sourceFiles: [{ path: "source.pdf", name: "source.pdf", size: 12 }], finalFile: { path: "final.pdf", name: "final.pdf", size: 24 } });
  const loaded = repository.getById(stored.automationJobId)!;
  assert.deepEqual(loaded.sourceFiles, stored.sourceFiles);
  assert.deepEqual(loaded.finalFile, stored.finalFile);
  assert.deepEqual(loaded.printOptions, stored.printOptions);
  assert.equal((database.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('logs', 'jobs') ORDER BY name").all() as Array<{ name: string }>).map((row) => row.name).join(","), "jobs,logs");
}));

test("writes state updates and recovers only non-terminal jobs", async () => withDatabase((_database, repository) => {
  const running = repository.create(createAutomationJob({ automationJobId: "running", deliveryDate: "2026-08-25" }));
  const terminal = repository.create({ ...createAutomationJob({ automationJobId: "terminal", deliveryDate: "2026-08-25" }), status: AutomationJobStatus.FINAL_READY, currentStep: "FINALIZE", progress: 80 });
  repository.update({ ...running, status: AutomationJobStatus.PROCESSING, currentStep: "PROCESS", progress: 60 });
  assert.equal(repository.getById("running")?.status, AutomationJobStatus.PROCESSING);
  const recovered = repository.recoverInterruptedJobs(new Date("2026-08-25T01:00:00.000Z"));
  assert.equal(recovered.length, 1);
  assert.equal(repository.getById("running")?.status, AutomationJobStatus.FAILED);
  assert.equal(repository.getById("running")?.error, "Service restarted mid-job");
  assert.equal(repository.getById("terminal")?.status, AutomationJobStatus.FINAL_READY);
}));
