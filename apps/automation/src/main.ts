import { loadConfig } from "./config/environment.js";
import { createAutomationJobHttpServer } from "./api/AutomationJobHttpServer.js";
import { AutomationJobService } from "./jobs/AutomationJobService.js";
import { InMemoryAutomationJobRepository } from "./jobs/InMemoryAutomationJobRepository.js";
import { createCircleKAutomationPort, RealAutomationWorkflow } from "./jobs/RealAutomationWorkflow.js";
import { Web2Client } from "./services/Web2Client.js";

const config = loadConfig();

const workflow = new RealAutomationWorkflow(createCircleKAutomationPort(config), new Web2Client({ baseUrl: config.web2BaseUrl }), config.web2ListFile, config.automationOutputDir);
const server = createAutomationJobHttpServer(new AutomationJobService(new InMemoryAutomationJobRepository(), workflow));
server.listen(config.port, config.host, () => console.log(`LPA POP automation API ready on ${config.host}:${config.port}`));
