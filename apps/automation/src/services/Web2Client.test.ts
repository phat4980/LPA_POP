import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import test from "node:test";
import { Web2Client } from "./Web2Client.js";

function listen(server: Server): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") return reject(new Error("Server did not expose a port."));
      resolve(address.port);
    });
  });
}

function close(server: Server): Promise<void> {
  return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}

test("forwards the complete Web2 snapshot log with normalized levels", async () => {
  const server = createServer((request, response) => {
    if (request.url !== "/api/jobs/python-1") {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({
      id: "python-1",
      status: "done",
      logs: [
        { time: "2026-08-25T00:00:00.000Z", level: "INFO", message: "Bắt đầu xử lý" },
        { time: "2026-08-25T00:00:01.000Z", level: "WARNING", message: "Khong co ma cua hang: SG0001" },
        { time: "2026-08-25T00:00:02.000Z", level: "ERROR", message: "Lỗi kiểm tra" },
      ],
    }));
  });
  const port = await listen(server);
  const entries: Array<{ level: string; message: string }> = [];
  try {
    new Web2Client({ baseUrl: `http://127.0.0.1:${port}` }).subscribeToJobEvents("python-1", (entry) => entries.push(entry));
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.deepEqual(entries.map(({ level, message }) => ({ level, message })), [
      { level: "INFO", message: "Bắt đầu xử lý" },
      { level: "WARNING", message: "Khong co ma cua hang: SG0001" },
      { level: "ERROR", message: "Lỗi kiểm tra" },
    ]);
  } finally {
    await close(server);
  }
});