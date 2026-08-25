# LPA POP - PO Automation Implementation Plan

> Updated 2026-08-25. Phase 7 is DONE and already in production for the
> client. This is the full, standalone plan: Phase 0-7 are carried over
> unchanged from the 2026-08-23 baseline (verified, in production), and new
> phases 7.4, 8.1 (restructured Phase 8), 9 and 10 are added based on real
> production feedback. Incremental: preserve the working Python PO tool
> first, keep adding automation and operational hardening around it one
> vertical slice at a time.

## 0. Current Repository Baseline

The repository is a Python application with a Node.js/TypeScript automation
layer added around it.

| Area                 | Current location                                       | Verified responsibility                                                     | Status                                      |
| --------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------- |
| Desktop GUI          | `src/gui_modern.py`, `src/po_merge_tool_gui.py`        | CustomTkinter/Tk workflows, PDF selection, merge, dashboard/staff/settings   | Existing                                     |
| Web UI               | `web/index.html`, `web/app.js`, `web/styles.css`      | Vanilla HTML/CSS/JS UI for the PO merge service                              | Existing                                     |
| Web API              | `src/web_app.py`                                        | FastAPI app, upload/path jobs, settings, staff, PDF download, SSE events     | Existing                                     |
| PO business logic    | `src/core.py`                                            | Read codes, extract PO pages, merge and annotate Qty                         | Existing; do not rewrite                     |
| Web job worker       | `src/jobs.py`                                            | In-memory jobs with background threads and SSE                               | Existing; not persistent                     |
| Configuration        | `src/config.py`                                          | `%APPDATA%\\LPA_POP` settings/jobs, app constants, port `8088`             | Existing                                     |
| Python dependencies  | `requirements.txt`                                       | FastAPI, Uvicorn, PDF libraries, CustomTkinter and other installed packages  | Existing                                     |
| Build artifacts      | `build/`, `dist/`, `__pycache__/`                     | Generated files                                                               | Do not use as source                         |
| Sample/runtime files | `po/`, `output/`, `po_merge_tool.log`                | Local PDFs, output and logs                                                   | Treat as data/artifacts                      |
| Tests                | `test/`                                                   | Existing test area; currently ignored by `.gitignore`                       | Needs cleanup before reliable test evidence  |
| Node/TypeScript      | `apps/automation/`                                        | Automation service: Playwright, job orchestration, printing, dashboard glue  | Implemented through Phase 7                  |

### Current commands

```powershell
# Web 2 / FastAPI UI
.venv\Scripts\python.exe src\web_app.py
# URL: http://127.0.0.1:8088

# Desktop GUI
.venv\Scripts\python.exe src\po_merge_tool_gui.py --gui

# CLI
.venv\Scripts\python.exe src\po_merge_tool_gui.py --input-folder .\po --list-file .\MCH.csv --output .\output\PO_FINAL.pdf

# Automation service (Node)
cd apps\automation
npm start
```

The source of truth for the Web2 port is `src/config.py`, which sets
`WEB_PORT = 8088`.

## 1. Architectural Decision

### Preserve the current Web 2 boundary

`src/` is not moved into `services/`. Existing imports, the PyInstaller
spec, CLI, GUI and FastAPI app depend on the current layout. A large
repository migration has no business value at this stage and increases
regression risk.

Current/target layout:

```text
LPA_POP/
  src/                         Existing Python Web 2, GUI, CLI and PO engine
  web/                         Existing Web 2 frontend + automation.html dashboard
  apps/automation/             Node.js + TypeScript + Playwright service
  packages/contracts/          Versioned HTTP contract and integration docs
  scripts/                     Print, service-install and launcher scripts
  storage/                     Automation runtime data (downloads, screenshots,
                                logs, manifest.json, and the automation SQLite DB)
  assets/                      Existing static assets
  compile/ build/ dist/        Existing build/generated areas; never source
```

### Runtime boundaries

```text
Existing Web 2 UI/API: 127.0.0.1:8088
Automation service: 127.0.0.1:8090 (configurable), reachable via a
  Cloudflare Tunnel domain once Phase 10 lands

Automation service
  -> Playwright -> Circle K BizTrade UI
  -> multipart REST -> Existing Python Web 2 API on 8088
  -> SQLite (jobs + logs, Phase 8.1) for persistence
```

## 2. Phase 0 - Baseline and Constraints

**Status: DONE / BASELINE CAPTURED**

Verified facts:

- Web 2 is FastAPI plus the existing `src/core.py` pipeline.
- Web 2 supports upload jobs at `POST /api/jobs/upload`.
- Web 2 supports local path jobs at `POST /api/jobs` for automation.
- Job updates use SSE at `GET /api/jobs/{id}/events`, not polling.
- Job state is process-local and is lost when the Python process exits.
- Settings persist under `%APPDATA%\LPA_POP` via `src/config.py`.
- `JOBS_DIR` is under `%APPDATA%\LPA_POP\jobs`, not repository `storage/`.
- The Web 2 frontend and the Circle K automation dashboard are separate
  UIs (`web/index.html` vs `web/automation.html`).

Rules:

- Do not rewrite `src/core.py`.
- Do not rename working Python modules as part of automation work.
- Do not treat `build/`, `dist/`, `output/`, `po/` or `__pycache__/` as
  source structure.
- Preserve existing upload and path API behavior while adding capabilities.

## 3. Phase 1 - Repository Preparation

**Status: DONE / INCREMENTAL SCAFFOLD COMPLETE**

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
    openapi.yaml
scripts/
  print.ps1
storage/
  jobs/
```

Evidence completed on 2026-08-23:

- Node.js `v22.20.0` and npm `10.8.1` are available.
- `apps/automation/package.json`, `tsconfig.json`, `README.md`,
  `.env.example` and `src/main.ts` exist.
- `packages/contracts/README.md` exists; `openapi.yaml` documentation is
  deferred.
- Root `.env.example` and `.gitignore` rules were added without moving
  existing Python files.
- `npm install` completed with zero vulnerabilities; `npm run build`
  passed; `npm start` ran independently and reported Web 2 base URL
  `http://127.0.0.1:8088`.
- POM scaffold separates page objects, reusable components, locator
  definitions, flows, services, jobs and fixtures.

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

The Node client uses the existing multipart endpoint: sends downloaded
PDFs as `pdfs`, the store list as `list_file`, an output filename/path
when required, reads the returned Python job ID, subscribes to SSE (or
polls) until `done`/`error`, then downloads `/api/jobs/{id}/pdf`.

`packages/contracts/openapi.yaml` documentation is still pending. Existing
endpoints are preserved unchanged.

## 5. Phase 3 - Circle K Automation Proof

**Status: DONE / VERIFIED AGAINST LIVE TEST ACCOUNT**

Vertical slice: `Launch browser -> Login -> Open PO page -> Select one
delivery date -> Download one page/file`.

Rules: Playwright Page Objects; selectors kept inside the Circle K module;
prefer roles/labels/text/stable attributes; auto-waiting, no arbitrary
sleeps; never commit browser storage state; screenshot + structured error
on failed login/navigation/download; no undocumented Circle K internal
APIs.

Acceptance: one command runs the proof against a configured test
environment; the selected date is visibly verified before download; one
downloaded artifact exists in an isolated job directory; a failure
identifies the phase and produces a screenshot.

## 6. Phase 4 - Pagination and Download Manager

**Status: DONE / VERIFIED AGAINST LIVE TEST DATA**

Detects whether the next-page control is enabled, processes until the UI
reports no next page (never hard-coded), uses deterministic filenames,
records page number/source URL/timestamp/local path in a manifest, retries
bounded transient failures, preserves completed downloads when a later
page fails.

```text
storage/jobs/<job-id>/
  downloads/
  screenshots/
  logs/
  manifest.json
```

Acceptance: a three-page test environment produces three distinct
artifacts; a failure on page N preserves pages 1..N-1; pagination stops
based on the UI, not a configured maximum.

## 7. Phase 5 - Web 2 Integration

**Status: DONE / LOCAL END-TO-END VERIFIED**

`apps/automation/src/web2/Web2Client.ts` checks Web 2 health, uploads
downloaded files and the configured store list to `/api/jobs/upload`,
tracks the Python job ID separately from the automation job ID, consumes
SSE or polls the Python job endpoint, downloads and exposes the final PDF
path, preserves source files if Web 2 processing fails, applies request
timeouts and returns actionable errors. Does not move merge, Qty
annotation, store mapping or PDF parsing into TypeScript.

Evidence completed on 2026-08-23: the Circle K workflow downloaded 3 source
PDFs for 109 POs across 3 dynamically detected pages (50, 50, 9);
`Web2Client` uploaded all source PDFs plus `MCH.csv` to
`/api/jobs/upload`; the client waited for the Python job to reach `done`
and downloaded the final merged PDF; the artifact was verified non-empty.

Acceptance: `Circle K download all -> Web 2 upload job -> Web 2 merge/annotate
-> final PDF available`, proven against a local fixture before daily live use.

## 8. Phase 6 - Automation Job Orchestration

**Status: DONE**

State machine:

```text
QUEUED -> LOGGING_IN -> DOWNLOADING -> PROCESSING -> FINAL_READY
                                              -> FAILED
FINAL_READY -> PRINTING -> COMPLETED
                         -> PRINT_FAILED
```

Job data: `automationJobId, deliveryDate, status, currentStep, progress,
downloadedCount, totalCount, pythonJobId, sourceFiles, finalFile, error,
createdAt, startedAt, completedAt`, plus the additive `autoPrint` and
`printOptions` fields delivered in Phase 7.1.

Endpoints:

```text
POST /api/automation/jobs
GET  /api/automation/jobs/:id
GET  /api/automation/jobs/:id/events
GET  /api/automation/jobs/:id/files
POST /api/automation/jobs/:id/print
```

Job state was in-memory through Phase 7; Phase 8.1 below moves it to
SQLite.

## 9. Phase 7 - Automation Dashboard & Printing (Merged)

**Status: DONE, verified on real hardware, running in production for the
client.**

### Architecture

`web/automation.html` extends `web/`, using **Alpine.js** vendored locally
under `web/vendor/alpinejs/` (no CDN, works on an air-gapped host). No
bundler, no build step. The JS layer calls the Node automation API via
`fetch`, polls `GET /api/automation/jobs/:id` every ~1.5-2s until a
terminal state, and renders.

### UX rules for non-technical users

- One primary action; Execute is disabled while a job is running.
- `currentStep`/`status` enum values are mapped to short human-readable
  labels; the raw enum or JSON is never rendered.
- Progress is a visual bar, not a bare number.
- Failure states map to a short plain-language explanation plus a clear
  next action; no raw error string, stack trace, or API body.
- The final PDF stays reachable once produced, even if printing later
  fails.
- No technical leakage: no Circle K selectors, filesystem paths, raw JSON
  or API endpoint names in the primary workflow.
- Accessibility: labeled date input, visible focus states,
  `aria-live="polite"` on the progress/status region.

### Printing

Explicit "Print" button plus an optional "Auto-print" checkbox next to
Execute. By default the job stops at `FINAL_READY` for review; Auto-print
proceeds through `PRINTING` automatically.

Backend rules: validate the final file exists before printing; use an
explicit configured printer, never user-selected; never invoke a shell
command with unvalidated input; print outcome resolves to exactly
`PRINTING -> COMPLETED` or `PRINTING -> PRINT_FAILED`; the final PDF
remains downloadable/previewable regardless of print outcome.

### Printer configuration (confirmed)

- Target: **Brother HL-L2321D**, Windows driver/queue name **"Brother
  HL-L2320D series"** (verify via `Get-Printer` on any new host).
  Monochrome laser, **USB-only** - the automation service must run on the
  same Windows host the printer is physically connected to.
- Default print mode: **simplex**. Duplex is supported by the hardware but
  not enabled by default.
- Print mechanism: `scripts/print.ps1` uses **SumatraPDF (portable)**,
  vendored under `scripts/vendor/`, invoked via
  `Start-Process -Wait -PassThru` reading `.ExitCode` (`$LASTEXITCODE` is
  unreliable for this GUI-subsystem executable). Printer names/paths passed
  to `-ArgumentList` are individually quoted.

### Configurable print options (confirmed)

`printOptions` (additive, stored alongside `autoPrint`):

```text
copies: number       (1-20, default 1)
pageRange: string    (Sumatra range syntax, e.g. "1-3,5"; default: all pages)
paperSize: 'A4' | 'Letter' | 'A5'   (default 'A4')
layout: 'portrait' | 'landscape'    (default 'portrait')
fitMode: 'fit' | 'noscale' | 'shrink'   (default 'fit')
```

No arbitrary percentage scaling (SumatraPDF's CLI does not support it).
All fields are server-validated against a fixed allow-list/range before
being composed into `-print-settings`; invalid values are rejected (400).

### Required non-technical workflow

1. User selects a delivery date, optionally checks Auto-print.
2. User clicks Execute once.
3. User sees current step and progress.
4. User can preview and download the final PDF.
5. User triggers Print explicitly, unless Auto-print was checked.
6. A failure explains what can be retried and preserves source artifacts.

### Delivered sub-phases

- **7.1** - Print Trigger API & PrintService: `POST .../print`,
  `PrintService.ts`, `scripts/print.ps1`, additive `autoPrint` field. DONE.
- **7.2** - Dashboard UI: `web/automation.html`, Alpine.js (vendored),
  polling, PDF preview/download, error/retry messaging. DONE (a `runJob`
  wiring bug found during CORS re-verification was fixed before close).
- **7.3** - Non-Technical Workflow Acceptance Pass: end-to-end walkthrough
  of the six-step workflow, no technical leakage. DONE.

Acceptance criteria: all met - date selection, single Execute click,
step/progress visibility, PDF preview/download, explicit or automatic
print, failure messaging with artifact preservation, zero technical
leakage in the primary workflow.

## 10. Phase 7.4 - Log Panel & Back Button (UI additions)

**Status: DONE / verified with automated SSE and SQLite coverage (see
`automation-mockup-additions.html`)**

Context: after going to production, the client needs to see processing
logs in real time - in particular the `WARNING: Khong co ma cua hang: ...`
lines that currently only exist in the Python-side `po_merge_tool.log` -
and needs a way to return to the start of the flow from the result page
without a full page reload.

### 7.4.a - Log panel (`running` state)

- Add a `.log-panel` block under `.ticket` in the `running` view of
  `web/automation.html`.
- Data source: Web2 already emits log entries over SSE at
  `GET /api/jobs/{id}/events`. The Node automation service subscribes to
  that stream (reusing the existing Web2Client connection from Phase 5)
  and **forwards it through its own SSE** at
  `/api/automation/jobs/:id/events`, merged with the automation service's
  own log lines (login/download/upload steps). The dashboard client
  connects to exactly one SSE stream.
- Every log line carries a `level` (`INFO`/`WARNING`/`ERROR`), mapped from
  Python's `logging` levels on the Web2 side and set directly on the Node
  side.
- UI: filter chips for All/Info/Warning/Error (client-side filter over
  already-received lines, no round trip per filter change), auto-scroll to
  the latest line, Copy button, and a Download-log button that exports
  only the current job's log as `.txt`.

### 7.4.b - "Back to start" button (`success` / `printed` / `printFailed`)

- Reuse the existing `resetForRetry()` in `automation-app.js` (currently
  only bound to `failure`) - wire it into `success`/`printed`/
  `printFailed` as well, placed next to Download/Print, not replacing them.
- Behavior: full reset (`job = null`, `view = 'idle'`, clear polling) -
  always starts a fresh job; does not reopen a previous job. Does not
  change the existing rule of preserving the final PDF on a failed print.

### 7.4.c - Log storage (shares the SQLite database from Phase 8.1)

```text
logs(id, automation_job_id, ts, level, message)
```

- Written in parallel with the SSE emit, never blocking real-time
  delivery.
- Filtering by level is a plain `WHERE level = ?`.
- A daily cleanup job runs `DELETE FROM logs WHERE ts < now - 3 days`
  (retention configurable via env var, default 3 days).

Acceptance criteria (7.4):

- Real-time log shows INFO/WARNING/ERROR from both Python and Node in one
  panel while a job is running.
- Level filter works correctly with no lines lost when switching filters.
- A given job's log remains viewable/downloadable for 3 days, even across
  a tab close or a service restart.
- The "Back to start" button appears on every terminal state (success,
  print failure), always starts a clean new job, and never deletes the
  produced PDF.

## 11. Phase 8 - Reliability, Recovery and Security (restructured)

**Status: 8.1 TODO - prioritized right after 7.4 | 8.2-8.6 TODO - still
"after the happy path" as in the original plan**

Rationale for the split: the production client is actively hitting the
"job lost on tab close" problem, so the "SQLite job history + restart
recovery" item is pulled forward as **8.1**, built as the full/proper
version (not a light interim version), per the client's explicit choice.
The remaining items (8.2-8.6) keep their original sequencing, run after
Phase 9 and 10.

### 8.1 - SQLite job + log persistence (pulled forward, high priority)

```text
jobs(automation_job_id, delivery_date, status, current_step, progress,
     downloaded_count, total_count, python_job_id, source_files, final_file,
     auto_print, print_options, error, created_at, started_at, completed_at)
logs(id, automation_job_id, ts, level, message)   -- see 7.4.c
```

- Replace the current in-memory job map with SQLite (`better-sqlite3` or
  equivalent); every state-machine transition is written straight to the
  DB instead of only living in RAM. DB file lives under
  `storage/db/automation.sqlite`.
- On automation service restart (crash or machine reboot): any job in a
  non-terminal state (`QUEUED`, `LOGGING_IN`, `DOWNLOADING`, `PROCESSING`,
  `PRINTING`) is marked `FAILED` with reason "Service restarted mid-job" -
  it does NOT attempt to blindly resume Playwright/printing. Files already
  downloaded remain intact under `storage/jobs/<job-id>/downloads/`.
- Client side: the current `automationJobId` is kept in `localStorage`; on
  tab reopen, call `GET /api/automation/jobs/:id` - if the job is still
  running, resume the `running` view; if it finished, show the matching
  `success`/`failure` view; if it's not found (already cleaned up), fall
  back to `idle`.
- This is the infrastructure the 7.4.b "Back to start" button relies on to
  behave correctly across tab close/reopen.

Acceptance criteria (8.1):

- Closing the tab mid-job and reopening it shows the current state instead
  of restarting from scratch.
- Restarting the automation service with a job in flight marks it `FAILED`
  clearly instead of disappearing or hanging forever in `QUEUED`.
- Files already downloaded / a PDF already produced before a service
  restart are not lost.

### 8.2 - 8.6 (unchanged from the original plan)

1. Bounded retries for navigation, date selection, pagination and download.
2. Web 2 retry without re-downloading completed Circle K files.
3. Print-only retry.
4. Screenshots, manifests and structured logs per job (beyond what 8.1
   already stores).
5. Credential redaction and secret validation.

Every failure reports the automation job ID, failed step, cause, retry
safety and artifact/log/screenshot location. Credentials come from
environment variables or an OS-backed secret mechanism - never committed
`.env`, browser storage state, screenshots, or logs.

## 12. Phase 9 - One-Click Startup for End Users

**Status: TODO**

Goal: the end user never manually runs `npm start` / `python
src/web_app.py`, and doesn't need to know what Node or Python is.

- Both services (Python Web2, Node automation) run as background **NSSM**
  Windows services: auto-start with Windows, auto-restart on crash, no
  console window shown to the user.
- A launcher (a packaged `.exe`, or a `.bat`/shortcut if a true `.exe`
  isn't required) placed on the Desktop/Start Menu: on click, it checks
  both services are running (starts them via NSSM if not), then runs
  `start <dashboard-url>` to open the right browser tab automatically - no
  need for the user to type a URL.
- `.env.example` gets a variable for the URL the launcher opens
  (localhost initially, the domain once Phase 10 lands).
- `scripts/service-install.ps1` (new) registers both NSSM services;
  `scripts/launcher/` (new) holds the launcher source/build config.

Acceptance criteria:

- The end user double-clicks one icon, never opens a terminal, never types
  a URL - the browser opens on the right page automatically.
- After a machine reboot, both services come back up on their own with no
  one having to log in and start anything.

## 13. Phase 10 - Domain & Remote Access

**Status: TODO - after Phase 9**

Context: the Brother HL-L2321D printer is USB-only, hard-wired to one
machine at the store - so no matter where the dashboard is accessed from,
the Execute/Print step must still run on that exact machine. Currently
there is only one machine; multi-site (multiple stores/multiple printers)
is a **future enhancement** for when a second machine exists, not built now.

- Use **Cloudflare Tunnel** running on the store machine to expose the
  dashboard on a dedicated subdomain - no router port forwarding, no VPN
  needed for every access.
- A user from home or elsewhere hits that domain and clicks Execute -> the
  job runs on the correct store machine (no remote desktop, no dependency
  on the client's own machine).
- **Auth is mandatory in this same phase**, not deferred - even with only
  one machine, a public domain with no login means anyone can
  Execute/Print (wasted paper, PO data exposure risk). Minimum bar: a
  simple login layer (session cookie + a preconfigured user/pass) is
  enough at the current scale; no OAuth/SSO needed yet.
- When scaling to multiple machines later: add a `siteId` concept to the
  job model (which site maps to which machine) - flagged as a future path,
  not designed in detail here.

Acceptance criteria:

- Accessing the dashboard via the domain from outside the store's LAN
  works normally, with acceptable latency for Execute/log viewing/PDF
  download.
- The dashboard is not reachable without logging in.
- A remote Execute still runs on the correct store machine with the
  attached printer.

## 14. Phase 11 - Testing and Validation

**Status: TODO**

### Existing Python Web 2

- Add focused tests around `src/core.py` without a browser.
- Test store-list parsing, code mapping, extraction fixtures, merge
  ordering and Qty annotation.
- Decide whether `test/` should be unignored before adding tracked tests.

### Node automation

- Unit test job transitions (including the SQLite-backed state machine
  from 8.1), manifest writing, retry classification, log forwarding/level
  mapping (7.4), and `Web2Client` with mocked HTTP.
- Use Playwright tests for the Circle K proof and pagination against a
  controlled environment.
- Keep credentials and live production data out of tests.

### Integration

```text
download fixture -> Web 2 multipart API -> final PDF
```

A change in `src/core.py` must be able to fail a Python regression test
without launching Circle K.

## 15. Delivery Slices

### Slice A - Baseline and contract

Fix README commands/port; document the Web 2 API in
`packages/contracts/openapi.yaml`.

### Slice B - Circle K one-page proof

Login, PO page, date, one download, screenshot-on-failure. DONE.

### Slice C - All pages

Pagination, manifest, isolated artifacts and bounded retries. DONE.

### Slice D - Web 2 integration

Upload all downloaded files, monitor the Python job, retrieve final PDF.
DONE.

### Slice E - Automation job API

Node job state, status endpoint, SSE, failure preservation. DONE.

### Slice F - Print trigger API (Phase 7.1)

`POST /api/automation/jobs/:id/print`, `PrintService.ts`,
`scripts/print.ps1`, additive `autoPrint` job field. DONE.

### Slice G - Dashboard UI (Phase 7.2)

`web/automation.html` on Alpine.js, delivery date, Execute, Auto-print
checkbox, progress, PDF preview/download, explicit Print action, retry
messaging. DONE.

### Slice H - Dashboard acceptance pass (Phase 7.3)

End-to-end walkthrough of the six-step non-technical workflow. DONE.

### Slice I - Log panel & back button (Phase 7.4)

Merged SSE log forwarding with levels, filterable log panel, Copy/Download
log, `logs` SQLite table with 3-day retention cleanup, back-to-start button
on all terminal states.

### Slice J - Persistence (Phase 8.1)

`jobs` + `logs` SQLite schema, restart-recovery marking in-flight jobs
`FAILED`, `localStorage`-based client resume.

### Slice K - One-click startup (Phase 9)

NSSM service registration, auto-restart on crash, launcher that opens the
dashboard automatically.

### Slice L - Domain & auth (Phase 10)

Cloudflare Tunnel, subdomain, minimum login layer.

### Slice M - Recovery and hardening (Phase 8.2-8.6)

Deep retry logic, print-only retry, credential redaction, structured
per-job diagnostics, focused tests.

## 16. Definition of Done

The system is complete only when the user can:

1. Open the local (or, after Phase 10, remote) automation dashboard.
2. Select a delivery date.
3. Click Execute.
4. See login/date/download/process progress, with a real-time, filterable
   log of what's happening (Phase 7.4).
5. See every source PO or its manifest.
6. See the existing Web 2 produce the final merged/annotated PDF.
7. Preview or download the final PDF.
8. Print the final PDF when enabled.
9. Return to the start of the flow with one click after any terminal state
   (Phase 7.4), and resume correctly even after closing the tab or a
   service restart (Phase 8.1).
10. Retry a failed step without unnecessarily repeating completed steps.
11. Find job status, logs and screenshots after restart, with logs kept
    for at least 3 days.
12. Launch the whole system with a single click, with no manual service
    start (Phase 9).
13. Access the dashboard remotely via a domain, behind a login, with
    execution still pinned to the correct printer-equipped machine
    (Phase 10).

The existing Web 2 must remain independently runnable throughout this work.

## 17. Current Status Summary

| Phase                                              | Status                                                        | Next evidence                                                    |
| ---------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------- |
| Phase 0 - Baseline                                 | DONE                                                            | -                                                                    |
| Phase 1 - Repository preparation                   | DONE                                                            | -                                                                    |
| Phase 2 - Existing Web 2/API                       | IMPLEMENTED; contract TODO                                     | OpenAPI document and compatibility check                            |
| Phase 3 - Circle K one-page proof                  | DONE                                                            | -                                                                    |
| Phase 4 - Pagination/downloads                     | DONE                                                            | -                                                                    |
| Phase 5 - Web 2 integration                        | DONE                                                            | -                                                                    |
| Phase 6 - Automation jobs                          | DONE (in-memory; persistence in 8.1)                            | -                                                                    |
| Phase 7 - Dashboard & Printing                     | DONE, running in production for the client                      | -                                                                    |
| **Phase 7.4 - Log panel & Back button**            | **DONE - verified with automated SSE and SQLite coverage**       | -                                                                  |
| **Phase 8.1 - SQLite job+log (pulled forward)**    | **TODO - prioritized right after 7.4**                          | `jobs`/`logs` schema, restart recovery, localStorage resume        |
| Phase 8.2-8.6 - Reliability/security (remainder)   | TODO - after the happy path                                    | Deep retries, redaction, manifests                                  |
| **Phase 9 - One-click startup**                    | **TODO**                                                        | NSSM services + auto-opening launcher                              |
| **Phase 10 - Domain & remote access**              | **TODO - after Phase 9**                                        | Cloudflare Tunnel + minimum auth                                    |
| Phase 11 - Testing                                 | TODO                                                             | Python, Node, Playwright and integration evidence                   |

## Final Principle

The current Python PO Management Tool is the completed foundation for PO
processing, not a placeholder to replace. Every new addition (logging,
persistence, startup, domain) wraps around the existing HTTP boundary,
ships one vertical slice at a time, and only adds new folders or
infrastructure when a concrete acceptance criterion requires it.