import assert from "node:assert/strict";
import test from "node:test";
import {
  AutomationJobStatus,
  createAutomationJob,
  transitionAutomationJob,
} from "./AutomationJob.js";
import { InMemoryAutomationJobRepository } from "./InMemoryAutomationJobRepository.js";

const createdAt = new Date("2026-08-23T08:00:00.000Z");

function newJob(id: string = "automation-job-1") {
  return createAutomationJob({ automationJobId: id, deliveryDate: "2026-08-24" }, createdAt);
}

test("creates a queued job with default values", () => {
  const job = newJob();

  assert.deepEqual(job, {
    automationJobId: "automation-job-1",
    deliveryDate: "2026-08-24",
    status: AutomationJobStatus.QUEUED,
    currentStep: "QUEUED",
    progress: 0,
    downloadedCount: 0,
    totalCount: null,
    pythonJobId: null,
    sourceFiles: [],
    finalFile: null,
    error: null,
    createdAt: "2026-08-23T08:00:00.000Z",
    startedAt: null,
    completedAt: null,
  });
});

test("allows every valid lifecycle transition", () => {
  const startedAt = new Date("2026-08-23T08:01:00.000Z");
  const job = newJob();
  const loggingIn = transitionAutomationJob(job, AutomationJobStatus.LOGGING_IN, { now: startedAt });
  const downloading = transitionAutomationJob(loggingIn, AutomationJobStatus.DOWNLOADING);
  const processing = transitionAutomationJob(downloading, AutomationJobStatus.PROCESSING);
  const finalReady = transitionAutomationJob(processing, AutomationJobStatus.FINAL_READY);
  const printing = transitionAutomationJob(finalReady, AutomationJobStatus.PRINTING);
  const completed = transitionAutomationJob(printing, AutomationJobStatus.COMPLETED, {
    now: new Date("2026-08-23T08:02:00.000Z"),
  });

  assert.equal(loggingIn.currentStep, "LOGIN");
  assert.equal(loggingIn.startedAt, "2026-08-23T08:01:00.000Z");
  assert.equal(downloading.currentStep, "DOWNLOAD");
  assert.equal(processing.currentStep, "PROCESS");
  assert.equal(finalReady.currentStep, "FINALIZE");
  assert.equal(printing.currentStep, "PRINT");
  assert.equal(completed.status, AutomationJobStatus.COMPLETED);
  assert.equal(completed.progress, 100);
  assert.equal(completed.completedAt, "2026-08-23T08:02:00.000Z");
});

test("allows valid failure transitions", () => {
  const loggingIn = transitionAutomationJob(newJob(), AutomationJobStatus.LOGGING_IN);
  const failed = transitionAutomationJob(loggingIn, AutomationJobStatus.FAILED, {
    error: "Login failed.",
    now: new Date("2026-08-23T08:03:00.000Z"),
  });
  const downloading = transitionAutomationJob(loggingIn, AutomationJobStatus.DOWNLOADING);
  const downloadFailed = transitionAutomationJob(downloading, AutomationJobStatus.FAILED, {
    error: "Download failed.",
  });
  const processing = transitionAutomationJob(downloading, AutomationJobStatus.PROCESSING);
  const processingFailed = transitionAutomationJob(processing, AutomationJobStatus.FAILED, {
    error: "Processing failed.",
  });
  const finalReady = transitionAutomationJob(processing, AutomationJobStatus.FINAL_READY);
  const printing = transitionAutomationJob(finalReady, AutomationJobStatus.PRINTING);
  const printFailed = transitionAutomationJob(printing, AutomationJobStatus.PRINT_FAILED, {
    error: "Printer unavailable.",
  });

  assert.equal(failed.error, "Login failed.");
  assert.equal(downloadFailed.error, "Download failed.");
  assert.equal(processingFailed.error, "Processing failed.");
  assert.equal(printFailed.status, AutomationJobStatus.PRINT_FAILED);
  assert.equal(printFailed.error, "Printer unavailable.");
});

test("rejects invalid lifecycle transitions", () => {
  assert.throws(
    () => transitionAutomationJob(newJob(), AutomationJobStatus.COMPLETED),
    /Invalid automation job transition: QUEUED -> COMPLETED/,
  );
  assert.throws(
    () => transitionAutomationJob(newJob(), AutomationJobStatus.PRINTING),
    /Invalid automation job transition: QUEUED -> PRINTING/,
  );

  const completed = transitionAutomationJob(
    transitionAutomationJob(
      transitionAutomationJob(
        transitionAutomationJob(
          transitionAutomationJob(
            transitionAutomationJob(newJob(), AutomationJobStatus.LOGGING_IN),
            AutomationJobStatus.DOWNLOADING,
          ),
          AutomationJobStatus.PROCESSING,
        ),
        AutomationJobStatus.FINAL_READY,
      ),
      AutomationJobStatus.PRINTING,
    ),
    AutomationJobStatus.COMPLETED,
  );
  assert.throws(
    () => transitionAutomationJob(completed, AutomationJobStatus.PROCESSING),
    /Invalid automation job transition: COMPLETED -> PROCESSING/,
  );

  const failed = transitionAutomationJob(
    transitionAutomationJob(newJob(), AutomationJobStatus.LOGGING_IN),
    AutomationJobStatus.FAILED,
  );
  assert.throws(
    () => transitionAutomationJob(failed, AutomationJobStatus.COMPLETED),
    /Invalid automation job transition: FAILED -> COMPLETED/,
  );
});

test("stores, retrieves, and updates a job", () => {
  const repository = new InMemoryAutomationJobRepository();
  const created = repository.create(newJob());
  assert.equal(repository.getById(created.automationJobId)?.status, AutomationJobStatus.QUEUED);

  const loggingIn = transitionAutomationJob(created, AutomationJobStatus.LOGGING_IN);
  const updated = repository.update(loggingIn);

  assert.equal(updated.status, AutomationJobStatus.LOGGING_IN);
  assert.equal(repository.getById(created.automationJobId)?.currentStep, "LOGIN");
});

test("returns undefined for a missing job", () => {
  const repository = new InMemoryAutomationJobRepository();

  assert.equal(repository.getById("missing-job"), undefined);
  assert.throws(() => repository.update(newJob("missing-job")), /Automation job was not found/);
});

test("rejects duplicate automation job IDs", () => {
  const repository = new InMemoryAutomationJobRepository();
  repository.create(newJob());

  assert.throws(() => repository.create(newJob()), /Automation job already exists/);
});
