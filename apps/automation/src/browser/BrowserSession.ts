import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import type { AutomationConfig } from "../config/environment.js";

export class BrowserSession {
  private browser?: Browser;
  private context?: BrowserContext;

  constructor(private readonly config: Pick<AutomationConfig, "headless">) {}

  async launch(): Promise<Browser> {
    if (!this.browser) {
      this.browser = await chromium.launch({
        headless: this.config.headless,
        args: this.config.headless ? [] : ["--start-maximized"],
      });
    }

    return this.browser;
  }

  async createContext(): Promise<BrowserContext> {
    const browser = await this.launch();

    if (!this.context) {
      this.context = await browser.newContext({
        viewport: this.config.headless ? { width: 1280, height: 720 } : null,
      });
    }

    return this.context;
  }

  async createPage(): Promise<Page> {
    const context = await this.createContext();
    return context.newPage();
  }

  async closeContext(): Promise<void> {
    if (this.context) {
      await this.context.close();
      this.context = undefined;
    }
  }

  async closeBrowser(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
      this.browser = undefined;
    }
  }

  async close(): Promise<void> {
    await this.closeContext();
    await this.closeBrowser();
  }
}