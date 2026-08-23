import "dotenv/config";

export type AutomationConfig = {
  host: string;
  port: number;
  web2BaseUrl: string;
  circleKBaseUrl: string;
  circleKUsername: string;
  circleKPassword: string;
  automationOutputDir: string;
  headless: boolean;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AutomationConfig {
  const config = {
    host: env.AUTOMATION_HOST ?? "127.0.0.1",
    port: Number(env.AUTOMATION_PORT ?? 8090),
    web2BaseUrl: env.WEB2_BASE_URL ?? "http://127.0.0.1:8088",
    circleKBaseUrl: env.CIRCLEK_BASE_URL ?? "",
    circleKUsername: env.CIRCLEK_USERNAME ?? "",
    circleKPassword: env.CIRCLEK_PASSWORD ?? "",
    automationOutputDir: env.AUTOMATION_OUTPUT_DIR ?? "",
    headless: env.CIRCLEK_HEADLESS !== "false",
  };

  const requiredValues = [
    ["CIRCLEK_BASE_URL", config.circleKBaseUrl],
    ["CIRCLEK_USERNAME", config.circleKUsername],
    ["CIRCLEK_PASSWORD", config.circleKPassword],
    ["AUTOMATION_OUTPUT_DIR", config.automationOutputDir],
  ] as const;

  const missing = requiredValues
    .filter(([, value]) => value.trim().length === 0)
    .map(([name]) => name);

  if (missing.length > 0) {
    throw new Error(`Missing required automation configuration: ${missing.join(", ")}`);
  }

  return config;
}
