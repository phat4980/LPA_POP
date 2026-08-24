import assert from "node:assert/strict";
import test from "node:test";
import type { Server } from "node:http";
import { resolve } from "node:path";
import { createAutomationJobHttpServer } from "./AutomationJobHttpServer.js";
import { AutomationJobStatus } from "../jobs/AutomationJob.js";
import { AutomationJobService } from "../jobs/AutomationJobService.js";
import { FakeAutomationWorkflow } from "../jobs/FakeAutomationWorkflow.js";
import { InMemoryAutomationJobRepository } from "../jobs/InMemoryAutomationJobRepository.js";

async function withServer(run: (baseUrl: string, service: AutomationJobService, repository: InMemoryAutomationJobRepository) => Promise<void>, printOutcome: "COMPLETED" | "PRINT_FAILED" = "COMPLETED"): Promise<void> {
  const repository = new InMemoryAutomationJobRepository();
  const service = new AutomationJobService(repository, new FakeAutomationWorkflow(), undefined, { print: async () => printOutcome });
  const server = createAutomationJobHttpServer(service);
  await listen(server);
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  try { await run(`http://127.0.0.1:${address.port}`, service, repository); } finally { await close(server); }
}
function listen(server: Server): Promise<void> { return new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); }); }
function close(server: Server): Promise<void> { return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); }
async function json(response: Response): Promise<unknown> { return response.json(); }
async function waitForStatus(baseUrl: string, jobId: string): Promise<string> {
  const deadline = Date.now() + 500;
  while (Date.now() < deadline) {
    const response = await fetch(`${baseUrl}/api/automation/jobs/${jobId}`);
    const job = await json(response) as { status: string };
    if (job.status !== "QUEUED") return job.status;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 10));
  }
  return "QUEUED";
}

test("POST creates a queued job immediately and validates input", async () => withServer(async (baseUrl) => {
  const created = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deliveryDate: "2026-08-24" }) });
  assert.equal(created.status, 201);
  const job = await json(created) as { automationJobId: string; status: string };
  assert.equal(job.status, "QUEUED"); assert.ok(job.automationJobId);
  const invalid = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  assert.equal(invalid.status, 400); assert.deepEqual(await json(invalid), { error: "deliveryDate is required" });
}));

test("POST starts the created job without waiting for workflow completion", async () => withServer(async (baseUrl) => {
  const created = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deliveryDate: "2026-08-24" }) });
  assert.equal(created.status, 201);
  const job = await json(created) as { automationJobId: string; status: string };
  assert.equal(job.status, "QUEUED");
  assert.notEqual(await waitForStatus(baseUrl, job.automationJobId), "QUEUED");
}));

test("applies explicit CORS to automation GET and preflight requests only", async () => withServer(async (baseUrl) => {
  const allowedOrigin = "http://127.0.0.1:8088";
  const getResponse = await fetch(`${baseUrl}/api/automation/jobs/missing`, { headers: { Origin: allowedOrigin } });
  assert.equal(getResponse.status, 404);
  assert.equal(getResponse.headers.get("access-control-allow-origin"), allowedOrigin);

  const preflight = await fetch(`${baseUrl}/api/automation/jobs`, {
    method: "OPTIONS",
    headers: { Origin: allowedOrigin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type" },
  });
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("access-control-allow-origin"), allowedOrigin);
  assert.equal(preflight.headers.get("access-control-allow-methods"), "GET, POST, OPTIONS");
  assert.equal(preflight.headers.get("access-control-allow-headers"), "Content-Type");

  const blocked = await fetch(`${baseUrl}/api/automation/jobs/missing`, { headers: { Origin: "http://127.0.0.1:9999" } });
  assert.equal(blocked.headers.has("access-control-allow-origin"), false);
  const nonAutomation = await fetch(`${baseUrl}/other`, { headers: { Origin: allowedOrigin } });
  assert.equal(nonAutomation.headers.has("access-control-allow-origin"), false);
}));

test("downloads final PDF bytes and hides missing-file paths", async () => withServer(async (baseUrl, service, repository) => {
  const fixturePath = resolve(process.cwd(), "../../scripts/vendor/test-fixture.pdf");
  const job = service.createJob({ automationJobId: "download-job", deliveryDate: "2026-08-24" });
  repository.update({ ...job, status: AutomationJobStatus.FINAL_READY, currentStep: "FINALIZE", progress: 80, finalFile: { path: fixturePath, name: "test-fixture.pdf" } });
  const download = await fetch(`${baseUrl}/api/automation/jobs/download-job/download`);
  assert.equal(download.status, 200);
  assert.equal(download.headers.get("content-type"), "application/pdf");
  assert.match(download.headers.get("content-disposition") ?? "", /attachment; filename="test-fixture\.pdf"/);
  assert.ok((await download.arrayBuffer()).byteLength > 0);

  repository.update({ ...repository.getById(job.automationJobId)!, finalFile: { path: "missing.pdf", name: "secret.pdf" } });
  const missing = await fetch(`${baseUrl}/api/automation/jobs/download-job/download`);
  assert.equal(missing.status, 404);
  assert.deepEqual(await json(missing), { error: "PDF file is not available" });
}));

test("POST rejects every invalid print option at both API entry points", async () => withServer(async (baseUrl) => {
  const invalidOptions = [
    { copies: 0 }, { copies: 1.5 }, { pageRange: "1,,2" },
    { paperSize: "A3" }, { layout: "diagonal" }, { fitMode: "scale" },
  ];
  for (const printOptions of invalidOptions) {
    const created = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deliveryDate: "2026-08-24", printOptions }) });
    assert.equal(created.status, 400);
    const printed = await fetch(`${baseUrl}/api/automation/jobs/missing/print`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ printOptions }) });
    assert.equal(printed.status, 400);
  }
  const raw = await fetch(`${baseUrl}/api/automation/jobs/missing/print`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ "-print-settings": "duplex" }) });
  assert.equal(raw.status, 400);
}));

test("GET job, events, and files are scoped and missing ids are safe", async () => withServer(async (baseUrl, service) => {
  const a = service.createJob({ automationJobId: "job-a", deliveryDate: "2026-08-24" });
  const b = service.createJob({ automationJobId: "job-b", deliveryDate: "2026-08-25" });
  await service.runJob(a.automationJobId);
  const job = await fetch(`${baseUrl}/api/automation/jobs/job-a`);
  assert.equal(job.status, 200); assert.equal((await json(job) as { automationJobId: string }).automationJobId, "job-a");
  const events = await fetch(`${baseUrl}/api/automation/jobs/job-a/events`);
  assert.deepEqual((await json(events) as Array<{ type: string }>).map((event) => event.type), ["JOB_CREATED", "LOGIN_STARTED", "LOGIN_COMPLETED", "DOWNLOAD_STARTED", "DOWNLOAD_COMPLETED", "PROCESSING_STARTED", "PROCESSING_COMPLETED", "FINAL_READY"]);
  const files = await fetch(`${baseUrl}/api/automation/jobs/job-a/files`);
  assert.equal((await json(files) as { finalFile: { name: string } }).finalFile.name, "final.pdf");
  const other = await fetch(`${baseUrl}/api/automation/jobs/job-b/files`);
  assert.equal((await json(other) as { finalFile: null }).finalFile, null);
  for (const path of ["missing", "missing/events", "missing/files", "%2e%2e%2fsecret/files"]) {
    const response = await fetch(`${baseUrl}/api/automation/jobs/${path}`);
    assert.equal(response.status, 404);
    const error = JSON.stringify(await json(response));
    assert.equal(error.includes("password"), false); assert.equal(error.includes("C:\\"), false); assert.equal(error.includes("at "), false);
  }
}));

test("POST print uses the FINAL_READY trigger and retains the final file on either outcome", async () => {
  await withServer(async (baseUrl, service) => {
    const job = service.createJob({ automationJobId: "print-success", deliveryDate: "2026-08-24" });
    await service.runJob(job.automationJobId);
    const printed = await fetch(`${baseUrl}/api/automation/jobs/print-success/print`, { method: "POST" });
    assert.equal(printed.status, 200);
    const result = await json(printed) as { status: string; finalFile: { name: string } };
    assert.equal(result.status, "COMPLETED"); assert.equal(result.finalFile.name, "final.pdf");
    const repeated = await fetch(`${baseUrl}/api/automation/jobs/print-success/print`, { method: "POST" });
    assert.equal(repeated.status, 409);
  });
  await withServer(async (baseUrl, service) => {
    const job = service.createJob({ automationJobId: "print-failure", deliveryDate: "2026-08-24" });
    await service.runJob(job.automationJobId);
    const printed = await fetch(`${baseUrl}/api/automation/jobs/print-failure/print`, { method: "POST" });
    const result = await json(printed) as { status: string; finalFile: { name: string } };
    assert.equal(result.status, "PRINT_FAILED"); assert.equal(result.finalFile.name, "final.pdf");
  }, "PRINT_FAILED");
});
