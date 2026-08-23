import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import type { AutomationJobService } from "../jobs/AutomationJobService.js";

export function createAutomationJobHttpServer(service: AutomationJobService): Server {
  return createServer(async (request, response) => {
    try { await route(request, response, service); }
    catch { respond(response, 500, { error: "Internal server error" }); }
  });
}

async function route(request: IncomingMessage, response: ServerResponse, service: AutomationJobService): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  if (request.method === "POST" && url.pathname === "/api/automation/jobs") {
    const body = await readJson(request);
    if (!isRecord(body) || typeof body.deliveryDate !== "string" || !body.deliveryDate.trim()) return respond(response, 400, { error: "deliveryDate is required" });
    return respond(response, 201, service.createJob({ automationJobId: randomUUID(), deliveryDate: body.deliveryDate }));
  }
  const match = /^\/api\/automation\/jobs\/([^/]+)(?:\/(events|files))?$/.exec(url.pathname);
  if (!match || request.method !== "GET") return respond(response, 404, { error: "Not found" });
  const id = decodeURIComponent(match[1]);
  const job = service.getJob(id);
  if (!job) return respond(response, 404, { error: "Job not found" });
  if (match[2] === "events") return respond(response, 200, service.getJobEvents(id) ?? []);
  if (match[2] === "files") return respond(response, 200, { sourceFiles: job.sourceFiles, finalFile: job.finalFile });
  return respond(response, 200, job);
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  let body = "";
  for await (const chunk of request) body += String(chunk);
  try { return JSON.parse(body); } catch { return null; }
}
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null; }
function respond(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, { "content-type": "application/json" }); response.end(JSON.stringify(body));
}
