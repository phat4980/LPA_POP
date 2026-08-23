import { BrowserSession } from "../browser/BrowserSession.js";
import { loadConfig } from "../config/environment.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage } from "../circlek/pages/POInboxPage.js";
import { getNextCalendarDay } from "../utils/date.js";

const config = loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" });
const session = new BrowserSession(config);

try {
  const page = await session.createPage();
  const loginPage = new LoginPage(page, config);
  const poInboxPage = new POInboxPage(page);

  await loginPage.open();
  await loginPage.login();
  await poInboxPage.open();
  await poInboxPage.selectDeliveryDate(getNextCalendarDay());
  await poInboxPage.search();

  const initial = await poInboxPage.getPaginationState();
  console.log(`Initial page: ${initial.currentPage}`);
  console.log(`Detected total pages: ${initial.totalPages ?? "unavailable"}`);
  console.log(`Next page existed: ${initial.hasNextPage ? "yes" : "no"}`);

  if (initial.hasNextPage) {
    const next = await poInboxPage.goToNextPage();
    console.log(`Navigated to page: ${next.currentPage}`);
    console.log("Page-change verification: passed");
  } else {
    console.log("Page-change verification: not applicable (final page)");
  }

  await new Promise((resolve) => setTimeout(resolve, 5_000));
} catch {
  console.error("Circle K pagination smoke failed.");
  process.exitCode = 1;
} finally {
  await session.close();
  console.log("Cleanup: succeeded");
}