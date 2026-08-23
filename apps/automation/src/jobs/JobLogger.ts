import type { AutomationJobEvent } from "./AutomationJobEvent.js";

export type JobLogSink = (line: string) => void;

export function logJobEvent(event: AutomationJobEvent, sink: JobLogSink = console.log): void {
  sink(`[JOB ${event.automationJobId}] ${event.type}${event.message ? ` ${event.message}` : ""}`);
}
