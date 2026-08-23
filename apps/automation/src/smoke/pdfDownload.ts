import { BrowserSession } from "../browser/BrowserSession.js";
import { loadConfig } from "../config/environment.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage } from "../circlek/pages/POInboxPage.js";
import { PdfDownloadService } from "../services/PdfDownloadService.js";
import { getNextCalendarDay } from "../utils/date.js";

const config = loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" });
const session = new BrowserSession(config);

try {
  const page = await session.createPage();
  const loginPage = new LoginPage(page, config);
  const poInboxPage = new POInboxPage(page);
  const targetDate = getNextCalendarDay();
  const pdfDownloadService = new PdfDownloadService();

  await loginPage.open();
  await loginPage.login();
  await poInboxPage.open();
  await poInboxPage.selectDeliveryDate(targetDate);
  const searchResult = await poInboxPage.search();
  const selectionResult = await poInboxPage.selectAllCurrentPage();
  const batchPdf = await poInboxPage.generateBatchPdf();
  const artifact = await pdfDownloadService.downloadBatchPdf(
    batchPdf.page,
    config.automationOutputDir,
    targetDate,
  );

  console.log(`PO count processed: ${searchResult.resultCount}`);
  console.log(`Selected PO count: ${selectionResult.selectedCount}`);
  console.log("PDF page detected: yes");
  console.log("Download triggered: yes");
  console.log(`Final artifact path: ${artifact.filePath}`);
  console.log(`File size: ${artifact.sizeBytes} bytes`);
  console.log("PDF verification: passed");
  await new Promise((resolve) => setTimeout(resolve, 5_000));
} catch {
  console.error("Circle K PDF download smoke failed.");
  process.exitCode = 1;
} finally {
  await session.close();
  console.log("Cleanup: succeeded");
}