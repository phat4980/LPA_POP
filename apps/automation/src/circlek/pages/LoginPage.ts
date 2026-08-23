import type { Page } from "playwright";
import type { AutomationConfig } from "../../config/environment.js";
import { BasePage } from "./BasePage.js";
import { loginLocators } from "../locators/loginLocators.js";

export class LoginPage extends BasePage {
  constructor(
    page: Page,
    private readonly config: Pick<AutomationConfig, "circleKBaseUrl" | "circleKUsername" | "circleKPassword">,
  ) {
    super(page);
  }

  async open(): Promise<void> {
    await this.page.goto(this.config.circleKBaseUrl);
    await this.waitForPageReady();
  }

  async login(): Promise<void> {
    const usernameField = this.page.getByRole(loginLocators.username.role, {
      name: loginLocators.username.name,
    });
    const passwordField = this.page.getByRole(loginLocators.password.role, {
      name: loginLocators.password.name,
    });

    if (await usernameField.count() !== 1 || await passwordField.count() !== 1) {
      throw new Error("Circle K login form fields are not uniquely identifiable.");
    }
    await usernameField.fill(this.config.circleKUsername);
    await passwordField.fill(this.config.circleKPassword);

    await this.page.getByRole(loginLocators.submit.role, {
      name: loginLocators.submit.name,
    }).click();

    await this.verifyAuthenticated();
  }

  private async verifyAuthenticated(): Promise<void> {
    const loginPath = new URL(this.config.circleKBaseUrl).pathname;
    await this.page.waitForURL((url) => url.pathname !== loginPath, {
      waitUntil: "domcontentloaded",
    });

    const loginButton = this.page.getByRole(loginLocators.submit.role, {
      name: loginLocators.submit.name,
    });
    if (await loginButton.isVisible()) {
      throw new Error("Circle K authentication did not leave the login page.");
    }
    if ((await this.page.title()).trim().toLowerCase() === "login page") {
      throw new Error("Circle K authentication did not reach an authenticated page.");
    }
  }

  async captureFailureScreenshot(filePath: string): Promise<void> {
    const usernameField = this.page.getByRole(loginLocators.username.role, {
      name: loginLocators.username.name,
    });
    const passwordField = this.page.getByRole(loginLocators.password.role, {
      name: loginLocators.password.name,
    });

    if (await usernameField.count() === 1) {
      await usernameField.fill("");
    }
    if (await passwordField.count() === 1) {
      await passwordField.fill("");
    }
    await this.page.screenshot({ path: filePath });
  }
}
