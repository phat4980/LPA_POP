import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { BrowserSession } from "../browser/BrowserSession.js";
import { loadConfig } from "../config/environment.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";

const config = loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" });
const session = new BrowserSession(config);
let loginPage: LoginPage | undefined;

try {
  const page = await session.createPage();
  loginPage = new LoginPage(page, config);

  await loginPage.open();
  await loginPage.login();
  console.log("Circle K login smoke succeeded.");
  await new Promise((resolve) => setTimeout(resolve, 5_000));
} catch {
  if (loginPage) {
    try {
      const failureDir = resolve(config.automationOutputDir, "login-smoke-failures");
      await mkdir(failureDir, { recursive: true });
      await loginPage.captureFailureScreenshot(resolve(failureDir, `${Date.now()}.png`));
    } catch {
    }
  }
  console.error("Circle K login smoke failed.");
  process.exitCode = 1;
} finally {
  await session.close();
}