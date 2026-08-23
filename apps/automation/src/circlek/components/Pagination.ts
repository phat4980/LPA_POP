import type { Page } from "playwright";
import { purchaseOrderLocators } from "../locators/purchaseOrderLocators.js";

export class Pagination {
  constructor(private readonly page: Page) {}

  async hasNextPage(): Promise<boolean> {
    return this.page.getByRole(purchaseOrderLocators.nextPage.role, {
      name: purchaseOrderLocators.nextPage.name,
    }).isEnabled();
  }

  async next(): Promise<void> {
    await this.page.getByRole(purchaseOrderLocators.nextPage.role, {
      name: purchaseOrderLocators.nextPage.name,
    }).click();
  }
}
