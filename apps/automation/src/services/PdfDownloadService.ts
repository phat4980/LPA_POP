import { stat } from "node:fs/promises";
import type { Page } from "playwright";
import { assertPdfOutputPath, createPdfOutputPath } from "../utils/pdfFile.js";

export type DownloadedPdfArtifact = {
  filePath: string;
  fileName: string;
  sizeBytes: number;
};

export class PdfDownloadService {
  async downloadBatchPdf(
    pdfPage: Page,
    outputDir: string,
    date: Date,
    pageNumber?: number,
  ): Promise<DownloadedPdfArtifact> {
    const filePath = await createPdfOutputPath(outputDir, date, pageNumber);
    assertPdfOutputPath(filePath);

    const downloadPromise = pdfPage.waitForEvent("download");
    await pdfPage.evaluate(() => {
      const downloadLink = document.createElement("a");
      downloadLink.href = window.location.href;
      downloadLink.download = "circlek-po-inbox-batch.pdf";
      document.body.appendChild(downloadLink);
      downloadLink.click();
      downloadLink.remove();
    });
    const download = await downloadPromise;
    await download.saveAs(filePath);

    const fileStats = await stat(filePath);
    if (fileStats.size <= 0) {
      throw new Error("Downloaded PDF artifact is empty.");
    }

    return {
      filePath,
      fileName: filePath.split(/[\\/]/).pop() ?? filePath,
      sizeBytes: fileStats.size,
    };
  }
}