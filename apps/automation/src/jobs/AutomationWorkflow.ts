import type {
  AutomationFinalFile,
  AutomationJob,
  AutomationSourceFile,
} from "./AutomationJob.js";

export type AutomationDownloadResult = {
  sourceFiles: AutomationSourceFile[];
  downloadedCount: number;
  totalCount: number | null;
};

export type AutomationProcessResult = {
  pythonJobId: string;
  finalFile: AutomationFinalFile;
};

export interface AutomationWorkflow {
  login(job: AutomationJob): Promise<void>;
  download(job: AutomationJob): Promise<AutomationDownloadResult>;
  process(job: AutomationJob): Promise<AutomationProcessResult>;
  print(job: AutomationJob): Promise<void>;
}
