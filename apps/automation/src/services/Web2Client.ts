export type Web2ClientOptions = {
  baseUrl: string;
};

export class Web2Client {
  constructor(private readonly options: Web2ClientOptions) {}

  async healthCheck(): Promise<boolean> {
    const response = await fetch(`${this.options.baseUrl}/api/health`);
    return response.ok;
  }

  async createUploadJob(): Promise<never> {
    throw new Error("Web 2 upload contract is pending Phase 5 implementation.");
  }
}
