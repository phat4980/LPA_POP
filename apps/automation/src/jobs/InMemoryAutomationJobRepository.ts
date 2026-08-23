import type { AutomationJob } from "./AutomationJob.js";
import type { AutomationJobRepository } from "./AutomationJobRepository.js";
import type { AutomationJobEvent } from "./AutomationJobEvent.js";

export class InMemoryAutomationJobRepository implements AutomationJobRepository {
  private readonly jobs = new Map<string, AutomationJob>();
  private readonly events = new Map<string, AutomationJobEvent[]>();

  create(job: AutomationJob): AutomationJob {
    if (this.jobs.has(job.automationJobId)) {
      throw new Error(`Automation job already exists: ${job.automationJobId}.`);
    }
    return this.store(job);
  }

  addEvent(event: AutomationJobEvent): AutomationJobEvent {
    if (!this.jobs.has(event.automationJobId)) throw new Error(`Automation job was not found: ${event.automationJobId}.`);
    const events = this.events.get(event.automationJobId) ?? [];
    const stored = { ...event };
    events.push(stored);
    this.events.set(event.automationJobId, events);
    return { ...stored };
  }

  listEvents(automationJobId: string): AutomationJobEvent[] | undefined {
    if (!this.jobs.has(automationJobId)) return undefined;
    return (this.events.get(automationJobId) ?? []).map((event) => ({ ...event }));
  }

  getById(automationJobId: string): AutomationJob | undefined {
    const job = this.jobs.get(automationJobId);
    return job ? cloneJob(job) : undefined;
  }

  update(job: AutomationJob): AutomationJob {
    if (!this.jobs.has(job.automationJobId)) {
      throw new Error(`Automation job was not found: ${job.automationJobId}.`);
    }
    return this.store(job);
  }

  private store(job: AutomationJob): AutomationJob {
    const storedJob = cloneJob(job);
    this.jobs.set(storedJob.automationJobId, storedJob);
    return cloneJob(storedJob);
  }
}

function cloneJob(job: AutomationJob): AutomationJob {
  return {
    ...job,
    sourceFiles: job.sourceFiles.map((sourceFile) => ({ ...sourceFile })),
    finalFile: job.finalFile ? { ...job.finalFile } : null,
  };
}
