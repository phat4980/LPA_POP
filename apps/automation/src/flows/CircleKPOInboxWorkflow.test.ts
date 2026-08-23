import assert from "node:assert/strict";
import test from "node:test";
import { AutomationJobStatus, createAutomationJob } from "../jobs/AutomationJob.js";
import { AutomationJobService } from "../jobs/AutomationJobService.js";
import { InMemoryAutomationJobRepository } from "../jobs/InMemoryAutomationJobRepository.js";
import type { CircleKAutomationPort, Web2ClientPort } from "../jobs/RealAutomationWorkflow.js";
import type { CircleKSessionContext } from "./CircleKPOInboxWorkflow.js";
import type { AutomationConfig } from "../config/environment.js";

test("closes the created BrowserSession when Circle K authentication fails after opening the page", async (t) => {
  let closeCalls = 0;
  let pageCreated = false;

  t.mock.module("../browser/BrowserSession.js", {
    namedExports: {
      BrowserSession: class {
        async createPage(): Promise<object> { pageCreated = true; return {}; }
        async close(): Promise<void> { closeCalls += 1; }
      },
    },
  });
  t.mock.module("../circlek/pages/LoginPage.js", {
    namedExports: {
      LoginPage: class {
        async open(): Promise<void> {}
        async login(): Promise<void> { throw new Error("authentication rejected at submit"); }
      },
    },
  });
  t.mock.module("../circlek/pages/POInboxPage.js", { namedExports: { POInboxPage: class {} } });

  const { loginToCircleK } = await import("./CircleKPOInboxWorkflow.js");
  const { RealAutomationWorkflow } = await import("../jobs/RealAutomationWorkflow.js");
  const config: AutomationConfig = { host: "127.0.0.1", port: 8090, web2BaseUrl: "http://web2", web2ListFile: "MCH.csv", circleKBaseUrl: "https://circlek.example/login", circleKUsername: "user", circleKPassword: "password", automationOutputDir: "out", headless: true, printerName: "Test printer", printScriptPath: "scripts/print.ps1" };
  const circleK: CircleKAutomationPort = {
    login: (deliveryDate) => loginToCircleK(config, new Date(`${deliveryDate}T00:00:00`)),
    async download(): Promise<never> { throw new Error("download must not run after failed login"); },
    async close(): Promise<void> { throw new Error("RealAutomationWorkflow must not receive a context to close"); },
  };
  const web2: Web2ClientPort = { healthCheck: async () => true, createUploadJob: async () => ({ id: "python-1", status: "queued" }), waitForCompletion: async () => ({ id: "python-1", status: "done" }), downloadFinalPdf: async () => ({ filePath: "out/final.pdf", fileName: "final.pdf", sizeBytes: 1 }) };
  const workflow = new RealAutomationWorkflow(circleK, web2, "MCH.csv", "out");
  const repository = new InMemoryAutomationJobRepository();
  const service = new AutomationJobService(repository, workflow);
  const job = service.createJob({ automationJobId: "mid-login-failure", deliveryDate: "2026-08-24" });

  const failed = await service.runJob(job.automationJobId);
  assert.equal(pageCreated, true);
  assert.equal(closeCalls, 1);
  assert.equal(failed.status, AutomationJobStatus.FAILED);
  assert.match(failed.error ?? "", /Circle K login failed: authentication rejected at submit/);
  await assert.rejects(workflow.download(createAutomationJob({ automationJobId: job.automationJobId, deliveryDate: job.deliveryDate })), /no active Circle K session/);
});
