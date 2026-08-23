import { BrowserSession } from "../browser/BrowserSession.js";
import { loadConfig } from "../config/environment.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage } from "../circlek/pages/POInboxPage.js";

const config = loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" });
const session = new BrowserSession(config);

try {
  const page = await session.createPage();
  const loginPage = new LoginPage(page, config);
  const poInboxPage = new POInboxPage(page);

  await loginPage.open();
  await loginPage.login();
  await poInboxPage.open();
  console.log("Circle K PO Inbox smoke succeeded.");
  await new Promise((resolve) => setTimeout(resolve, 5_000));
} catch {
  console.error("Circle K PO Inbox smoke failed.");
  process.exitCode = 1;
} finally {
  await session.close();
}