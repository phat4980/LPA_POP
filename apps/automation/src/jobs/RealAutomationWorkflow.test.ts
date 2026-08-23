import assert from "node:assert/strict";
import test from "node:test";
import { createAutomationJob } from "./AutomationJob.js";
import { RealAutomationWorkflow, type CircleKAutomationPort, type CircleKDownloadResult, type Web2ClientPort } from "./RealAutomationWorkflow.js";
import type { CircleKSessionContext } from "../flows/CircleKPOInboxWorkflow.js";

class StubCircleK implements CircleKAutomationPort {
  closedCount = 0;
  private readonly context = {} as CircleKSessionContext;
  constructor(private readonly result: CircleKDownloadResult, private readonly failure?: "login" | "download") {}
  async login(): Promise<CircleKSessionContext> { if (this.failure === "login") throw new Error("bad login"); return this.context; }
  async download(): Promise<CircleKDownloadResult> { if (this.failure === "download") throw new Error("download interrupted"); return this.result; }
  async close(): Promise<void> { this.closedCount += 1; }
}
function web2(overrides: Partial<Web2ClientPort> = {}): Web2ClientPort { return { healthCheck: async () => true, createUploadJob: async () => ({ id: "python-1", status: "queued" as const }), waitForCompletion: async () => ({ id: "python-1", status: "done" as const }), downloadFinalPdf: async () => ({ filePath: "out/final.pdf", fileName: "final.pdf", sizeBytes: 3 }), ...overrides }; }
function job(id = "a") { return createAutomationJob({ automationJobId: id, deliveryDate: "2026-08-24" }); }

test("maps Circle K downloads and Web 2 processing results", async () => {
  const circleK = new StubCircleK({ artifacts: [{ filePath: "out/a.pdf", fileName: "a.pdf", sizeBytes: 2 }], downloadedCount: 1, totalCount: 1 });
  const workflow = new RealAutomationWorkflow(circleK, web2(), "MCH.csv", "out");
  await workflow.login(job()); const download = await workflow.download(job()); const processed = await workflow.process({ ...job(), sourceFiles: download.sourceFiles });
  assert.deepEqual(download.sourceFiles, [{ path: "out/a.pdf", name: "a.pdf", size: 2 }]); assert.equal(processed.pythonJobId, "python-1"); assert.equal(processed.finalFile.name, "final.pdf"); assert.equal(circleK.closedCount, 1);
});
test("closes exactly once and removes the session after a download failure", async () => {
  const circleK = new StubCircleK({ artifacts: [], downloadedCount: 0, totalCount: null }, "download"); const workflow = new RealAutomationWorkflow(circleK, web2(), "MCH.csv", "out");
  await workflow.login(job()); await assert.rejects(workflow.download(job()), /Circle K download failed: download interrupted/); assert.equal(circleK.closedCount, 1);
  await assert.rejects(workflow.download(job()), /no active Circle K session/); assert.equal(circleK.closedCount, 1);
});
test("propagates login failure without storing a partial session", async () => {
  const circleK = new StubCircleK({ artifacts: [], downloadedCount: 0, totalCount: null }, "login"); const workflow = new RealAutomationWorkflow(circleK, web2(), "MCH.csv", "out");
  await assert.rejects(workflow.login(job()), /Circle K login failed: bad login/); await assert.rejects(workflow.download(job()), /no active Circle K session/); assert.equal(circleK.closedCount, 0);
});
test("rejects download without a prior login and does not create a session", async () => {
  const circleK = new StubCircleK({ artifacts: [], downloadedCount: 0, totalCount: null }); const workflow = new RealAutomationWorkflow(circleK, web2(), "MCH.csv", "out");
  await assert.rejects(workflow.download(job("missing")), /no active Circle K session for automation job missing/); assert.equal(circleK.closedCount, 0);
});
test("preserves Web 2 processing failures", async () => {
  const circleK = new StubCircleK({ artifacts: [], downloadedCount: 0, totalCount: null }); const workflow = new RealAutomationWorkflow(circleK, web2({ healthCheck: async () => { throw new Error("offline"); } }), "MCH.csv", "out");
  await assert.rejects(workflow.process(job()), /Web 2 processing failed: offline/);
});
