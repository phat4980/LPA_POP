import "dotenv/config";

export type AutomationConfig = {
  host: string;
  port: number;
  web2BaseUrl: string;
  circleKBaseUrl: string;
  circleKUsername: string;
  circleKPassword: string;
  headless: boolean;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AutomationConfig {
  return {
    host: env.AUTOMATION_HOST ?? "127.0.0.1",
    port: Number(env.AUTOMATION_PORT ?? 8090),
    web2BaseUrl: env.WEB2_BASE_URL ?? "http://127.0.0.1:8088",
    circleKBaseUrl: env.CIRCLEK_BASE_URL ?? "https://circlekvn-biz.b2b.com.my/circlek_vn/auth/login",
    circleKUsername: env.CIRCLEK_USERNAME ?? "",
    circleKPassword: env.CIRCLEK_PASSWORD ?? "",
    headless: env.CIRCLEK_HEADLESS !== "false",
  };
}
