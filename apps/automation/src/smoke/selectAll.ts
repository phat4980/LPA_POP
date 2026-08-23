import { BrowserSession } from "../browser/BrowserSession.js";
import { loadConfig } from "../config/environment.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage } from "../circlek/pages/POInboxPage.js";
import { getNextCalendarDay } from "../utils/date.js";

function formatDate(date: Date): string {
  return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
}

const config = loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" });
const session = new BrowserSession(config);

try {
  const page = await session.createPage();
  const loginPage = new LoginPage(page, config);
  const poInboxPage = new POInboxPage(page);
  const targetDate = getNextCalendarDay();

  await loginPage.open();
  await loginPage.login();
  await poInboxPage.open();
  await poInboxPage.selectDeliveryDate(targetDate);
  const searchResult = await poInboxPage.search();
  const selectionResult = await poInboxPage.selectAllCurrentPage();

  console.log(`Calculated target date: ${formatDate(targetDate)}`);
  console.log(`Current-page PO count: ${searchResult.resultCount}`);
  console.log(`Selection state: ${selectionResult.status}`);
  console.log(`Selected PO count: ${selectionResult.selectedCount}`);
  console.log(`Selection verification: ${selectionResult.status === "no-records" || selectionResult.selectedCount === selectionResult.selectableCount ? "passed" : "failed"}`);
  await new Promise((resolve) => setTimeout(resolve, 5_000));
} catch {
  console.error("Circle K Select All smoke failed.");
  process.exitCode = 1;
} finally {
  await session.close();
  console.log("Cleanup: succeeded");
}