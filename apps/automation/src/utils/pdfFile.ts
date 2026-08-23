import { access, mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

export async function createPdfOutputPath(
  outputDir: string,
  date: Date,
  pageNumber?: number,
): Promise<string> {
  const resolvedOutputDir = resolve(outputDir);
  await mkdir(resolvedOutputDir, { recursive: true });

  const datePart = [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((part, index) => index === 0 ? String(part) : String(part).padStart(2, "0"))
    .join("-");
  const pagePart = pageNumber === undefined ? "" : `-page-${pageNumber}`;
  const baseName = `circlek-po-inbox-batch-${datePart}${pagePart}`;

  for (let suffix = 0; ; suffix += 1) {
    const name = suffix === 0 ? `${baseName}.pdf` : `${baseName}-${suffix}.pdf`;
    const candidate = join(resolvedOutputDir, name);
    try {
      await access(candidate);
    } catch {
      return candidate;
    }
  }
}

export function assertPdfOutputPath(filePath: string): void {
  if (dirname(filePath) === filePath || !filePath.toLowerCase().endsWith(".pdf")) {
    throw new Error("PDF output path must be a filesystem PDF path.");
  }
}

export async function createFinalPdfOutputPath(outputDir: string, date: Date): Promise<string> {
  return createPdfOutputPath(outputDir, date, undefined).then((path) => path.replace("circlek-po-inbox-batch-", "circlek-po-final-"));
}