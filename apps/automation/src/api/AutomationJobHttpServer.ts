import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { access } from "node:fs/promises";
import { constants, createReadStream } from "node:fs";
import { basename } from "node:path";
import type { AutomationJobService } from "../jobs/AutomationJobService.js";
import { validatePrintOptions } from "../printing/PrintService.js";

export function createAutomationJobHttpServer(service: AutomationJobService, options: { allowedOrigins?: readonly string[] } = {}): Server {
  const allowedOrigins = new Set(options.allowedOrigins ?? ["http://127.0.0.1:8088", "http://localhost:8088"]);
  return createServer(async (request, response) => {
    try { await route(request, response, service, allowedOrigins); }
    catch { respond(response, 500, { error: "Internal server error" }); }
  });
}

async function route(request: IncomingMessage, response: ServerResponse, service: AutomationJobService, allowedOrigins: ReadonlySet<string>): Promise<void> {
  const url = new URL(request.url ?? "/", "http://localhost");
  if (url.pathname.startsWith("/api/automation/")) {
    const origin = request.headers.origin;
    if (origin && allowedOrigins.has(origin)) response.setHeader("access-control-allow-origin", origin);
    if (request.method === "OPTIONS") {
      response.setHeader("access-control-allow-methods", "GET, POST, OPTIONS");
      response.setHeader("access-control-allow-headers", "Content-Type");
      response.statusCode = 204;
      response.end();
      return;
    }
  }
  if (request.method === "POST" && url.pathname === "/api/automation/jobs") {
    const body = await readJson(request);
    if (!isRecord(body) || typeof body.deliveryDate !== "string" || !body.deliveryDate.trim()) return respond(response, 400, { error: "deliveryDate is required" });
    if (body.autoPrint !== undefined && typeof body.autoPrint !== "boolean") return respond(response, 400, { error: "autoPrint must be a boolean" });
    if (body.printSettings !== undefined || body["-print-settings"] !== undefined) return respond(response, 400, { error: "Raw print settings are not accepted" });
    let printOptions;
    try { if (body.printOptions !== undefined) printOptions = validatePrintOptions(body.printOptions); }
    catch (error) { return respond(response, 400, { error: error instanceof Error ? error.message : "Invalid printOptions" }); }
    return respond(response, 201, service.createJob({ automationJobId: randomUUID(), deliveryDate: body.deliveryDate, autoPrint: body.autoPrint, printOptions }));
  }
  const printMatch = /^\/api\/automation\/jobs\/([^/]+)\/print$/.exec(url.pathname);
  if (request.method === "POST" && printMatch) {
    const body = await readJson(request);
    let printOptions;
    try {
      if (body !== null && isRecord(body) && Object.keys(body).some((key) => key !== "printOptions")) return respond(response, 400, { error: "Only printOptions is accepted in the print request body" });
      if (body !== null && isRecord(body) && body.printOptions !== undefined) printOptions = validatePrintOptions(body.printOptions);
      else if (body !== null && !isRecord(body)) return respond(response, 400, { error: "Request body must be an object" });
    } catch (error) { return respond(response, 400, { error: error instanceof Error ? error.message : "Invalid printOptions" }); }
    try { return respond(response, 200, await service.triggerPrint(decodeURIComponent(printMatch[1]), printOptions)); }
    catch (error) { return respond(response, 409, { error: error instanceof Error ? error.message : "Print request failed" }); }
  }
    const downloadMatch = /^\/api\/automation\/jobs\/([^/]+)\/download$/.exec(url.pathname);
    if (request.method === "GET" && downloadMatch) {
      const job = service.getJob(decodeURIComponent(downloadMatch[1]));
      if (!job?.finalFile?.path) return respond(response, 404, { error: "PDF file is not available" });
      try { await access(job.finalFile.path, constants.F_OK); }
      catch { return respond(response, 404, { error: "PDF file is not available" }); }
      const filename = basename(job.finalFile.name || "purchase-order.pdf").replace(/[\r\n"\\]/g, "_") || "purchase-order.pdf";
      response.writeHead(200, { "content-type": "application/pdf", "content-disposition": `attachment; filename="${filename}"` });
      createReadStream(job.finalFile.path).on("error", () => response.destroy()).pipe(response);
      return;
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
