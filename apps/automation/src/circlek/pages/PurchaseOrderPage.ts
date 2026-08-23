import type { Page } from "playwright";
import { BasePage } from "./BasePage.js";
import { purchaseOrderLocators } from "../locators/purchaseOrderLocators.js";

export class PurchaseOrderPage extends BasePage {
  async selectDeliveryDate(deliveryDate: string): Promise<void> {
    await this.page.getByLabel(purchaseOrderLocators.deliveryDate.label).fill(deliveryDate);
  }

  async selectAll(): Promise<void> {
    await this.page.getByRole(purchaseOrderLocators.selectAll.role, {
      name: purchaseOrderLocators.selectAll.name,
    }).check();
  }

  async hasNextPage(): Promise<boolean> {
    return this.page.getByRole(purchaseOrderLocators.nextPage.role, {
      name: purchaseOrderLocators.nextPage.name,
    }).isEnabled();
  }

  async goToNextPage(): Promise<void> {
    await this.page.getByRole(purchaseOrderLocators.nextPage.role, {
      name: purchaseOrderLocators.nextPage.name,
    }).click();
  }

  async startPrint(): Promise<void> {
    await this.page.getByRole(purchaseOrderLocators.print.role, {
      name: purchaseOrderLocators.print.name,
    }).click();
  }
}
