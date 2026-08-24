import { loadConfig } from "./config/environment.js";
import { createAutomationJobHttpServer } from "./api/AutomationJobHttpServer.js";
import { AutomationJobService } from "./jobs/AutomationJobService.js";
import { InMemoryAutomationJobRepository } from "./jobs/InMemoryAutomationJobRepository.js";
import { createCircleKAutomationPort, RealAutomationWorkflow } from "./jobs/RealAutomationWorkflow.js";
import { Web2Client } from "./services/Web2Client.js";
import { PrintService } from "./printing/PrintService.js";

const config = loadConfig();

const workflow = new RealAutomationWorkflow(createCircleKAutomationPort(config), new Web2Client({ baseUrl: config.web2BaseUrl }), config.web2ListFile, config.automationOutputDir);
const repository = new InMemoryAutomationJobRepository();
const printService = new PrintService(repository, { printerName: config.printerName, scriptPath: config.printScriptPath });
const server = createAutomationJobHttpServer(new AutomationJobService(repository, workflow, undefined, printService), { allowedOrigins: config.allowedOrigins });
server.listen(config.port, config.host, () => console.log(`LPA POP automation API ready on ${config.host}:${config.port}`));
