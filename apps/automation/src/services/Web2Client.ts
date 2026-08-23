import { readFile, stat, writeFile } from "node:fs/promises";
import { basename, resolve } from "node:path";

export type Web2ClientOptions = {
  baseUrl: string;
  requestTimeoutMs?: number;
};

export type Web2Job = {
  id: string;
  status: "queued" | "running" | "done" | "error";
  output_path?: string;
  error?: string | null;
};

export type Web2FinalArtifact = {
  filePath: string;
  fileName: string;
  sizeBytes: number;
};

export class Web2Client {
  constructor(private readonly options: Web2ClientOptions) {}

  async healthCheck(): Promise<boolean> {
    const response = await this.request("/api/health");
    return response.ok;
  }

  async createUploadJob(pdfPaths: string[], listFile: string, outputPath?: string): Promise<Web2Job> {
    if (pdfPaths.length === 0) {
      throw new Error("Web 2 upload requires at least one PDF.");
    }

    const form = new FormData();
    for (const pdfPath of pdfPaths) {
      const data = await readFile(resolve(pdfPath));
      form.append("pdfs", new Blob([data], { type: "application/pdf" }), basename(pdfPath));
    }
    const listData = await readFile(resolve(listFile));
    form.append("list_file", new Blob([listData], { type: "text/csv" }), basename(listFile));
    if (outputPath) {
      form.append("output", outputPath);
    }

    const response = await this.request("/api/jobs/upload", {
      method: "POST",
      body: form,
    });
    return this.parseJson<Web2Job>(response);
  }

  async waitForCompletion(jobId: string): Promise<Web2Job> {
    while (true) {
      const response = await this.request(`/api/jobs/${encodeURIComponent(jobId)}`);
      const job = await this.parseJson<Web2Job>(response);
      if (job.status === "done" || job.status === "error") {
        if (job.status === "error") {
          throw new Error("Web 2 processing failed.");
        }
        return job;
      }
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 1_000));
    }
  }

  async downloadFinalPdf(jobId: string, outputPath: string): Promise<Web2FinalArtifact> {
    const response = await this.request(`/api/jobs/${encodeURIComponent(jobId)}/pdf`);
    if (!response.headers.get("content-type")?.toLowerCase().includes("application/pdf")) {
      throw new Error("Web 2 final artifact is not a PDF.");
    }
    await writeFile(outputPath, Buffer.from(await response.arrayBuffer()));
    const fileStats = await stat(outputPath);
    if (fileStats.size <= 0) {
      throw new Error("Web 2 final PDF artifact is empty.");
    }
    return {
      filePath: outputPath,
      fileName: basename(outputPath),
      sizeBytes: fileStats.size,
    };
  }

  private async request(path: string, init?: RequestInit): Promise<Response> {
    const response = await fetch(`${this.options.baseUrl}${path}`, {
      ...init,
      signal: AbortSignal.timeout(this.options.requestTimeoutMs ?? 30_000),
    });
    if (!response.ok) {
      throw new Error(`Web 2 request failed with status ${response.status}.`);
    }
    return response;
  }

  private async parseJson<T>(response: Response): Promise<T> {
    return response.json() as Promise<T>;
  }
}
