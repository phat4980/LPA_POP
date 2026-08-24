export enum AutomationJobStatus {
  QUEUED = "QUEUED",
  LOGGING_IN = "LOGGING_IN",
  DOWNLOADING = "DOWNLOADING",
  PROCESSING = "PROCESSING",
  FINAL_READY = "FINAL_READY",
  FAILED = "FAILED",
  PRINTING = "PRINTING",
  PRINT_FAILED = "PRINT_FAILED",
  COMPLETED = "COMPLETED",
}

export type AutomationJobStep =
  | "QUEUED"
  | "LOGIN"
  | "DOWNLOAD"
  | "PROCESS"
  | "FINALIZE"
  | "PRINT"
  | "FAILED"
  | "COMPLETED";

export type AutomationSourceFile = {
  path: string;
  name: string;
  size?: number;
};

export type AutomationFinalFile = {
  path: string;
  name: string;
  size?: number;
};

import type { PrintOptions } from "../printing/PrintService.js";

export type AutomationJob = {
  automationJobId: string;
  deliveryDate: string;
  status: AutomationJobStatus;
  currentStep: AutomationJobStep;
  progress: number;
  downloadedCount: number;
  totalCount: number | null;
  pythonJobId: string | null;
  sourceFiles: AutomationSourceFile[];
  finalFile: AutomationFinalFile | null;
  autoPrint: boolean;
  printOptions?: PrintOptions;
  error: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
};

export type CreateAutomationJobInput = {
  automationJobId: string;
  deliveryDate: string;
  autoPrint?: boolean;
  printOptions?: PrintOptions;
};

export type TransitionAutomationJobOptions = {
  error?: string;
  now?: Date;
};

const validTransitions: ReadonlyMap<AutomationJobStatus, readonly AutomationJobStatus[]> = new Map([
  [AutomationJobStatus.QUEUED, [AutomationJobStatus.LOGGING_IN]],
  [AutomationJobStatus.LOGGING_IN, [AutomationJobStatus.DOWNLOADING, AutomationJobStatus.FAILED]],
  [AutomationJobStatus.DOWNLOADING, [AutomationJobStatus.PROCESSING, AutomationJobStatus.FAILED]],
  [AutomationJobStatus.PROCESSING, [AutomationJobStatus.FINAL_READY, AutomationJobStatus.FAILED]],
  [AutomationJobStatus.FINAL_READY, [AutomationJobStatus.PRINTING]],
  [AutomationJobStatus.PRINTING, [AutomationJobStatus.COMPLETED, AutomationJobStatus.PRINT_FAILED]],
]);

const stepsByStatus: Readonly<Record<AutomationJobStatus, AutomationJobStep>> = {
  [AutomationJobStatus.QUEUED]: "QUEUED",
  [AutomationJobStatus.LOGGING_IN]: "LOGIN",
  [AutomationJobStatus.DOWNLOADING]: "DOWNLOAD",
  [AutomationJobStatus.PROCESSING]: "PROCESS",
  [AutomationJobStatus.FINAL_READY]: "FINALIZE",
  [AutomationJobStatus.FAILED]: "FAILED",
  [AutomationJobStatus.PRINTING]: "PRINT",
  [AutomationJobStatus.PRINT_FAILED]: "PRINT",
  [AutomationJobStatus.COMPLETED]: "COMPLETED",
};

export function createAutomationJob(
  input: CreateAutomationJobInput,
  now: Date = new Date(),
): AutomationJob {
  return {
    automationJobId: input.automationJobId,
    deliveryDate: input.deliveryDate,
    status: AutomationJobStatus.QUEUED,
    currentStep: "QUEUED",
    progress: 0,
    downloadedCount: 0,
    totalCount: null,
    pythonJobId: null,
    sourceFiles: [],
    finalFile: null,
    autoPrint: input.autoPrint ?? false,
    ...(input.printOptions === undefined ? {} : { printOptions: input.printOptions }),
    error: null,
    createdAt: now.toISOString(),
    startedAt: null,
    completedAt: null,
  };
}

export function transitionAutomationJob(
  job: AutomationJob,
  nextStatus: AutomationJobStatus,
  options: TransitionAutomationJobOptions = {},
): AutomationJob {
  if (!validTransitions.get(job.status)?.includes(nextStatus)) {
    throw new Error(`Invalid automation job transition: ${job.status} -> ${nextStatus}.`);
  }

  const timestamp = (options.now ?? new Date()).toISOString();
  const isTerminal = nextStatus === AutomationJobStatus.FAILED
    || nextStatus === AutomationJobStatus.PRINT_FAILED
    || nextStatus === AutomationJobStatus.COMPLETED;

  return {
    ...job,
    status: nextStatus,
    currentStep: stepsByStatus[nextStatus],
    progress: nextStatus === AutomationJobStatus.COMPLETED ? 100 : job.progress,
    error: nextStatus === AutomationJobStatus.FAILED || nextStatus === AutomationJobStatus.PRINT_FAILED
      ? options.error ?? job.error
      : null,
    startedAt: nextStatus === AutomationJobStatus.LOGGING_IN ? job.startedAt ?? timestamp : job.startedAt,
    completedAt: isTerminal ? timestamp : job.completedAt,
  };
}
