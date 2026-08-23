import assert from "node:assert/strict";
import test from "node:test";
import { AutomationJobStatus } from "./AutomationJob.js";
import { AutomationJobService } from "./AutomationJobService.js";
import { FakeAutomationWorkflow } from "./FakeAutomationWorkflow.js";
import { InMemoryAutomationJobRepository } from "./InMemoryAutomationJobRepository.js";

function createService(workflow: FakeAutomationWorkflow = new FakeAutomationWorkflow()) {
  const repository = new InMemoryAutomationJobRepository();
  return { repository, workflow, service: new AutomationJobService(repository, workflow) };
}

function createJob(service: AutomationJobService) {
  return service.createJob({ automationJobId: "automation-job-1", deliveryDate: "2026-08-24" });
}

function eventTypes(repository: InMemoryAutomationJobRepository, jobId: string) {
  return repository.listEvents(jobId)?.map((event) => event.type);
}

test("creates jobs with the Phase 6.1 defaults", () => {
  const { service } = createService();
  const job = createJob(service);

  assert.equal(job.status, AutomationJobStatus.QUEUED);
  assert.equal(job.currentStep, "QUEUED");
  assert.equal(job.progress, 0);
  assert.equal(job.downloadedCount, 0);
  assert.equal(job.totalCount, null);
  assert.equal(job.pythonJobId, null);
  assert.equal(job.finalFile, null);
  assert.equal(job.error, null);
  assert.equal(job.startedAt, null);
  assert.equal(job.completedAt, null);
});

test("runs the full valid lifecycle with workflow-derived job data", async () => {
  const { service, workflow, repository } = createService();
  const created = createJob(service);
  const completed = await service.runJob(created.automationJobId);

  assert.equal(completed.status, AutomationJobStatus.COMPLETED);
  assert.equal(completed.currentStep, "COMPLETED");
  assert.equal(completed.progress, 100);
  assert.ok(completed.startedAt);
  assert.ok(completed.completedAt);
  assert.equal(completed.downloadedCount, 1);
  assert.equal(completed.totalCount, 1);
  assert.equal(completed.sourceFiles.length, 1);
  assert.equal(completed.finalFile?.name, "final.pdf");
  assert.equal(completed.pythonJobId, "python-job-1");
  assert.deepEqual(
    workflow.calls.map((job) => [job.status, job.currentStep, job.progress]),
    [
      [AutomationJobStatus.LOGGING_IN, "LOGIN", 0],
      [AutomationJobStatus.DOWNLOADING, "DOWNLOAD", 20],
      [AutomationJobStatus.PROCESSING, "PROCESS", 60],
      [AutomationJobStatus.PRINTING, "PRINT", 90],
    ],
  );
  assert.deepEqual(eventTypes(repository, created.automationJobId), ["JOB_CREATED", "LOGIN_STARTED", "LOGIN_COMPLETED", "DOWNLOAD_STARTED", "DOWNLOAD_COMPLETED", "PROCESSING_STARTED", "PROCESSING_COMPLETED", "FINAL_READY", "PRINT_STARTED", "PRINT_COMPLETED"]);
});

for (const failingStep of ["login", "download", "process"] as const) {
  test(`fails the job at ${failingStep} without running later workflow steps`, async () => {
    const workflow = new FakeAutomationWorkflow({ failAt: failingStep });
    const { service, repository } = createService(workflow);
    const created = createJob(service);
    const failed = await service.runJob(created.automationJobId);

    assert.equal(failed.status, AutomationJobStatus.FAILED);
    assert.match(failed.error ?? "", new RegExp(`Fake workflow failed during ${failingStep}`));
    assert.ok(failed.startedAt);
    assert.ok(failed.completedAt);
    assert.ok(failed.progress < 100);
    assert.equal(workflow.calls.at(-1)?.status, {
      login: AutomationJobStatus.LOGGING_IN,
      download: AutomationJobStatus.DOWNLOADING,
      process: AutomationJobStatus.PROCESSING,
    }[failingStep]);
    const expected = failingStep === "login"
      ? ["JOB_CREATED", "LOGIN_STARTED", "JOB_FAILED"]
      : failingStep === "download"
        ? ["JOB_CREATED", "LOGIN_STARTED", "LOGIN_COMPLETED", "DOWNLOAD_STARTED", "JOB_FAILED"]
        : ["JOB_CREATED", "LOGIN_STARTED", "LOGIN_COMPLETED", "DOWNLOAD_STARTED", "DOWNLOAD_COMPLETED", "PROCESSING_STARTED", "JOB_FAILED"];
    assert.deepEqual(eventTypes(repository, created.automationJobId), expected);
  });
}

test("marks print failures as PRINT_FAILED", async () => {
  const workflow = new FakeAutomationWorkflow({ failAt: "print" });
  const { service, repository } = createService(workflow);
  const created = createJob(service);
  const failed = await service.runJob(created.automationJobId);

  assert.equal(failed.status, AutomationJobStatus.PRINT_FAILED);
  assert.equal(failed.currentStep, "PRINT");
  assert.match(failed.error ?? "", /Fake workflow failed during print/);
  assert.ok(failed.completedAt);
  assert.equal(failed.progress, 90);
  assert.equal(failed.finalFile?.name, "final.pdf");
  assert.deepEqual(eventTypes(repository, created.automationJobId), ["JOB_CREATED", "LOGIN_STARTED", "LOGIN_COMPLETED", "DOWNLOAD_STARTED", "DOWNLOAD_COMPLETED", "PROCESSING_STARTED", "PROCESSING_COMPLETED", "FINAL_READY", "PRINT_STARTED", "PRINT_FAILED"]);
});

test("uses the domain transition validator instead of bypassing lifecycle rules", async () => {
  const { service } = createService();
  const created = createJob(service);
  const completed = await service.runJob(created.automationJobId);

  await assert.rejects(
    service.runJob(completed.automationJobId),
    /Invalid automation job transition: COMPLETED -> LOGGING_IN/,
  );
});
