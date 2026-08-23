import type { Page } from "playwright";
import { downloadPurchaseOrders } from "../flows/downloadPurchaseOrders.js";

export type ProcessPOJobInput = {
  page: Page;
  deliveryDate: string;
};

export class ProcessPOJob {
  async run(input: ProcessPOJobInput): Promise<void> {
    await downloadPurchaseOrders(input);
  }
}
