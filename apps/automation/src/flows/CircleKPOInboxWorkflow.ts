import type { AutomationConfig } from "../config/environment.js";
import { BrowserSession } from "../browser/BrowserSession.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage } from "../circlek/pages/POInboxPage.js";
import { PdfDownloadService, type DownloadedPdfArtifact } from "../services/PdfDownloadService.js";
import { getNextCalendarDay } from "../utils/date.js";

export type CircleKPOInboxPageResult = {
  pageNumber: number;
  poCount: number;
  pdfGenerated: boolean;
  artifact?: DownloadedPdfArtifact;
};

export type CircleKPOInboxWorkflowResult = {
  targetDate: string;
  pagesProcessed: number;
  totalPOsProcessed: number;
  pdfsGenerated: number;
  pdfsDownloaded: number;
  artifacts: string[];
  pagesWithNoPORecords: number[];
  pageResults: CircleKPOInboxPageResult[];
  failures: string[];
  success: boolean;
};

export class CircleKPOInboxWorkflow {
  private readonly session: BrowserSession;
  private readonly pdfDownloadService = new PdfDownloadService();

  constructor(private readonly config: AutomationConfig) {
    this.session = new BrowserSession(config);
  }

  async run(): Promise<CircleKPOInboxWorkflowResult> {
    const targetDate = getNextCalendarDay();
    const result: CircleKPOInboxWorkflowResult = {
      targetDate: this.formatDate(targetDate),
      pagesProcessed: 0,
      totalPOsProcessed: 0,
      pdfsGenerated: 0,
      pdfsDownloaded: 0,
      artifacts: [],
      pagesWithNoPORecords: [],
      pageResults: [],
      failures: [],
      success: false,
    };

    try {
      const page = await this.session.createPage();
      const loginPage = new LoginPage(page, this.config);
      const poInboxPage = new POInboxPage(page);

      await loginPage.open();
      await loginPage.login();
      await poInboxPage.open();
      await poInboxPage.selectDeliveryDate(targetDate);
      const searchResult = await poInboxPage.search();

      if (searchResult.status === "no-results") {
        result.pagesProcessed = 1;
        result.pagesWithNoPORecords.push(1);
        result.success = true;
        return result;
      }

      let pagination = await poInboxPage.getPaginationState();
      const visitedPages = new Set<number>();

      while (true) {
        if (visitedPages.has(pagination.currentPage)) {
          throw new Error(`Pagination revisited page ${pagination.currentPage}.`);
        }
        visitedPages.add(pagination.currentPage);

        const pageResult = await this.processCurrentPage(poInboxPage, pagination.currentPage, targetDate);
        result.pagesProcessed += 1;
        result.totalPOsProcessed += pageResult.poCount;
        result.pageResults.push(pageResult);
        if (pageResult.poCount === 0) {
          result.pagesWithNoPORecords.push(pageResult.pageNumber);
        }
        if (pageResult.pdfGenerated) {
          result.pdfsGenerated += 1;
        }
        if (pageResult.artifact) {
          result.pdfsDownloaded += 1;
          result.artifacts.push(pageResult.artifact.filePath);
        }

        if (!pagination.hasNextPage) {
          break;
        }
        pagination = await poInboxPage.goToNextPage();
      }

      result.success = true;
      return result;
    } catch (error) {
      result.failures.push(error instanceof Error ? error.message : "Unknown workflow failure.");
      return result;
    } finally {
      await this.session.close();
    }
  }

  private async processCurrentPage(
    poInboxPage: POInboxPage,
    pageNumber: number,
    targetDate: Date,
  ): Promise<CircleKPOInboxPageResult> {
    const selection = await poInboxPage.selectAllCurrentPage();
    if (selection.status === "no-records") {
      return { pageNumber, poCount: 0, pdfGenerated: false };
    }

    const batchPdf = await poInboxPage.generateBatchPdf();
    let artifact: DownloadedPdfArtifact | undefined;
    try {
      artifact = await this.pdfDownloadService.downloadBatchPdf(
        batchPdf.page,
        this.config.automationOutputDir,
        targetDate,
        pageNumber,
      );
    } finally {
      await batchPdf.page.close();
    }

    await poInboxPage.verifyUsable();
    return {
      pageNumber,
      poCount: selection.selectedCount,
      pdfGenerated: true,
      artifact,
    };
  }

  private formatDate(date: Date): string {
    return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
      .map((part, index) => index === 0 ? String(part) : String(part).padStart(2, "0"))
      .join("-");
  }
}