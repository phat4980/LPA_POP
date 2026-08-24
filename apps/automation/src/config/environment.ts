import "dotenv/config";

export type AutomationConfig = {
  host: string;
  port: number;
  web2BaseUrl: string;
  web2ListFile: string;
  circleKBaseUrl: string;
  circleKUsername: string;
  circleKPassword: string;
  automationOutputDir: string;
  headless: boolean;
  printerName: string;
  printScriptPath: string;
  allowedOrigins?: string[];
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AutomationConfig {
  const config = {
    host: env.AUTOMATION_HOST ?? "127.0.0.1",
    port: Number(env.AUTOMATION_PORT ?? 8090),
    web2BaseUrl: env.WEB2_BASE_URL ?? "http://127.0.0.1:8088",
    web2ListFile: env.WEB2_LIST_FILE ?? "../../MCH.csv",
    circleKBaseUrl: env.CIRCLEK_BASE_URL ?? "",
    circleKUsername: env.CIRCLEK_USERNAME ?? "",
    circleKPassword: env.CIRCLEK_PASSWORD ?? "",
    automationOutputDir: env.AUTOMATION_OUTPUT_DIR ?? "",
    headless: env.CIRCLEK_HEADLESS !== "false",
    printerName: env.PRINTER_NAME ?? "Brother HL-L2320D series",
    printScriptPath: env.PRINT_SCRIPT_PATH ?? "../../scripts/print.ps1",
    allowedOrigins: (env.AUTOMATION_ALLOWED_ORIGINS ?? "http://127.0.0.1:8088,http://localhost:8088")
      .split(",").map((origin) => origin.trim()).filter(Boolean),
  };

  const requiredValues = [
    ["CIRCLEK_BASE_URL", config.circleKBaseUrl],
    ["CIRCLEK_USERNAME", config.circleKUsername],
    ["CIRCLEK_PASSWORD", config.circleKPassword],
    ["AUTOMATION_OUTPUT_DIR", config.automationOutputDir],
    ["PRINTER_NAME", config.printerName],
  ] as const;

  const missing = requiredValues
    .filter(([, value]) => value.trim().length === 0)
    .map(([name]) => name);

  if (missing.length > 0) {
    throw new Error(`Missing required automation configuration: ${missing.join(", ")}`);
  }

  return config;
}
