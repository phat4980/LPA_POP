import { basename } from "node:path";
import type { AutomationJob, AutomationSourceFile } from "./AutomationJob.js";
import type { AutomationDownloadResult, AutomationProcessResult, AutomationWorkflow } from "./AutomationWorkflow.js";
import { createFinalPdfOutputPath } from "../utils/pdfFile.js";
import type { Web2Client, Web2FinalArtifact, Web2Job, Web2LogEntry } from "../services/Web2Client.js";
import type { AutomationConfig } from "../config/environment.js";
import { closeCircleKSession, downloadCircleKSession, loginToCircleK, type CircleKSessionContext } from "../flows/CircleKPOInboxWorkflow.js";

export type CircleKDownloadArtifact = { filePath: string; fileName: string; sizeBytes: number };
export type CircleKDownloadResult = { artifacts: CircleKDownloadArtifact[]; downloadedCount: number; totalCount: number | null };
export interface CircleKAutomationPort { login(deliveryDate: string): Promise<CircleKSessionContext>; download(context: CircleKSessionContext): Promise<CircleKDownloadResult>; close(context: CircleKSessionContext): Promise<void>; }
export type Web2ClientPort = Pick<Web2Client, "healthCheck" | "createUploadJob" | "waitForCompletion" | "downloadFinalPdf"> & Partial<Pick<Web2Client, "subscribeToJobEvents">>;
export function createRealAutomationWorkflow(circleK: CircleKAutomationPort, web2Client: Web2ClientPort, options: { listFile: string; outputDir: string }): RealAutomationWorkflow { return new RealAutomationWorkflow(circleK, web2Client, options.listFile, options.outputDir); }
export function createCircleKAutomationPort(config: AutomationConfig): CircleKAutomationPort {
  return {
    login: (deliveryDate) => loginToCircleK(config, parseDeliveryDate(deliveryDate)),
    async download(context) {
      const result = await downloadCircleKSession(context, config.automationOutputDir);
      return {
        artifacts: result.artifacts.map((artifact) => ({ filePath: artifact.filePath, fileName: artifact.fileName, sizeBytes: artifact.sizeBytes })),
        downloadedCount: result.artifacts.length,
        totalCount: result.pageResults.reduce((total, page) => total + page.poCount, 0),
      };
    },
    close: closeCircleKSession,
  };
}

export class RealAutomationWorkflow implements AutomationWorkflow {
  // Phase 6 executes jobs serially. Concurrent access and abandoned-session cleanup are deferred.
  private readonly circleKSessions = new Map<string, CircleKSessionContext>();
  constructor(private readonly circleK: CircleKAutomationPort, private readonly web2Client: Web2ClientPort, private readonly listFile: string, private readonly outputDir: string, private readonly logSink?: (jobId: string, entry: Web2LogEntry) => void) {}
  async login(job: AutomationJob): Promise<void> {
    try { this.circleKSessions.set(job.automationJobId, await this.circleK.login(job.deliveryDate)); }
    catch (error) { throw new Error(`Circle K login failed: ${messageOf(error)}`); }
  }
  async download(job: AutomationJob): Promise<AutomationDownloadResult> {
    const context = this.circleKSessions.get(job.automationJobId);
    if (!context) throw new Error(`Circle K download failed: no active Circle K session for automation job ${job.automationJobId}.`);
    try { const result = await this.circleK.download(context); return { sourceFiles: result.artifacts.map(toSourceFile), downloadedCount: result.downloadedCount, totalCount: result.totalCount }; }
    catch (error) { throw new Error(`Circle K download failed: ${messageOf(error)}`); }
    finally { this.circleKSessions.delete(job.automationJobId); await this.circleK.close(context); }
  }
  async process(job: AutomationJob): Promise<AutomationProcessResult> {
    try {
      if (!(await this.web2Client.healthCheck())) throw new Error("Web 2 health check failed.");
      const createdJob: Web2Job = await this.web2Client.createUploadJob(job.sourceFiles.map((sourceFile) => sourceFile.path), this.listFile);
      const stopLogStream = this.web2Client.subscribeToJobEvents?.(createdJob.id, (entry) => this.logSink?.(job.automationJobId, entry));
      try {
        const completedJob = await this.web2Client.waitForCompletion(createdJob.id);
        const finalFile: Web2FinalArtifact = await this.web2Client.downloadFinalPdf(completedJob.id, await createFinalPdfOutputPath(this.outputDir, parseDeliveryDate(job.deliveryDate)));
        return { pythonJobId: createdJob.id, finalFile: { path: finalFile.filePath, name: finalFile.fileName, size: finalFile.sizeBytes } };
      } finally { stopLogStream?.(); }
    } catch (error) { throw new Error(`Web 2 processing failed: ${messageOf(error)}`); }
  }
  async print(_job: AutomationJob): Promise<void> { /* Printing is intentionally deferred to a later phase. */ }
}
function toSourceFile(artifact: CircleKDownloadArtifact): AutomationSourceFile { return { path: artifact.filePath, name: artifact.fileName || basename(artifact.filePath), size: artifact.sizeBytes }; }
function parseDeliveryDate(value: string): Date { const date = new Date(`${value}T00:00:00`); if (Number.isNaN(date.getTime())) throw new Error(`Invalid delivery date: ${value}.`); return date; }
function messageOf(error: unknown): string { return error instanceof Error ? error.message : String(error); }
