import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import type { AutomationJobRepository } from "../jobs/AutomationJobRepository.js";

export type PrintOutcome = "COMPLETED" | "PRINT_FAILED";
type SpawnProcess = (command: string, args: readonly string[]) => ChildProcess;

export class PrintService {
  constructor(
    private readonly repository: AutomationJobRepository,
    private readonly options: { printerName: string; scriptPath: string; timeoutMs?: number; spawnProcess?: SpawnProcess },
  ) {}

  async print(jobId: string): Promise<PrintOutcome> {
    const job = this.repository.getById(jobId);
    const outcome = await this.tryPrint(job?.finalFile?.path);
    console.info(`[JOB ${jobId}] print ${new Date().toISOString()} printer=${this.options.printerName || "(unset)"} outcome=${outcome}`);
    return outcome;
  }

  private async tryPrint(finalPath: string | undefined): Promise<PrintOutcome> {
    if (!finalPath || !this.options.printerName.trim()) return "PRINT_FAILED";
    try { await access(finalPath, constants.F_OK); } catch { return "PRINT_FAILED"; }
    const spawnProcess = this.options.spawnProcess ?? ((command, args) => spawn(command, args, { stdio: "ignore", shell: false }));
    try {
      const child = spawnProcess("powershell.exe", ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", this.options.scriptPath, "-FilePath", finalPath, "-PrinterName", this.options.printerName]);
      return await new Promise<PrintOutcome>((resolve) => {
        const timer = setTimeout(() => { child.kill(); resolve("PRINT_FAILED"); }, this.options.timeoutMs ?? 30_000);
        child.once("error", () => { clearTimeout(timer); resolve("PRINT_FAILED"); });
        child.once("exit", (code) => { clearTimeout(timer); resolve(code === 0 ? "COMPLETED" : "PRINT_FAILED"); });
      });
    } catch { return "PRINT_FAILED"; }
  }
}
