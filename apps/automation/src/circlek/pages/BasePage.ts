import type { Page } from "playwright";

export abstract class BasePage {
  constructor(protected readonly page: Page) {}

  protected async waitForPageReady(): Promise<void> {
    await this.page.waitForLoadState("domcontentloaded");
  }
}
