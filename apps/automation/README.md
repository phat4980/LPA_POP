# LPA POP Automation

Node.js/TypeScript service boundary for Circle K BizTrade browser automation.

This package is intentionally separate from the existing Python PO Management Tool:

- Circle K interaction belongs here.
- PO parsing, merge and Qty annotation remain in the Python Web 2 under `src/`.
- Cross-runtime communication uses HTTP and files.

## Source layout (Page Object Model)

```text
src/
	config/       Environment/config parsing only
	circlek/
		pages/      Page Objects: actions and assertions for one Circle K page
		components/ Reusable widgets such as pagination
		locators/   Selector definitions only
	flows/        Business flows composed from Page Objects
	services/     External boundaries, including the Python Web 2 client
	jobs/         Job orchestration and state transitions
	fixtures/     Controlled test data only
	main.ts       Composition root; no selectors or workflow logic
```

POM rules:

- Page Objects own locators' usage and page-level actions.
- Locators do not perform actions.
- Flows compose pages; pages do not call external services.
- Services do HTTP/filesystem integration; they do not know browser selectors.
- Jobs coordinate flows and services; `main.ts` only wires dependencies.

## Requirements

- Node.js 22 or newer
- npm 10 or newer
- Existing Python Web 2 available at `http://127.0.0.1:8088` when integration is enabled

## Commands

```powershell
npm install
npm run build
npm start
```

The Circle K proof flow is not implemented yet. Do not add credentials to this folder. Use environment variables or an OS-backed secret store when login is implemented.
