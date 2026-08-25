import { loadConfig } from "./config/environment.js";
import { createAutomationJobHttpServer } from "./api/AutomationJobHttpServer.js";
import { AutomationJobService } from "./jobs/AutomationJobService.js";
import { InMemoryAutomationJobRepository } from "./jobs/InMemoryAutomationJobRepository.js";
import { createCircleKAutomationPort, RealAutomationWorkflow } from "./jobs/RealAutomationWorkflow.js";
import { Web2Client } from "./services/Web2Client.js";
import { PrintService } from "./printing/PrintService.js";
import { LogStore } from "./logging/LogStore.js";
import { AutomationLogHub } from "./logging/AutomationLogHub.js";

const config = loadConfig();

const repository = new InMemoryAutomationJobRepository();
const printService = new PrintService(repository, { printerName: config.printerName, scriptPath: config.printScriptPath, timeoutMs: config.printTimeoutMs });
const logStore = new LogStore(config.automationDatabasePath, config.logRetentionDays);
const logHub = new AutomationLogHub(logStore);
const workflow = new RealAutomationWorkflow(createCircleKAutomationPort(config), new Web2Client({ baseUrl: config.web2BaseUrl }), config.web2ListFile, config.automationOutputDir, (jobId, entry) => logHub.publish(jobId, entry.level, entry.message, entry.ts));
const server = createAutomationJobHttpServer(new AutomationJobService(repository, workflow, undefined, printService, (entry) => logHub.publish(entry.automationJobId, entry.level, entry.message, entry.ts)), { allowedOrigins: config.allowedOrigins, logHub });
server.listen(config.port, config.host, () => console.log(`LPA POP automation API ready on ${config.host}:${config.port}`));
