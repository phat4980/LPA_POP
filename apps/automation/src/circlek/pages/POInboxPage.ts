import type { Page } from "playwright";
import { poInboxLocators } from "../locators/poInboxLocators.js";
import { BasePage } from "./BasePage.js";

export class POInboxPage extends BasePage {
  async open(): Promise<void> {
    const documentsMenu = this.page.getByRole(poInboxLocators.documentsMenu.role, {
      name: poInboxLocators.documentsMenu.name,
      exact: true,
    });
    await documentsMenu.hover();

    const inboxOrdersMenuItem = this.page.getByRole(poInboxLocators.inboxOrdersMenuItem.role, {
      name: poInboxLocators.inboxOrdersMenuItem.name,
      exact: true,
    });
    await inboxOrdersMenuItem.click();
    await this.verifyLoaded();
  }

  private async verifyLoaded(): Promise<void> {
    await this.waitForPageReady();
    const pageTitle = await this.page.title();
    if (!poInboxLocators.inboxPageMarker.title.test(pageTitle.trim())) {
      throw new Error("Circle K PO Inbox page was not loaded.");
    }
  }
}