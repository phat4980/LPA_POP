# LPA POP - PO Automation Implementation Plan

> This plan is based on the repository as it exists on 2026-08-23. It is incremental: preserve the working Python PO tool first, then add Circle K automation around it.

## 0. Current Repository Baseline

The repository is currently a Python application. The planned Node.js/TypeScript automation layer does not exist yet.

| Area | Current location | Verified responsibility | Status |
|---|---|---|---|
| Desktop GUI | `src/gui_modern.py`, `src/po_merge_tool_gui.py` | CustomTkinter/Tk workflows, PDF selection, merge, dashboard/staff/settings | Existing |
| Web UI | `web/index.html`, `web/app.js`, `web/styles.css` | Vanilla HTML/CSS/JS UI for the PO merge service | Existing |
| Web API | `src/web_app.py` | FastAPI app, upload/path jobs, settings, staff, PDF download, SSE events | Existing |
| PO business logic | `src/core.py` | Read codes, extract PO pages, merge and annotate Qty | Existing; do not rewrite |
| Web job worker | `src/jobs.py` | In-memory jobs with background threads and SSE | Existing; not persistent |
| Configuration | `src/config.py` | `%APPDATA%\\LPA_POP` settings/jobs, app constants, port `8088` | Existing |
| Python dependencies | `requirements.txt` | FastAPI, Uvicorn, PDF libraries, CustomTkinter and other installed packages | Existing |
| Build artifacts | `build/`, `dist/`, `__pycache__/` | Generated files | Do not use as source |
| Sample/runtime files | `po/`, `output/`, `po_merge_tool.log` | Local PDFs, output and logs | Treat as data/artifacts |
| Tests | `test/` | Existing test area; currently ignored by `.gitignore` | Needs cleanup before reliable test evidence |
| Node/TypeScript | None | No `package.json`, `tsconfig.json`, Playwright project or Node source | Not started |

### Current commands

```powershell
# Web 2 / FastAPI UI
.venv\\Scripts\\python.exe src\\web_app.py
# URL: http://127.0.0.1:8088

# Desktop GUI
.venv\\Scripts\\python.exe src\\po_merge_tool_gui.py --gui

# CLI
.venv\\Scripts\\python.exe src\\po_merge_tool_gui.py --input-folder .\\po --list-file .\\MCH.csv --output .\\output\\PO_FINAL.pdf
```

The README contains stale references to port `8080`; update them to `8088`. The source of truth is `src/config.py`, which sets `WEB_PORT = 8088`.

## 1. Architectural Decision

### Preserve the current Web 2 boundary

Do not move `src/` into `services/` yet. Existing imports, the PyInstaller spec, CLI, GUI and FastAPI app depend on the current layout. A large repository migration has no business value at this stage and increases regression risk.

The incremental target is:

```text
LPA_POP/
  src/                         Existing Python Web 2, GUI, CLI and PO engine
  web/                         Existing Web 2 frontend
  apps/automation/             New Node.js + TypeScript + Playwright service
  packages/contracts/          Versioned HTTP contract and integration docs
  scripts/                     Print and maintenance scripts, added when needed
  storage/                     Automation runtime data, added when needed
  assets/                      Existing static assets
  compile/ build/ dist/        Existing build/generated areas; never source
```

### Runtime boundaries

```text
Existing Web 2 UI/API: 127.0.0.1:8088
New automation service: configurable, proposed 127.0.0.1:8090

Automation service
  -> Playwright -> Circle K BizTrade UI
  -> multipart REST -> Existing Python Web 2 API on 8088
```

Do not reserve port `8090` until the automation service is implemented. Make it configurable through environment variables.

## 2. Phase 0 - Baseline and Constraints

**Status: DONE / BASELINE CAPTURED**

Verified facts:

- Web 2 is FastAPI plus the existing `src/core.py` pipeline.
- Web 2 supports upload jobs at `POST /api/jobs/upload`.
- Web 2 supports local path jobs at `POST /api/jobs` for automation.
- Job updates use SSE at `GET /api/jobs/{id}/events`, not polling.
- Job state is process-local and is lost when the Python process exits.
- Settings persist under `%APPDATA%\\LPA_POP` via `src/config.py`.
- `JOBS_DIR` is under `%APPDATA%\\LPA_POP\\jobs`, not repository `storage/`.
- The current frontend is a Web 2 merge UI, not yet the Circle K automation dashboard.

Rules:

- Do not rewrite `src/core.py`.
- Do not rename working Python modules as part of automation work.
- Do not treat `build/`, `dist/`, `output/`, `po/` or `__pycache__/` as source structure.
- Preserve existing upload and path API behavior while adding capabilities.

## 3. Phase 1 - Repository Preparation

**Status: DONE / INCREMENTAL SCAFFOLD COMPLETE**

Add only the minimum structure required for the first automation slice:

```text
apps/
  automation/
    package.json
    tsconfig.json
    README.md
    src/
      config/
      circlek/
        pages/
          BasePage.ts
          LoginPage.ts
          PurchaseOrderPage.ts
        components/
          Pagination.ts
        selectors/
        locators/
      flows/
      services/
      jobs/
      fixtures/
      main.ts
packages/
  contracts/
    README.md
    openapi.yaml                # add before first cross-runtime integration is complete
scripts/
  print.ps1                     # only in the printing phase
storage/
  jobs/                         # only when persistent automation jobs begin
```

Do not create empty `apps/dashboard/` or `services/po-management/` folders merely to match a diagram. Keep `web/` and `src/` authoritative until a concrete migration is approved.

Required preparation:

- Add a Node manifest only for `apps/automation`.
- Pin Node and package-manager expectations in its README.
- Add `.env.example` for non-secret URLs and browser options only.
- Keep credentials out of files, logs and git.
- Add `storage/`, Playwright artifacts and local environment files to `.gitignore`.
- Fix the README port mismatch (`8080` -> `8088`).

Acceptance criteria:

- Existing Python commands still start Web 2 and the desktop app.
- No existing Python import path changes.
- A Node smoke command runs independently without importing `src/`.

Evidence completed on 2026-08-23:

- Node.js `v22.20.0` and npm `10.8.1` are available.
- `apps/automation/package.json`, `tsconfig.json`, `README.md`, `.env.example` and `src/main.ts` exist.
- `packages/contracts/README.md` exists; `openapi.yaml` is intentionally deferred until the first integration contract is defined.
- Root `.env.example` and `.gitignore` rules were added without moving existing Python files.
- `npm install` completed with zero vulnerabilities.
- `npm run build` passed.
- `npm start` ran independently and reported Web 2 base URL `http://127.0.0.1:8088`.
- POM scaffold now separates page objects, reusable components, locator definitions, flows, services, jobs and fixtures.

## 4. Phase 2 - Existing Web 2 API Contract

**Status: IMPLEMENTED; CONTRACT DOCUMENTATION TODO**

Existing endpoints:

```text
GET  /api/health
GET  /api/settings
PUT  /api/settings
GET  /api/jobs
GET  /api/jobs/{id}
POST /api/jobs                     Path mode: pdf_paths/pdf_folder/list_file/output
POST /api/jobs/upload              Multipart: pdfs/list_file/output/pattern
GET  /api/jobs/{id}/events         SSE progress and logs
GET  /api/jobs/{id}/pdf            Final PDF download
GET  /api/staff
```

For the first automation integration, use the existing multipart endpoint. The Node client must:

1. Send downloaded PDFs as `pdfs`.
2. Send the store list as `list_file`.
3. Send an output filename/path only when required by the local deployment.
4. Read the returned Python job ID.
5. Subscribe to SSE or poll the existing job endpoint until `done`/`error`.
6. Download `/api/jobs/{id}/pdf` when complete.

Add `packages/contracts/openapi.yaml` before considering cross-runtime integration complete. Candidate additive API changes are a stable job-files/manifest endpoint, explicit timestamps/error codes and optional delivery-date metadata. Preserve existing endpoints.

## 5. Phase 3 - Circle K Automation Proof

**Status: DONE / VERIFIED AGAINST LIVE TEST ACCOUNT**

Prerequisites:

- Circle K BizTrade URL and environment are confirmed.
- Login and credential injection method are confirmed.
- Delivery-date control, PO table, pagination and print/download behavior are observed in the real UI.
- Test account and safe test date are available.

First vertical slice only:

```text
Launch browser -> Login -> Open PO page -> Select one delivery date -> Download one page/file
```

Rules:

- Use Playwright Page Objects.
- Keep selectors inside the Circle K module.
- Prefer roles, labels, text and stable attributes over positional selectors.
- Use auto-waiting and explicit conditions; avoid arbitrary sleeps.
- Never commit browser storage state.
- Capture a screenshot and structured error on failed login/navigation/download.
- Do not call undocumented Circle K internal APIs.

Acceptance criteria:

- One command runs the proof against a configured test environment.
- The selected date is visibly verified before download.
- One downloaded artifact exists in an isolated job directory.
- A failure identifies the phase and produces a screenshot.

## 6. Phase 4 - Pagination and Download Manager

**Status: DONE / VERIFIED AGAINST LIVE TEST DATA**

Expand only after the one-page proof is stable:

- Detect whether the next-page control is enabled.
- Process until the UI reports no next page; never hard-code page count.
- Use deterministic filenames and avoid overwriting files.
- Record page number, source URL, timestamp and local path in a manifest.
- Retry bounded transient navigation/download failures.
- Preserve completed downloads when a later page fails.

Target runtime layout:

```text
storage/jobs/<job-id>/
  downloads/
  screenshots/
  logs/
  manifest.json
```

Acceptance criteria:

- A three-page test environment produces three distinct artifacts.
- A failure on page N preserves pages 1..N-1.
- Pagination stops based on the UI, not a configured maximum.

## 7. Phase 5 - Web 2 Integration

**Status: DONE / LOCAL END-TO-END VERIFIED**

Create `apps/automation/src/web2/Web2Client.ts`.

Responsibilities:

- Check Web 2 health at configurable `http://127.0.0.1:8088`.
- Upload downloaded files and the configured store list to `/api/jobs/upload`.
- Track the Python job ID separately from the automation job ID.
- Consume SSE or poll the Python job endpoint.
- Download and expose the final PDF path.
- Preserve source files if Web 2 processing fails.
- Apply request timeouts and return actionable errors.

Do not move merge, Qty annotation, store mapping or PDF parsing into TypeScript.

Evidence completed on 2026-08-23:

- The Circle K workflow downloaded 3 source PDFs for 109 POs across 3 dynamically detected pages (`50`, `50`, `9`).
- `Web2Client` uploaded all source PDFs plus the configured `MCH.csv` to the existing `/api/jobs/upload` endpoint.
- The client waited for the Python job to reach `done` and downloaded the final merged PDF.
- The final artifact was verified under the configured output directory and was non-empty.

Acceptance criteria:

```text
Circle K download all -> Web 2 upload job -> Web 2 merge/annotate -> final PDF available
```

Prove this with a local fixture or controlled input before using the live Circle K site daily.

## 8. Phase 6 - Automation Job Orchestration

**Status: TODO / CURRENT PYTHON JOBS ARE NOT ENOUGH**

The current `src/jobs.py` is useful for Web 2 processing but is not a persistent cross-system job model. Add a separate automation job model in Node first; do not silently replace the Python manager.

Recommended states:

```text
QUEUED -> LOGGING_IN -> DOWNLOADING -> PROCESSING -> FINAL_READY
                                              -> FAILED
FINAL_READY -> PRINTING -> COMPLETED
                         -> PRINT_FAILED
```

Minimum data:

```text
automationJobId, deliveryDate, status, currentStep, progress
downloadedCount, totalCount, pythonJobId, sourceFiles, finalFile
error, createdAt, startedAt, completedAt
```

Start in-memory only if restart recovery is explicitly deferred. Use SQLite when history, retry or recovery begins. Do not add Redis/Kafka/brokers without a demonstrated need.

Minimum automation endpoints:

```text
POST /api/automation/jobs
GET  /api/automation/jobs/:id
GET  /api/automation/jobs/:id/events
GET  /api/automation/jobs/:id/files
```

## 9. Phase 7 - Automation Dashboard

**Status: TODO / AFTER BACKEND VERTICAL SLICE**

The current `web/` is a Web 2 merge interface, not the final Circle K dashboard. Decide explicitly whether to extend `web/` with an automation view or create `apps/dashboard/`.

Prefer extending `web/` for the first usable version to avoid duplicate frontends, provided it can call the Node API cleanly. Create `apps/dashboard/` only when the existing Web 2 UI becomes difficult to maintain.

The non-technical workflow should contain only:

- delivery date picker;
- one primary Execute button;
- current step and progress;
- clear success/failure message;
- downloaded PO count;
- final PDF preview/download;
- retry action when supported.

Do not expose Circle K selectors, filesystem paths, JSON or API details in the primary workflow.

Acceptance criteria:

1. User selects a delivery date.
2. User clicks Execute once.
3. User sees the current step and progress.
4. User can download the final PDF.
5. A failure explains what can be retried and preserves source artifacts.

## 10. Phase 8 - Printing

**Status: TODO / AFTER FINAL PDF IS STABLE**

Add only after the final PDF workflow is reliable:

```text
scripts/print.ps1
apps/automation/src/printing/PrintService.ts
```

Requirements:

- Validate the final file exists.
- Use an explicit/configured printer.
- Never invoke a shell command with unvalidated user input.
- Return `PRINTING`, `COMPLETED` or `PRINT_FAILED`.
- Keep the final PDF available when printing fails.

## 11. Phase 9 - Reliability, Recovery and Security

**Status: TODO / AFTER HAPPY PATH**

Implement in order:

1. Bounded retries for navigation, date selection, pagination and download.
2. Web 2 retry without re-downloading completed Circle K files.
3. Print-only retry.
4. SQLite job history and restart recovery.
5. Screenshots, manifests and structured logs per job.
6. Credential redaction and secret validation.

Every failure should report the automation job ID, failed step, cause, retry safety and artifact/log/screenshot location.

Credentials must come from environment variables or an OS-backed secret mechanism. Never store them in committed `.env`, browser storage state, screenshots or logs.

## 12. Phase 10 - Testing and Validation

**Status: TODO**

### Existing Python Web 2

- Add focused tests around `src/core.py` without a browser.
- Test store-list parsing, code mapping, extraction fixtures, merge ordering and Qty annotation.
- Decide whether `test/` should be unignored before adding tracked tests.

### Node automation

- Unit test job transitions, manifest writing, retry classification and `Web2Client` with mocked HTTP.
- Use Playwright tests for the Circle K proof and pagination against a controlled environment.
- Keep credentials and live production data out of tests.

### Integration

```text
download fixture -> Web 2 multipart API -> final PDF
```

A change in `src/core.py` must be able to fail a Python regression test without launching Circle K.

## 13. Delivery Slices

### Slice A - Baseline and contract

- Fix README commands/port.
- Create the automation package skeleton only when implementation starts.
- Document the current Web 2 API in `packages/contracts/openapi.yaml`.

### Slice B - Circle K one-page proof

- Login, PO page, date, one download, screenshot-on-failure.

### Slice C - All pages

- Pagination, manifest, isolated artifacts and bounded retries.

### Slice D - Web 2 integration

- Upload all downloaded files, monitor the Python job, retrieve final PDF.

### Slice E - Automation job API

- Node job state, status endpoint, SSE, failure preservation.

### Slice F - User dashboard

- Delivery date, Execute, progress, final file and retry messaging.

### Slice G - Print and recovery

- PowerShell print service, SQLite history, resumable steps and focused tests.

## 14. Definition of Done

The system is complete only when the user can:

1. Open the local automation dashboard.
2. Select a delivery date.
3. Click Execute.
4. See login/date/download/process progress.
5. See every source PO or its manifest.
6. See the existing Web 2 produce the final merged/annotated PDF.
7. Preview or download the final PDF.
8. Print the final PDF when enabled.
9. Retry a failed step without unnecessarily repeating completed steps.
10. Find job status, logs and screenshots after restart.

The existing Web 2 must remain independently runnable throughout this work.

## 15. Current Status Summary

| Phase | Status | Next evidence |
|---|---|---|
| Phase 0 - Baseline | DONE | Inventory and verified commands |
| Phase 1 - Repository preparation | DONE | Node scaffold validated without Python moves |
| Phase 2 - Existing Web 2/API | IMPLEMENTED; contract TODO | OpenAPI document and compatibility check |
| Phase 3 - Circle K one-page proof | DONE | Login, date, PDF generation and download verified |
| Phase 4 - Pagination/downloads | DONE | All detected pages downloaded with page-specific artifacts |
| Phase 5 - Web 2 integration | DONE | Final PDF produced through existing `/api/jobs/upload` |
| Phase 6 - Automation jobs | TODO | Status/retry/recovery model |
| Phase 7 - Dashboard | TODO | Non-technical Execute workflow |
| Phase 8 - Printing | TODO | Safe print command and result state |
| Phase 9 - Reliability/security | TODO | Recovery and redacted diagnostics |
| Phase 10 - Testing | TODO | Python, Node, Playwright and integration evidence |

## Final Principle

The current Python PO Management Tool is the completed foundation for PO processing, not a placeholder to replace. Add Circle K automation around its HTTP boundary, implement one vertical slice at a time, and introduce new folders or infrastructure only when a concrete acceptance criterion requires them.
