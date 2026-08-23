import type { Page } from "playwright";
import { poInboxLocators } from "../locators/poInboxLocators.js";

export type PaginationState = {
  currentPage: number;
  totalPages: number | undefined;
  hasNextPage: boolean;
  rowCount: number;
  columnNames: string[];
};

export class Pagination {
  constructor(private readonly page: Page) {}

  async getCurrentPage(): Promise<number> {
    const value = await this.page.locator(poInboxLocators.pagination.currentPage.selector).inputValue();
    const currentPage = Number(value);
    if (!Number.isInteger(currentPage) || currentPage < 0) {
      throw new Error("Circle K pagination current page could not be read.");
    }

    return currentPage + 1;
  }

  async getState(): Promise<PaginationState> {
    const currentPage = await this.getCurrentPage();
    const totalRecords = await this.readNumber(poInboxLocators.pagination.totalRecords.selector);
    const pageSize = await this.readNumber(poInboxLocators.pagination.pageSize.selector);
    const totalPages = totalRecords > 0 && pageSize > 0
      ? Math.ceil(totalRecords / pageSize)
      : undefined;
    const nextPage = this.page.getByText(poInboxLocators.pagination.nextPage.text, { exact: true });
    const nextAvailable = await nextPage.count() === 1 && await nextPage.isVisible();
    const disabled = nextAvailable
      ? await nextPage.evaluate((element) => element.parentElement?.classList.contains("disabled") === true
        || element.getAttribute("aria-disabled") === "true")
      : true;

    const dataState = await this.readDataState();

    return {
      currentPage,
      totalPages,
      hasNextPage: !disabled && (totalPages === undefined || currentPage < totalPages),
      rowCount: dataState.rowCount,
      columnNames: dataState.columnNames,
    };
  }

  async goToNextPage(): Promise<PaginationState> {
    const before = await this.getState();
    if (!before.hasNextPage) {
      throw new Error("Circle K pagination has no next page available.");
    }

    const nextPage = this.page.getByText(poInboxLocators.pagination.nextPage.text, { exact: true });
    const resultRows = this.page.locator(
      `${poInboxLocators.resultTable.selector} ${poInboxLocators.resultRow.selector}`,
    );
    const previousDataFingerprint = await this.readDataFingerprint();
    await Promise.all([
      this.page.waitForLoadState("domcontentloaded"),
      nextPage.click(),
    ]);
    await this.page.waitForFunction(
      ({ selector, previousPage }) => document.querySelector<HTMLInputElement>(selector)?.value !== String(previousPage),
      { selector: poInboxLocators.pagination.currentPage.selector, previousPage: before.currentPage - 1 },
    );
    await this.page.locator(poInboxLocators.resultTable.selector).waitFor({ state: "visible" });

    const after = await this.getState();
    if (after.currentPage === before.currentPage) {
      throw new Error("Circle K pagination did not change page.");
    }
    const totalRecords = await this.readNumber(poInboxLocators.pagination.totalRecords.selector);
    const pageSize = await this.readNumber(poInboxLocators.pagination.pageSize.selector);
    const expectedRows = Math.max(Math.min(pageSize, totalRecords - ((after.currentPage - 1) * pageSize)), 0);
    await this.waitForFreshData(expectedRows, previousDataFingerprint);

    return this.getState();
  }

  private async waitForFreshData(expectedRows: number, previousDataFingerprint: string): Promise<void> {
    await this.page.waitForFunction(
      ({ tableSelector, rowSelector, expected, previousFingerprint }) => {
        const table = document.querySelector(tableSelector);
        const rows = Array.from(document.querySelectorAll(rowSelector));
        const columnNames = Array.from(table?.querySelectorAll("thead th") ?? [])
          .map((header) => header.textContent?.trim() ?? "")
          .filter(Boolean);
        const rowValues = rows.map((row) => row.textContent?.trim() ?? "");
        const fingerprint = JSON.stringify({ columnNames, rowValues });
        return rows.length === expected && fingerprint !== previousFingerprint;
      },
      {
        tableSelector: poInboxLocators.resultTable.selector,
        rowSelector: `${poInboxLocators.resultTable.selector} ${poInboxLocators.resultRow.selector}`,
        expected: expectedRows,
        previousFingerprint: previousDataFingerprint,
      },
    );
  }

  private async readDataFingerprint(): Promise<string> {
    return this.page.locator(poInboxLocators.resultTable.selector).evaluate((table) => {
      const columnNames = Array.from(table.querySelectorAll("thead th"))
        .map((header) => header.textContent?.trim() ?? "")
        .filter(Boolean);
      const rowValues = Array.from(table.querySelectorAll('tbody tr:has(input[type="checkbox"])'))
        .map((row) => row.textContent?.trim() ?? "");
      return JSON.stringify({ columnNames, rowValues });
    });
  }

  private async readDataState(): Promise<{ rowCount: number; columnNames: string[] }> {
    return this.page.locator(poInboxLocators.resultTable.selector).evaluate((table) => ({
      rowCount: table.querySelectorAll('tbody tr:has(input[type="checkbox"])').length,
      columnNames: Array.from(table.querySelectorAll("thead th"))
        .map((header) => header.textContent?.trim() ?? "")
        .filter(Boolean),
    }));
  }

  private async readNumber(selector: string): Promise<number> {
    const value = await this.page.locator(selector).inputValue();
    const numberValue = Number(value);
    return Number.isFinite(numberValue) && numberValue >= 0 ? numberValue : 0;
  }
}
