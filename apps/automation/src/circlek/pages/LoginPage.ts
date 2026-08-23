import type { Page } from "playwright";
import { BasePage } from "./BasePage.js";

export class LoginPage extends BasePage {
  constructor(page: Page, private readonly baseUrl: string) {
    super(page);
  }

  async open(): Promise<void> {
    if (!this.baseUrl) {
      throw new Error("CIRCLEK_BASE_URL is required before opening Circle K.");
    }
    await this.page.goto(this.baseUrl);
    await this.waitForPageReady();
  }

  async login(username: string, password: string): Promise<void> {
    throw new Error("Circle K login selectors are pending live-site discovery.");
  }
}
