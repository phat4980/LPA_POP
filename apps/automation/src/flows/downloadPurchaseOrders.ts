import type { Page } from "playwright";
import { PurchaseOrderPage } from "../circlek/pages/PurchaseOrderPage.js";

export type DownloadPurchaseOrdersInput = {
  page: Page;
  deliveryDate: string;
};

export async function downloadPurchaseOrders(input: DownloadPurchaseOrdersInput): Promise<void> {
  const purchaseOrderPage = new PurchaseOrderPage(input.page);
  await purchaseOrderPage.selectDeliveryDate(input.deliveryDate);
  await purchaseOrderPage.selectAll();
  await purchaseOrderPage.startPrint();
}
