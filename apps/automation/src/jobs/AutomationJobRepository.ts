import type { AutomationJob } from "./AutomationJob.js";
import type { AutomationJobEvent } from "./AutomationJobEvent.js";

export interface AutomationJobRepository {
  create(job: AutomationJob): AutomationJob;
  getById(automationJobId: string): AutomationJob | undefined;
  update(job: AutomationJob): AutomationJob;
  addEvent(event: AutomationJobEvent): AutomationJobEvent;
  listEvents(automationJobId: string): AutomationJobEvent[] | undefined;
}
