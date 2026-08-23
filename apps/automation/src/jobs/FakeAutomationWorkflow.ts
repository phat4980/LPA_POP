import type { AutomationJob, AutomationFinalFile } from "./AutomationJob.js";
import type { AutomationDownloadResult, AutomationProcessResult, AutomationWorkflow } from "./AutomationWorkflow.js";

export type FakeAutomationWorkflowStep = "login" | "download" | "process" | "print";

export type FakeAutomationWorkflowOptions = {
  failAt?: FakeAutomationWorkflowStep;
  downloadResult?: AutomationDownloadResult;
  finalFile?: AutomationFinalFile;
  pythonJobId?: string;
};

export class FakeAutomationWorkflow implements AutomationWorkflow {
  readonly calls: AutomationJob[] = [];

  constructor(private readonly options: FakeAutomationWorkflowOptions = {}) {}

  async login(job: AutomationJob): Promise<void> {
    this.record(job);
    this.throwIfConfiguredToFail("login");
  }

  async download(job: AutomationJob): Promise<AutomationDownloadResult> {
    this.record(job);
    this.throwIfConfiguredToFail("download");
    return this.options.downloadResult ?? {
      sourceFiles: [{ path: "jobs/test/source.pdf", name: "source.pdf", size: 1 }],
      downloadedCount: 1,
      totalCount: 1,
    };
  }

  async process(job: AutomationJob): Promise<AutomationProcessResult> {
    this.record(job);
    this.throwIfConfiguredToFail("process");
    return {
      pythonJobId: this.options.pythonJobId ?? "python-job-1",
      finalFile: this.options.finalFile ?? { path: "jobs/test/final.pdf", name: "final.pdf", size: 1 },
    };
  }

  async print(job: AutomationJob): Promise<void> {
    this.record(job);
    this.throwIfConfiguredToFail("print");
  }

  private record(job: AutomationJob): void {
    this.calls.push({
      ...job,
      sourceFiles: job.sourceFiles.map((sourceFile) => ({ ...sourceFile })),
      finalFile: job.finalFile ? { ...job.finalFile } : null,
    });
  }

  private throwIfConfiguredToFail(step: FakeAutomationWorkflowStep): void {
    if (this.options.failAt === step) {
      throw new Error(`Fake workflow failed during ${step}.`);
    }
  }
}
