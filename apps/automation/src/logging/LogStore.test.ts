import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { LogStore } from "./LogStore.js";

test("stores leveled logs and removes entries older than retention", async () => {
  const directory = await mkdtemp(join(tmpdir(), "lpa-logs-"));
  const store = new LogStore(join(directory, "automation.sqlite"), 3);
  try {
    store.append({ automationJobId: "job-1", ts: new Date().toISOString(), level: "INFO", message: "current" });
    store.append({ automationJobId: "job-1", ts: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(), level: "WARNING", message: "old" });
    assert.deepEqual(store.list("job-1").map((entry) => entry.message), ["current", "old"]);
    store.cleanup();
    assert.deepEqual(store.list("job-1").map((entry) => entry.message), ["current"]);
  } finally { store.close(); }
});