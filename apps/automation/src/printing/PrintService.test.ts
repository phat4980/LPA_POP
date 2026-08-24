import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { resolve } from "node:path";
import test from "node:test";
import { AutomationJobStatus } from "../jobs/AutomationJob.js";
import { InMemoryAutomationJobRepository } from "../jobs/InMemoryAutomationJobRepository.js";
import { composePrintSettings, PrintService, validatePrintOptions } from "./PrintService.js";

test("composes print settings without an empty page range", () => {
  assert.equal(composePrintSettings({ copies: 3, pageRange: "1-2,4", paperSize: "Letter", layout: "landscape", fitMode: "shrink" }), "3x,1-2,4,paper=Letter,landscape,shrink,simplex");
  assert.equal(composePrintSettings({ paperSize: "A4" }), "2x,paper=A4,portrait,fit,simplex");
});

test("validates every print option field", () => {
  const invalid = [
    { copies: 0 }, { copies: 1.5 }, { pageRange: "1,,2" },
    { paperSize: "A3" }, { layout: "diagonal" }, { fitMode: "scale" },
    { "-print-settings": "duplex" },
  ];
  for (const options of invalid) assert.throws(() => validatePrintOptions(options));
});

test("uses stored options, explicit options, and the legacy optionless path", async () => {
  const filePath = resolve(process.cwd(), "../../scripts/vendor/test-fixture.pdf");
  const repository = new InMemoryAutomationJobRepository();
  repository.create({
      automationJobId: "print-test",
      deliveryDate: "2026-08-24",
      status: AutomationJobStatus.FINAL_READY,
      currentStep: "FINALIZE",
      progress: 80,
      downloadedCount: 1,
      totalCount: 1,
      pythonJobId: null,
      sourceFiles: [],
      finalFile: { path: filePath, name: "final.pdf" },
      autoPrint: false,
      printOptions: { copies: 4, paperSize: "Letter" },
      error: null,
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
  });
  const calls: readonly string[][] = [];
  const spawnProcess = (_command: string, args: readonly string[]) => {
      (calls as string[][]).push([...args]);
      const child = new EventEmitter() as EventEmitter & { kill(): void };
      child.kill = () => undefined;
      queueMicrotask(() => child.emit("exit", 0));
      return child as never;
  };
  const service = new PrintService(repository, { printerName: "Brother HL-L2320D series", scriptPath: "print.ps1", spawnProcess });
  assert.equal(await service.print("print-test"), "COMPLETED");
  assert.equal(calls[0].at(-1), "4x,paper=Letter,portrait,fit,simplex");
  assert.equal(await service.print("print-test", { copies: 2, layout: "landscape" }), "COMPLETED");
  assert.equal(calls[1].at(-1), "2x,paper=Letter,landscape,fit,simplex");

  repository.update({ ...repository.getById("print-test")!, printOptions: undefined });
  assert.equal(await service.print("print-test"), "COMPLETED");
  assert.equal(calls[2].at(-1), "simplex");
});
