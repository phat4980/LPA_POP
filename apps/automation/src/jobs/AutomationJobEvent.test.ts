import assert from "node:assert/strict";
import test from "node:test";
import { createAutomationJob } from "./AutomationJob.js";
import { InMemoryAutomationJobRepository } from "./InMemoryAutomationJobRepository.js";
import { logJobEvent } from "./JobLogger.js";

function addJob(repository: InMemoryAutomationJobRepository, id: string) {
  repository.create(createAutomationJob({ automationJobId: id, deliveryDate: "2026-08-24" }));
}

test("stores ordered events scoped to their automation job", () => {
  const repository = new InMemoryAutomationJobRepository();
  addJob(repository, "job-a");
  addJob(repository, "job-b");
  repository.addEvent({ automationJobId: "job-a", type: "JOB_CREATED", timestamp: "2026-08-23T00:00:00.000Z" });
  repository.addEvent({ automationJobId: "job-b", type: "JOB_CREATED", timestamp: "2026-08-23T00:00:01.000Z" });
  repository.addEvent({ automationJobId: "job-a", type: "LOGIN_STARTED", timestamp: "2026-08-23T00:00:02.000Z" });
  assert.deepEqual(repository.listEvents("job-a")?.map((event) => event.type), ["JOB_CREATED", "LOGIN_STARTED"]);
  assert.deepEqual(repository.listEvents("job-b")?.map((event) => event.type), ["JOB_CREATED"]);
});

test("returns empty events for an existing job and undefined for a missing job", () => {
  const repository = new InMemoryAutomationJobRepository();
  addJob(repository, "job-a");
  assert.deepEqual(repository.listEvents("job-a"), []);
  assert.equal(repository.listEvents("missing"), undefined);
});

test("formats job logs without credential-like event data", () => {
  const lines: string[] = [];
  logJobEvent({ automationJobId: "job-a", type: "LOGIN_STARTED", timestamp: "2026-08-23T00:00:00.000Z", message: "Login started" }, (line) => lines.push(line));
  assert.equal(lines[0], "[JOB job-a] LOGIN_STARTED Login started");
  const fakePassword = "not-a-real-password";
  assert.equal(lines.some((line) => line.includes(fakePassword)), false);
});
