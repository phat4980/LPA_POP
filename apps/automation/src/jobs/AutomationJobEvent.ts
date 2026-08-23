export type AutomationJobEventType =
  | "JOB_CREATED" | "LOGIN_STARTED" | "LOGIN_COMPLETED" | "DOWNLOAD_STARTED"
  | "DOWNLOAD_COMPLETED" | "PROCESSING_STARTED" | "PROCESSING_COMPLETED"
  | "FINAL_READY" | "PRINT_STARTED" | "PRINT_COMPLETED" | "JOB_FAILED" | "PRINT_FAILED";

export type AutomationJobEvent = {
  automationJobId: string;
  type: AutomationJobEventType;
  timestamp: string;
  message?: string;
};
