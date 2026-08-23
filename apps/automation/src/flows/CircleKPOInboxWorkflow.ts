import type { Page } from "playwright";
import type { AutomationConfig } from "../config/environment.js";
import { BrowserSession } from "../browser/BrowserSession.js";
import { LoginPage } from "../circlek/pages/LoginPage.js";
import { POInboxPage, type POInboxSearchResult } from "../circlek/pages/POInboxPage.js";
import type { PaginationState } from "../circlek/components/Pagination.js";
import { PdfDownloadService, type DownloadedPdfArtifact } from "../services/PdfDownloadService.js";
import { Web2Client, type Web2FinalArtifact } from "../services/Web2Client.js";
import { createFinalPdfOutputPath } from "../utils/pdfFile.js";
import { getNextCalendarDay } from "../utils/date.js";

export type CircleKPOInboxPageResult = { pageNumber: number; poCount: number; pdfGenerated: boolean; artifact?: DownloadedPdfArtifact };
export type CircleKPOInboxWorkflowResult = { targetDate: string; pagesProcessed: number; totalPOsProcessed: number; pdfsGenerated: number; pdfsDownloaded: number; artifacts: string[]; finalFile?: Web2FinalArtifact; pagesWithNoPORecords: number[]; pageResults: CircleKPOInboxPageResult[]; failures: string[]; success: boolean };
export type CircleKSessionContext = { session: BrowserSession; page: Page; poInboxPage: POInboxPage; targetDate: Date; searchResult: POInboxSearchResult; pagination: PaginationState | null; pdfDownloadService: PdfDownloadService };
export type CircleKDownloadResult = { pageResults: CircleKPOInboxPageResult[]; pagesWithNoPORecords: number[]; artifacts: DownloadedPdfArtifact[] };

/** Opens an authenticated PO Inbox search and leaves its session open for downloadCircleKSession. */
export async function loginToCircleK(config: AutomationConfig, targetDate: Date): Promise<CircleKSessionContext> {
  const session = new BrowserSession(config);
  try {
    const page = await session.createPage();
    const loginPage = new LoginPage(page, config);
    const poInboxPage = new POInboxPage(page);
    await loginPage.open(); await loginPage.login(); await poInboxPage.open(); await poInboxPage.selectDeliveryDate(targetDate);
    const searchResult = await poInboxPage.search();
    return { session, page, poInboxPage, targetDate, searchResult, pagination: null, pdfDownloadService: new PdfDownloadService() };
  } catch (error) { await session.close(); throw error; }
}

/** Processes the already-searched PO Inbox pages without logging in or searching again. */
export async function downloadCircleKSession(context: CircleKSessionContext, outputDir: string): Promise<CircleKDownloadResult> {
  if (context.searchResult.status === "no-results") return { pageResults: [{ pageNumber: 1, poCount: 0, pdfGenerated: false }], pagesWithNoPORecords: [1], artifacts: [] };
  const pageResults: CircleKPOInboxPageResult[] = [];
  const pagesWithNoPORecords: number[] = [];
  const artifacts: DownloadedPdfArtifact[] = [];
  let pagination = await context.poInboxPage.getPaginationState();
  context.pagination = pagination;
  const visitedPages = new Set<number>();
  while (true) {
    if (visitedPages.has(pagination.currentPage)) throw new Error(`Pagination revisited page ${pagination.currentPage}.`);
    visitedPages.add(pagination.currentPage);
    const pageResult = await processCurrentPage(context, pagination.currentPage, outputDir);
    pageResults.push(pageResult);
    if (pageResult.poCount === 0) pagesWithNoPORecords.push(pageResult.pageNumber);
    if (pageResult.artifact) artifacts.push(pageResult.artifact);
    if (!pagination.hasNextPage) break;
    pagination = await context.poInboxPage.goToNextPage(); context.pagination = pagination;
  }
  return { pageResults, pagesWithNoPORecords, artifacts };
}

export async function closeCircleKSession(context: CircleKSessionContext): Promise<void> { await context.session.close(); }

export class CircleKPOInboxWorkflow {
  private readonly web2Client: Web2Client;
  constructor(private readonly config: AutomationConfig) { this.web2Client = new Web2Client({ baseUrl: config.web2BaseUrl }); }
  async run(): Promise<CircleKPOInboxWorkflowResult> {
    const targetDate = getNextCalendarDay();
    const result: CircleKPOInboxWorkflowResult = { targetDate: formatDate(targetDate), pagesProcessed: 0, totalPOsProcessed: 0, pdfsGenerated: 0, pdfsDownloaded: 0, artifacts: [], finalFile: undefined, pagesWithNoPORecords: [], pageResults: [], failures: [], success: false };
    let context: CircleKSessionContext | undefined;
    try {
      context = await loginToCircleK(this.config, targetDate);
      if (context.searchResult.status === "no-results") { result.pagesProcessed = 1; result.pagesWithNoPORecords.push(1); result.success = true; return result; }
      if (!(await this.web2Client.healthCheck())) throw new Error("Web 2 health check failed.");
      const download = await downloadCircleKSession(context, this.config.automationOutputDir);
      result.pageResults = download.pageResults; result.pagesWithNoPORecords = download.pagesWithNoPORecords; result.pagesProcessed = download.pageResults.length;
      result.totalPOsProcessed = download.pageResults.reduce((total, page) => total + page.poCount, 0); result.pdfsGenerated = download.pageResults.filter((page) => page.pdfGenerated).length;
      result.pdfsDownloaded = download.artifacts.length; result.artifacts = download.artifacts.map((artifact) => artifact.filePath);
      const web2Job = await this.web2Client.createUploadJob(result.artifacts, this.config.web2ListFile);
      const completedJob = await this.web2Client.waitForCompletion(web2Job.id);
      result.finalFile = await this.web2Client.downloadFinalPdf(completedJob.id, await createFinalPdfOutputPath(this.config.automationOutputDir, targetDate)); result.success = true; return result;
    } catch (error) { result.failures.push(error instanceof Error ? error.message : "Unknown workflow failure."); return result; }
    finally { if (context) await closeCircleKSession(context); }
  }
}

async function processCurrentPage(context: CircleKSessionContext, pageNumber: number, outputDir: string): Promise<CircleKPOInboxPageResult> {
  const selection = await context.poInboxPage.selectAllCurrentPage();
  if (selection.status === "no-records") return { pageNumber, poCount: 0, pdfGenerated: false };
  const batchPdf = await context.poInboxPage.generateBatchPdf(); let artifact: DownloadedPdfArtifact | undefined;
  try { artifact = await context.pdfDownloadService.downloadBatchPdf(batchPdf.page, outputDir, context.targetDate, pageNumber); } finally { await batchPdf.page.close(); }
  await context.poInboxPage.verifyUsable(); return { pageNumber, poCount: selection.selectedCount, pdfGenerated: true, artifact };
}
function formatDate(date: Date): string { return [date.getFullYear(), date.getMonth() + 1, date.getDate()].map((part, index) => index === 0 ? String(part) : String(part).padStart(2, "0")).join("-"); }
