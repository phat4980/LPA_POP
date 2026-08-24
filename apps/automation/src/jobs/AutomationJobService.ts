import {
  AutomationJobStatus,
  createAutomationJob,
  transitionAutomationJob,
  type AutomationJob,
  type CreateAutomationJobInput,
} from "./AutomationJob.js";
import type { AutomationJobRepository } from "./AutomationJobRepository.js";
import type { AutomationWorkflow } from "./AutomationWorkflow.js";
import type { AutomationJobEventType } from "./AutomationJobEvent.js";
import type { AutomationJobEvent } from "./AutomationJobEvent.js";
import { logJobEvent, type JobLogSink } from "./JobLogger.js";
import { validatePrintOptions, type PrintOptions, type PrintOutcome } from "../printing/PrintService.js";

export interface AutomationPrintService { print(jobId: string, options?: PrintOptions): Promise<PrintOutcome>; }

const progress = {
  downloading: 20,
  processing: 60,
  finalReady: 80,
  printing: 90,
} as const;

export class AutomationJobService {
  constructor(
    private readonly repository: AutomationJobRepository,
    private readonly workflow: AutomationWorkflow,
    private readonly logSink?: JobLogSink,
    private readonly printService?: AutomationPrintService,
  ) {}

  createJob(input: CreateAutomationJobInput): AutomationJob {
    if (input.printOptions !== undefined) validatePrintOptions(input.printOptions);
    const job = this.repository.create(createAutomationJob(input));
    this.event(job, "JOB_CREATED");
    return job;
  }

  getJob(automationJobId: string): AutomationJob | undefined {
    return this.repository.getById(automationJobId);
  }

  getJobEvents(automationJobId: string): AutomationJobEvent[] | undefined {
    return this.repository.listEvents(automationJobId);
  }

  async runJob(automationJobId: string): Promise<AutomationJob> {
    let job = this.requireJob(automationJobId);
    job = this.transition(job, AutomationJobStatus.LOGGING_IN);
    this.event(job, "LOGIN_STARTED");

    try {
      await this.workflow.login(job);
      this.event(job, "LOGIN_COMPLETED");
    } catch (error) {
      return this.fail(job, AutomationJobStatus.FAILED, error);
    }

    job = this.transition(job, AutomationJobStatus.DOWNLOADING, progress.downloading);
    this.event(job, "DOWNLOAD_STARTED");
    try {
      const download = await this.workflow.download(job);
      job = this.update(job, {
        downloadedCount: download.downloadedCount,
        totalCount: download.totalCount,
        sourceFiles: download.sourceFiles,
      });
      this.event(job, "DOWNLOAD_COMPLETED");
    } catch (error) {
      return this.fail(job, AutomationJobStatus.FAILED, error);
    }

    job = this.transition(job, AutomationJobStatus.PROCESSING, progress.processing);
    this.event(job, "PROCESSING_STARTED");
    let processing;
    try {
      processing = await this.workflow.process(job);
      this.event(job, "PROCESSING_COMPLETED");
    } catch (error) {
      return this.fail(job, AutomationJobStatus.FAILED, error);
    }

    job = this.transition(job, AutomationJobStatus.FINAL_READY, progress.finalReady);
    job = this.update(job, { finalFile: processing.finalFile, pythonJobId: processing.pythonJobId });
    this.event(job, "FINAL_READY");
    return job.autoPrint ? this.triggerPrint(job.automationJobId) : job;
  }

  async triggerPrint(automationJobId: string, options?: PrintOptions): Promise<AutomationJob> {
    if (options !== undefined) validatePrintOptions(options);
    let job = this.requireJob(automationJobId);
    if (job.status !== AutomationJobStatus.FINAL_READY) throw new Error("Printing is only available when the automation job is FINAL_READY.");
    job = this.transition(job, AutomationJobStatus.PRINTING, progress.printing);
    this.event(job, "PRINT_STARTED");
    try {
      if (!this.printService) throw new Error("Print service is not configured.");
      const outcome = await this.printService.print(job.automationJobId, options);
      if (outcome === "PRINT_FAILED") return this.fail(job, AutomationJobStatus.PRINT_FAILED, new Error("Print service failed."));
    } catch (error) {
      return this.fail(job, AutomationJobStatus.PRINT_FAILED, error);
    }

    job = this.transition(job, AutomationJobStatus.COMPLETED);
    this.event(job, "PRINT_COMPLETED");
    return job;
  }

  private requireJob(automationJobId: string): AutomationJob {
    const job = this.repository.getById(automationJobId);
    if (!job) {
      throw new Error(`Automation job was not found: ${automationJobId}.`);
    }
    return job;
  }

  private transition(job: AutomationJob, nextStatus: AutomationJobStatus, nextProgress?: number): AutomationJob {
    const transitioned = transitionAutomationJob(job, nextStatus);
    return this.update(transitioned, nextProgress === undefined ? {} : { progress: nextProgress });
  }

  private update(job: AutomationJob, changes: Partial<AutomationJob>): AutomationJob {
    return this.repository.update({ ...job, ...changes });
  }

  private fail(job: AutomationJob, status: AutomationJobStatus.FAILED | AutomationJobStatus.PRINT_FAILED, error: unknown): AutomationJob {
    const message = error instanceof Error ? error.message : String(error);
    const failed = this.repository.update(transitionAutomationJob(job, status, { error: message }));
    this.event(failed, status === AutomationJobStatus.FAILED ? "JOB_FAILED" : "PRINT_FAILED", message);
    return failed;
  }

  private event(job: AutomationJob, type: AutomationJobEventType, message?: string): void {
    const event = this.repository.addEvent({ automationJobId: job.automationJobId, type, timestamp: new Date().toISOString(), message });
    logJobEvent(event, this.logSink);
  }
}
