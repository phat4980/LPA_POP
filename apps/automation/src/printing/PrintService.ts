import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import type { AutomationJobRepository } from "../jobs/AutomationJobRepository.js";

export type PrintOutcome = "COMPLETED" | "PRINT_FAILED";
export interface PrintOptions {
  copies?: number;
  pageRange?: string;
  paperSize?: "A4" | "Letter" | "A5";
  layout?: "portrait" | "landscape";
  fitMode?: "fit" | "noscale" | "shrink";
}

export const defaultPrintOptions: Required<Omit<PrintOptions, "pageRange">> = {
  copies: 2,
  paperSize: "A5",
  layout: "portrait",
  fitMode: "fit",
};

export function validatePrintOptions(value: unknown): PrintOptions {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("printOptions must be an object");
  const options = value as Record<string, unknown>;
  const allowed = new Set(["copies", "pageRange", "paperSize", "layout", "fitMode"]);
  const unknown = Object.keys(options).find((key) => !allowed.has(key));
  if (unknown) throw new Error(`printOptions contains unsupported field: ${unknown}`);
  if (options.copies !== undefined && (typeof options.copies !== "number" || !Number.isInteger(options.copies) || options.copies < 1 || options.copies > 20)) throw new Error("printOptions.copies must be an integer from 1 to 20");
  if (options.pageRange !== undefined && (typeof options.pageRange !== "string" || !/^\d+(-\d+)?(,\d+(-\d+)?)*$/.test(options.pageRange))) throw new Error("printOptions.pageRange must use Sumatra range syntax");
  if (options.paperSize !== undefined && !["A4", "Letter", "A5"].includes(options.paperSize as string)) throw new Error("printOptions.paperSize must be A4, Letter, or A5");
  if (options.layout !== undefined && !["portrait", "landscape"].includes(options.layout as string)) throw new Error("printOptions.layout must be portrait or landscape");
  if (options.fitMode !== undefined && !["fit", "noscale", "shrink"].includes(options.fitMode as string)) throw new Error("printOptions.fitMode must be fit, noscale, or shrink");
  return value as PrintOptions;
}

export function composePrintSettings(options?: PrintOptions, stored?: PrintOptions): string {
  const resolved = { ...defaultPrintOptions, ...stored, ...options };
  const range = resolved.pageRange === undefined ? "" : `${resolved.pageRange},`;
  return `${resolved.copies}x,${range}paper=${resolved.paperSize},${resolved.layout},${resolved.fitMode},simplex`;
}

type SpawnProcess = (command: string, args: readonly string[]) => ChildProcess;

export class PrintService {
  constructor(
    private readonly repository: AutomationJobRepository,
    private readonly options: { printerName: string; scriptPath: string; timeoutMs?: number; spawnProcess?: SpawnProcess },
  ) {}

  async print(jobId: string, options?: PrintOptions): Promise<PrintOutcome> {
    const job = this.repository.getById(jobId);
    const outcome = await this.tryPrint(job?.finalFile?.path, options, job?.printOptions);
    console.info(`[JOB ${jobId}] print ${new Date().toISOString()} printer=${this.options.printerName || "(unset)"} outcome=${outcome}`);
    return outcome;
  }

  private async tryPrint(finalPath: string | undefined, options?: PrintOptions, stored?: PrintOptions): Promise<PrintOutcome> {
    if (!finalPath || !this.options.printerName.trim()) return "PRINT_FAILED";
    try {
      if (options !== undefined) validatePrintOptions(options);
      if (stored !== undefined) validatePrintOptions(stored);
    } catch { return "PRINT_FAILED"; }
    try { await access(finalPath, constants.F_OK); } catch { return "PRINT_FAILED"; }
    const spawnProcess = this.options.spawnProcess ?? ((command, args) => spawn(command, args, { stdio: "ignore", shell: false }));
    try {
      const printSettings = options === undefined && stored === undefined ? "simplex" : composePrintSettings(options, stored);
      const child = spawnProcess("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", this.options.scriptPath, "-FilePath", finalPath, "-PrinterName", this.options.printerName, "-PrintSettings", printSettings]);
      return await new Promise<PrintOutcome>((resolve) => {
        const timer = setTimeout(() => { child.kill(); resolve("PRINT_FAILED"); }, this.options.timeoutMs ?? 30_000);
        child.once("error", () => { clearTimeout(timer); resolve("PRINT_FAILED"); });
        child.once("exit", (code) => { clearTimeout(timer); resolve(code === 0 ? "COMPLETED" : "PRINT_FAILED"); });
      });
    } catch { return "PRINT_FAILED"; }
  }
}
