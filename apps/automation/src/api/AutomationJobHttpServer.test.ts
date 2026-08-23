import assert from "node:assert/strict";
import test from "node:test";
import type { Server } from "node:http";
import { createAutomationJobHttpServer } from "./AutomationJobHttpServer.js";
import { AutomationJobService } from "../jobs/AutomationJobService.js";
import { FakeAutomationWorkflow } from "../jobs/FakeAutomationWorkflow.js";
import { InMemoryAutomationJobRepository } from "../jobs/InMemoryAutomationJobRepository.js";

async function withServer(run: (baseUrl: string, service: AutomationJobService) => Promise<void>, printOutcome: "COMPLETED" | "PRINT_FAILED" = "COMPLETED"): Promise<void> {
  const service = new AutomationJobService(new InMemoryAutomationJobRepository(), new FakeAutomationWorkflow(), undefined, { print: async () => printOutcome });
  const server = createAutomationJobHttpServer(service);
  await listen(server);
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  try { await run(`http://127.0.0.1:${address.port}`, service); } finally { await close(server); }
}
function listen(server: Server): Promise<void> { return new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); }); }
function close(server: Server): Promise<void> { return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); }
async function json(response: Response): Promise<unknown> { return response.json(); }

test("POST creates a queued job immediately and validates input", async () => withServer(async (baseUrl) => {
  const created = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ deliveryDate: "2026-08-24" }) });
  assert.equal(created.status, 201);
  const job = await json(created) as { automationJobId: string; status: string };
  assert.equal(job.status, "QUEUED"); assert.ok(job.automationJobId);
  const invalid = await fetch(`${baseUrl}/api/automation/jobs`, { method: "POST", headers: { "content-type": "application/json" }, body: "{}" });
  assert.equal(invalid.status, 400); assert.deepEqual(await json(invalid), { error: "deliveryDate is required" });
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
