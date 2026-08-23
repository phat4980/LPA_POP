import type { Page } from "playwright";
import { DatePicker } from "../components/DatePicker.js";
import { Pagination, type PaginationState } from "../components/Pagination.js";
import { poInboxLocators } from "../locators/poInboxLocators.js";
import { BasePage } from "./BasePage.js";

export type POInboxSearchResult =
  | { status: "results-loaded"; resultCount: number }
  | { status: "no-results"; resultCount: 0 };

export type POInboxSelectionResult =
  | { status: "selected"; selectableCount: number; selectedCount: number }
  | { status: "no-records"; selectableCount: 0; selectedCount: 0 };

export type BatchPdfResult = {
  page: Page;
  responseContentType: string;
};

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

  async selectDeliveryDate(targetDate: Date): Promise<void> {
    const input = this.page.locator(poInboxLocators.deliveryDateFrom.selector);
    await new DatePicker(this.page, input).selectDate(targetDate);
  }

  async getDeliveryDateValue(): Promise<string> {
    return this.page.locator(poInboxLocators.deliveryDateFrom.selector).inputValue();
  }

  async verifyUsable(): Promise<void> {
    await this.verifyLoaded();
  }

  async search(): Promise<POInboxSearchResult> {
    const searchButton = this.page.getByText(poInboxLocators.search.text, {
      exact: true,
    });
    if (await searchButton.count() !== 1) {
      throw new Error("Circle K PO Inbox search action is not uniquely identifiable.");
    }

    await searchButton.click();

    const resultArea = this.page.locator(poInboxLocators.resultArea.selector);
    const resultTable = this.page.locator(poInboxLocators.resultTable.selector);
    const resultRows = resultTable.locator(poInboxLocators.resultRow.selector);
    await resultArea.waitFor({ state: "visible" });
    await resultTable.waitFor({ state: "visible" });
    await resultTable.locator("tbody").waitFor({ state: "visible" });

    const totalRecords = await this.readNumericValue(poInboxLocators.resultTotal.selector);
    const pageSize = await this.readNumericValue(poInboxLocators.pageSize.selector);
    const expectedRows = Math.min(totalRecords, pageSize);
    if (expectedRows > 0) {
      await this.page.waitForFunction(
        ({ selector, expected }) => document.querySelectorAll(selector).length >= expected,
        { selector: `${poInboxLocators.resultTable.selector} ${poInboxLocators.resultRow.selector}`, expected: expectedRows },
      );
    }

    const resultCount = await resultRows.count();
    if (resultCount === 0) {
      return { status: "no-results", resultCount: 0 };
    }

    return { status: "results-loaded", resultCount };
  }

  async selectAllCurrentPage(): Promise<POInboxSelectionResult> {
    const resultTable = this.page.locator(poInboxLocators.resultTable.selector);
    const selectableRows = resultTable.locator(poInboxLocators.selectableRowCheckbox.selector);
    const selectableCount = await selectableRows.count();
    if (selectableCount === 0) {
      return { status: "no-records", selectableCount: 0, selectedCount: 0 };
    }

    const selectAll = this.page.getByTitle(poInboxLocators.selectAll.title);
    if (await selectAll.count() !== 1) {
      throw new Error("Circle K PO Inbox Select All action is not uniquely identifiable.");
    }

    await selectAll.check();
    await this.page.waitForFunction(
      ({ selector, expected }) => document.querySelectorAll(`${selector}:checked`).length === expected,
      { selector: `${poInboxLocators.resultTable.selector} ${poInboxLocators.selectableRowCheckbox.selector}`, expected: selectableCount },
    );
    const selectedCount = await resultTable.locator(
      `${poInboxLocators.selectableRowCheckbox.selector}:checked`,
    ).count();
    if (selectedCount !== selectableCount) {
      throw new Error("Circle K PO Inbox did not select all current-page PO records.");
    }

    return { status: "selected", selectableCount, selectedCount };
  }

  async getPaginationState(): Promise<PaginationState> {
    return new Pagination(this.page).getState();
  }

  async goToNextPage(): Promise<PaginationState> {
    return new Pagination(this.page).goToNextPage();
  }

  async generateBatchPdf(): Promise<BatchPdfResult> {
    const batchPrint = this.page.getByText(poInboxLocators.batchPrint.text, {
      exact: true,
    });
    if (await batchPrint.count() !== 1) {
      throw new Error("Circle K batch PDF action is not uniquely identifiable.");
    }

    const context = this.page.context();
    const [pdfPage, pdfResponse] = await Promise.all([
      context.waitForEvent("page"),
      context.waitForEvent("response", {
        predicate: (response) => response.url().includes("/trade/poDetails/printBatch")
          && response.headers()["content-type"]?.toLowerCase().includes("application/pdf") === true,
      }),
      batchPrint.click(),
    ]);

    await pdfPage.waitForLoadState("domcontentloaded");
    if (!pdfPage.url().includes("/trade/poDetails/printBatch")) {
      throw new Error("Circle K batch print opened an unexpected page.");
    }

    return {
      page: pdfPage,
      responseContentType: pdfResponse.headers()["content-type"] ?? "",
    };
  }

  private async readNumericValue(selector: string): Promise<number> {
    const value = await this.page.locator(selector).inputValue();
    const numericValue = Number(value);
    return Number.isFinite(numericValue) && numericValue >= 0 ? numericValue : 0;
  }

  private async verifyLoaded(): Promise<void> {
    await this.waitForPageReady();
    const pageTitle = await this.page.title();
    if (!poInboxLocators.inboxPageMarker.title.test(pageTitle.trim())) {
      throw new Error("Circle K PO Inbox page was not loaded.");
    }
  }
}