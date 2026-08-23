import { loadConfig } from "./config/environment.js";
import { CircleKPOInboxWorkflow } from "./flows/CircleKPOInboxWorkflow.js";

const result = await new CircleKPOInboxWorkflow(
  loadConfig({ ...process.env, CIRCLEK_HEADLESS: "false" }),
).run();
console.log(JSON.stringify(result, null, 2));

if (!result.success) {
  process.exitCode = 1;
}