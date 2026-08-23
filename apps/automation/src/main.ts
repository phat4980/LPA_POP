import { loadConfig } from "./config/environment.js";

const config = loadConfig();

console.log(`LPA POP automation scaffold ready on ${config.host}:${config.port}`);
console.log(`Web 2 base URL: ${config.web2BaseUrl}`);
