# Phase 9 - One-Click Startup - Rule

Hard constraints for implementing Phase 9 (One-Click Startup for End
Users), per `LPA_POP_PO_Automation_Implementation_Plan.md` section 12
and Slice K.

1. **Do not touch anything already DONE.**

   - Do not modify `src/core.py`, do not restructure `src/`.
   - Do not modify Phase 8.1 state-machine / SQLite logic.
   - Do not change existing ports (Web2 `8088`, automation `8090` or
     whatever is currently in `.env`) — the launcher only *reads* the
     URL, never hardcodes a new one.
2. **Two independent services, two separate NSSM services.**

   - Service 1: Python Web2 (`.venv\Scripts\python.exe src\web_app.py`).
   - Service 2: Node automation — prefer running the built entrypoint
     directly via `node.exe` (e.g. `dist/main.js`) rather than
     `npm start`, since NSSM is more reliable pointed at a script/binary
     directly than wrapped through npm.
   - Do not merge the two services into a single process.
3. **No visible console/terminal window for the end user.**

   - NSSM must run hidden (`AppNoConsole` or equivalent); stdout/stderr
     go to log files, not to a visible window.
4. **Idempotent — the install script must be safely re-runnable.**

   - `scripts/service-install.ps1` must check whether each service
     already exists before creating it; if it exists, update its config
     instead of failing.
   - Provide a clean uninstall/reinstall path (needed for dev debugging).
5. **Auto-restart on crash, auto-start with Windows.**

   - Configure NSSM `AppExit` restart policy and service start type =
     Automatic.
6. **The launcher must never assume a service is already running.**

   - Always check both services' status before opening the browser.
   - If not running, start them via NSSM/`Start-Service`, then poll the
     port/health endpoint until ready — with a bounded timeout, never an
     infinite wait.
   - On timeout, show a clear, non-technical error message to the end
     user (not a stack trace); never fail silently.
7. **No absolute paths hardcoded to a dev machine.**

   - Every path in the scripts must be derived from `$PSScriptRoot` or
     from `.env`, not hardcoded like `C:\Users\...`.
8. **`.env.example` only adds a new variable, never changes existing ones.**

   - Add one variable, e.g. `DASHBOARD_URL` (defaulting to the current
     automation dashboard URL) — so Phase 10 only needs to change this
     value to the public domain, with no launcher code changes required.
9. **Manual dev commands must keep working after Phase 9.**

   - The existing commands in the plan's "Current commands" section
     (`npm start`, running `python src/web_app.py` by hand) must still
     work for dev/debug purposes. NSSM is an additional layer, not a
     replacement for manual dev workflows.
10. **New files must land exactly where the plan specifies:**

    - `scripts/service-install.ps1` (new)
    - `scripts/launcher/` (new) — launcher source/build config
    - Do not create new top-level directories outside the plan.
11. **Required evidence before marking Phase 9 DONE:**

    - Run `scripts/service-install.ps1` on a clean machine (or clearly
      document test steps if a real Windows machine isn't available in
      this environment) → both services reach Running state.
    - Kill one service's process → confirm NSSM auto-restarts it.
    - Simulate/perform a reboot → both services come back up
      automatically with no manual login/start required.
    - Double-click the launcher → the browser opens on the correct
      dashboard URL, with no terminal window visible.
    - Update `LPA_POP_PO_Automation_Implementation_Plan.md`: Phase 9 →
      DONE, Slice K → DONE, and the Current Status Summary table
      updated accordingly.
    - If any of the above cannot be verified in the current environment
      (e.g. no Windows machine available for testing), state that
      explicitly instead of marking it DON

# Rules — Phase 8.1 (SQLite Job Persistence)

> Dedicated rule file for this sub-phase, per the same convention used
> before 7.1/7.2/7.3 (a short rules file precedes a sub-phase whenever it
> introduces a new pattern the repo hasn't used yet, so multiple/separate
> agent sessions stay consistent). Phase 8.1 introduces SQLite to the
> automation service for the first time — these are the conventions to
> follow while implementing it.

## Database

- One SQLite file for the whole automation service:
  `storage/db/automation.sqlite`. Do not create a second DB file for job
  persistence — **Phase 7.4 already created a `logs` table** (written by
  `AutomationLogHub`, see `web2/Web2Client.ts` snapshot-sync logic) that is
  expected to live in this same file. Locate that existing table/connection
  first; add the new `jobs` table to it rather than starting a fresh
  database.
- Use `better-sqlite3` (synchronous API) unless the existing 7.4 code
  already established a different driver — match whatever 7.4 used rather
  than introducing a second SQLite library into the same service.
- One shared connection/module (e.g. `persistence/db.ts`) exporting a
  singleton `Database` instance. Every repository/module reuses it — no
  per-request `new Database(...)`.
- Schema changes go through a migrations folder (e.g.
  `persistence/migrations/NNN_description.sql` or equivalent), applied on
  service startup, tracked via a `schema_migrations` (or similar) table.
  Do not hand-edit the schema outside a migration once this exists.

## Naming

- DB columns: `snake_case` (matches the `logs` table already shipped in
  7.4: `automation_job_id`, `ts`, `level`, `message`).
- TypeScript/JS layer: `camelCase`, with an explicit mapping
  function/layer between DB rows and in-memory job objects — never leak
  raw `snake_case` row objects into the job state machine or the HTTP
  layer.
- Job table name: `jobs`. Column list matches the plan's `jobs(...)`
  schema in section 8.1 exactly (`automation_job_id`, `delivery_date`,
  `status`, `current_step`, `progress`, `downloaded_count`, `total_count`,
  `python_job_id`, `source_files`, `final_file`, `auto_print`,
  `print_options`, `error`, `created_at`, `started_at`, `completed_at`).
  `source_files`/`print_options` are JSON-serialized text columns.

## Writes

- Every state-machine transition writes to SQLite synchronously as part of
  the same function that updates in-memory state — the DB is the source of
  truth going forward, not a best-effort mirror. This differs from the
  7.4 log writes (which are intentionally async/non-blocking) because job
  status must never drift from what's persisted.
- Wrap the write in a try/catch that logs a structured error (job ID,
  step, cause) via the existing `AutomationLogHub` — do not let a DB write
  failure crash the job in progress; surface it as a log entry and keep
  serving from in-memory state for that request.

## Restart recovery

- Runs once at service startup, before the HTTP server starts accepting
  automation job requests.
- Query for any job whose `status` is not in the terminal set
  (`FINAL_READY`, `COMPLETED`, `FAILED`, `PRINT_FAILED`) — for each, set
  `status = 'FAILED'`, `error = 'Service restarted mid-job'`,
  `completed_at = now`. Do not attempt to resume Playwright or printing.
- Never delete rows from `storage/jobs/<job-id>/downloads/` as part of
  recovery — recovery only touches the `jobs` table.

## Client-side resume

- `localStorage` key: `lpaPop.automationJobId` (single active job ID,
  overwritten on every new Execute — this app has one job in flight at a
  time, not a list).
- On page load, if the key is present: call
  `GET /api/automation/jobs/:id`. Route the result to the matching view
  exactly as live polling would (`running` if non-terminal, `success`/
  `printed`/`printFailed`/`failure` if terminal). A 404 (job not found —
  e.g. already cleaned up) clears the key and falls back to `idle`.
- Clear the key whenever `resetForRetry()` runs (7.4.b) — a fresh Execute
  should not resume a job the user has explicitly moved past.

## Testing

- Unit tests for: each state transition writes the expected row: restart
  recovery marks the right jobs `FAILED` and leaves terminal jobs
  untouched; the DB-row-to-job mapping round-trips
  `source_files`/`print_options` correctly.
- Use a temporary/in-memory SQLite file per test (not the real
  `storage/db/automation.sqlite`) — never run tests against a path that
  could collide with a real running servic

# Phase 7 Rules — Dashboard Frontend & Printing

> Applies to `web/automation.html`, its JS/CSS, and
> `apps/automation/src/printing/PrintService.ts`. Written before 7.1/7.2/7.3
> so agent sessions produce consistent code. Confirmed decisions this file
> assumes: extend `web/`, Alpine.js (vendored, no CDN), explicit Print
> button + optional Auto-print.

---

## 1. File & Folder Structure

```text
web/
  automation.html          Dashboard page (markup + x-data wiring only)
  automation.css            Dashboard-specific styles
  js/
    automation-app.js       Alpine component definition + Alpine.store
    automation-api.js       Thin fetch wrapper, no Alpine dependency
  vendor/
    alpinejs/
      alpine.min.js         Vendored, pinned version, committed to repo
```

Rules:

- **One page, one component.** Do not split the dashboard into multiple
  Alpine components communicating via events unless a concrete second page
  appears. A single `x-data="automationDashboard()"` root is correct at
  this scope.
- **No inline `x-data="{ ... }"` objects in HTML.** Define the component as
  a named function in `automation-app.js` and reference it by name in the
  HTML (`x-data="automationDashboard()"`). Inline object literals in
  attributes are the #1 reason Alpine pages become unmaintainable — keep
  all logic in `.js`, all structure in `.html`.
- **API calls never live in the Alpine component directly.** They go in
  `automation-api.js` as plain async functions (`startJob()`,
  `getJob(id)`, `triggerPrint(id)`). The Alpine component calls these and
  only holds UI state. This keeps the component testable without a DOM and
  keeps `fetch`/error-mapping logic in one place.
- Do not add a bundler, transpiler, or `package.json` to `web/`. If a
  build step is ever justified, that is a decision for a future phase, not
  an incidental addition here.

---

## 2. Alpine.js Conventions

### 2.1 Component shape

```js
// automation-app.js
function automationDashboard() {
  return {
    // --- state ---
    deliveryDate: '',
    autoPrint: false,
    job: null,          // current job object from the API, or null
    polling: null,       // interval handle
    errorMessage: null,  // human-readable string, never raw error

    // --- derived (computed via getters, not duplicated state) ---
    get isRunning() {
      return this.job && !TERMINAL_STATES.includes(this.job.status);
    },
    get statusLabel() {
      return STATUS_LABELS[this.job?.status] ?? '';
    },

    // --- lifecycle ---
    init() { /* restore nothing from localStorage; fresh state on load */ },

    // --- actions ---
    async execute() { /* calls automation-api.js, starts polling */ },
    async print() { /* calls automation-api.js */ },
    destroy() { clearInterval(this.polling); },
  };
}
```

- **State vs. derived state:** anything computable from existing state
  (button disabled, status label, progress percentage text) must be a
  getter, never a second piece of state kept in sync by hand. Duplicated
  state is the most common source of Alpine bugs.
- **No global `window` mutation** beyond the single `function automationDashboard() {}` declaration needed for `x-data`.
- **Naming:** camelCase for all state/methods. Boolean state prefixed
  `is`/`has` (`isRunning`), not bare adjectives.
- Use `Alpine.store()` **only if** a second page needs to share job state.
  Not needed for a single-page dashboard — do not add it preemptively.

### 2.2 Templates (HTML)

- Use `x-show` for the ~6 state views (idle / running / success / failure
  / print-pending / printed), not `x-if`/`<template>`, unless a view does
  DOM work expensive enough to justify not pre-rendering it. `x-show` is
  simpler to reason about for this many mutually-exclusive states.
- Use `x-text` for all dynamic text content. **Never use `x-html`** with
  data that originates from the API — job status, error messages, file
  names are all effectively external input. This is a hard rule, not a
  style preference: `x-html` on API-derived content is an XSS vector.
- One `x-data` root per page. Nested `x-data` blocks are allowed only for
  genuinely independent widgets (there are none planned in this phase).
- Keep templates declarative: no `x-init` blocks containing multi-step
  logic — call a single named method (`x-init="init()"`) and put the logic
  in the component function.

---

## 3. API Client Layer (`automation-api.js`)

```js
const BASE = 'http://127.0.0.1:8090'; // from a single documented constant

export async function startJob(deliveryDate, autoPrint) {
  const res = await fetch(`${BASE}/api/automation/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deliveryDate, autoPrint }),
  });
  if (!res.ok) throw await toApiError(res);
  return res.json();
}
```

Rules:

- Every function returns parsed JSON or throws a normalized `ApiError`
  (`{ code, message }`). The Alpine layer maps `code` to a human message —
  raw `error.message` from `fetch`/JSON never reaches `x-text` directly.
- Every request has a timeout (`AbortController`, ~10s for job start,
  longer tolerance only for the poll loop, which has its own retry logic
  — see §4).
- The base URL is one constant, not hardcoded per call, and should be
  overridable via a `<meta>` tag or small config object if the port ever
  needs to differ per deployment — do not hardcode `8090` in more than one
  place.
- No credentials, tokens, or secrets in this file or in `automation.html`.
  This is a local-only tool talking to a local-only API; if that changes,
  auth must be added deliberately, not bolted onto this layer silently.

---

## 4. Polling Rules

- Poll `GET /api/automation/jobs/:id` every **1.5–2s** while
  `isRunning`. Stop immediately on reaching a terminal state
  (`COMPLETED`, `FAILED`, `PRINT_FAILED`).
- Always clear the interval in two places: on terminal state, and on
  `destroy()`/page unload. A leaked interval hitting a dead job ID
  indefinitely is a known Alpine footgun.
- On a single poll failure (network blip), retry silently up to 3 times
  before surfacing an error — do not fail the whole workflow on one dropped
  request.
- Never poll faster than 1s. This is a local API with no rate limiting,
  but tight polling loops are still wasteful and make debugging harder.

---

## 5. UX / Error-Mapping Rules

(Carried over from the merged Phase 7 plan section — repeated here because
this is where they get implemented.)

- Map every `status`/`currentStep` enum value to a fixed, reviewed
  human-readable string in a single lookup table (`STATUS_LABELS`,
  `ERROR_LABELS`) in `automation-app.js`. Never fall back to displaying the
  raw enum if a mapping is missing — treat a missing mapping as a bug to
  fix, and show a generic "Something went wrong" instead.
- `finalFile`/download link renders as soon as it's present in the job
  object, regardless of print status.
- Execute button: `:disabled="isRunning"`.
- Progress bar: bind width/aria-valuenow to `job.progress`; always pair
  the bar with `x-text` showing the mapped step label, not just a percent.
- Status/progress region: `aria-live="polite"` wrapping the step label and
  progress, so screen readers announce changes without a visual reread.
- No animation/transition beyond a simple CSS `transition` on the progress
  bar width. No spinners with custom illustration, no confetti on success.

---

## 6. CSS Rules (`automation.css`)

- Plain CSS, no preprocessor, no utility framework (Tailwind etc. would
  need a build step — out of scope per §1).
- Use CSS custom properties for the handful of colors/spacing values used
  (`--color-success`, `--color-error`, `--space-md`, …) defined once at
  `:root`, so status colors (running/success/failure) stay consistent and
  editable in one place.
- Mobile responsiveness: not a requirement (internal desktop tool), but
  don't hardcode pixel widths that break on a laptop screen — use relative
  units for the main container.
- No CSS-in-JS. Keep style entirely out of `automation-app.js`.

---

## 7. Printing (`PrintService.ts`, backend — Phase 7.1)

### Hardware & mechanism (confirmed, verified on real host)

- Target printer: **Brother HL-L2321D**. **Actual Windows queue name is
  `"Brother HL-L2320D series"`** — the driver is shared across the
  HL-L2320D/L2321D family, so the queue name does not match the model
  printed on the device. Always verify with `Get-Printer` on any new
  host; never assume the model name is the queue name.
- Default output: **simplex (1-sided)**.
- Print invoker: **SumatraPDF (portable)**, vendored under
  `scripts/vendor/sumatrapdf-3.6.1/`. Authenticity verified via
  Authenticode signature (`Get-AuthenticodeSignature`, signer: Krzysztof
  Kowalczyk) rather than a published checksum — SumatraPDF does not
  publish official hashes for cross-verification, so the signature check
  is the reliable integrity method, not a SHA-256 comparison against an
  official list.
- **SumatraPDF is a GUI-subsystem executable, not a console app.**
  `$LASTEXITCODE` after invoking it via the `&` call operator is
  unreliable and was the cause of a false-negative bug found during 7.1
  verification (script reported failure on a successful print). Use
  `Start-Process -Wait -PassThru` and read `.ExitCode` from the returned
  process object instead.
- **`Start-Process -ArgumentList` does not auto-quote array elements
  containing spaces** the way the `&` call operator does. A printer name
  like `"Brother HL-L2320D series"` passed unquoted gets split across
  multiple arguments by the resulting command line, causing SumatraPDF to
  silently print to the wrong (default) printer instead of failing
  loudly. Every argument that may contain spaces (printer name, file
  path, and later the composed `-print-settings` string) must be
  individually wrapped in quotes in code before being added to the
  `-ArgumentList` array — do not rely on PowerShell to do this
  automatically.

### Service contract

- `PrintService.print(jobId: string, options?: PrintOptions): Promise<'COMPLETED' | 'PRINT_FAILED'>`. No other method returns a raw
  shell/process result to the caller.
- Validate the final file exists on disk (not just that `finalFile` is set
  in job state) before invoking `print.ps1`.
- Invoke the printer via a fixed, configured script path and a fixed
  printer name (`"Brother HL-L2320D series"` — the verified queue name,
  not the model name) read from environment/config — **never interpolate
  the job ID, file path, or any request field directly into a shell
  command string.** Pass values as separate process arguments, quoted
  individually per the `Start-Process` note above.
- On any failure (script exit code, timeout, missing file, missing
  printer), return `PRINT_FAILED` and keep the job's `finalFile`
  untouched.
- Log the attempt (job ID, timestamp, printer, outcome) without logging
  full file system paths beyond what's needed to debug.

### Configurable print options (additive)

```ts
interface PrintOptions {
  copies?: number;                          // 1-20, default 2
  pageRange?: string;                       // Sumatra range syntax, default: all pages
  paperSize?: 'A4' | 'Letter' | 'A5';       // default 'A5'
  layout?: 'portrait' | 'landscape';        // default 'portrait'
  fitMode?: 'fit' | 'noscale' | 'shrink';   // default 'fit'
}
```

- Stored on the job record alongside `autoPrint` (declared at job
  creation, since an auto-printed job has no manual Print click at which
  to collect these). The explicit `POST .../print` endpoint may accept an
  optional `printOptions` body to override just that call; otherwise it
  falls back to the job's stored value, then to the defaults above.
- **Every field is validated against a fixed allow-list/range** before
  being composed into the `-print-settings` string
  (`${copies}x,${pageRange},paper=${paperSize},${layout},${fitMode},simplex`).
  The client never supplies a raw `-print-settings` string. Invalid values
  are rejected outright, never silently clamped or dropped.
- **No arbitrary percentage scaling is possible.** SumatraPDF's print CLI
  only supports the three discrete `fitMode` values; `-zoom <percent>`
  affects only the interactive viewer, not `-print-to`. Do not design a
  UI control that implies free-form scale percentage — it cannot be
  honored by the underlying tool.
- UI for these options is Phase 7.2/7.3 scope, not this section.

---

## 8. Code Style Summary

| Concern        | Rule                                                                       |
| -------------- | -------------------------------------------------------------------------- |
| Naming         | camelCase everywhere in JS; kebab-case for CSS classes                     |
| Functions      | Small, single-purpose; API calls never mixed with DOM/Alpine state updates |
| Comments       | Explain*why* (e.g. why a retry count is 3), not *what* the line does   |
| Error surfaces | Always mapped to a fixed human string; raw errors only in`console.error` |
| Dependencies   | Alpine.js only, vendored; zero new npm packages in`web/`                 |
| Secrets        | None in this layer, ever                                                   |

# Phase 9 - One-Click Startup - Rule

Hard constraints for implementing Phase 9 (One-Click Startup for End
Users), per `LPA_POP_PO_Automation_Implementation_Plan.md` section 12
and Slice K.

1. **Do not touch anything already DONE.**

   - Do not modify `src/core.py`, do not restructure `src/`.
   - Do not modify Phase 8.1 state-machine / SQLite logic.
   - Do not change existing ports (Web2 `8088`, automation `8090` or
     whatever is currently in `.env`) — the launcher only *reads* the
     URL, never hardcodes a new one.
2. **Two independent services, two separate NSSM services.**

   - Service 1: Python Web2 (`.venv\Scripts\python.exe src\web_app.py`).
   - Service 2: Node automation — prefer running the built entrypoint
     directly via `node.exe` (e.g. `dist/main.js`) rather than
     `npm start`, since NSSM is more reliable pointed at a script/binary
     directly than wrapped through npm.
   - Do not merge the two services into a single process.
3. **No visible console/terminal window for the end user.**

   - NSSM must run hidden (`AppNoConsole` or equivalent); stdout/stderr
     go to log files, not to a visible window.
4. **Idempotent — the install script must be safely re-runnable.**

   - `scripts/service-install.ps1` must check whether each service
     already exists before creating it; if it exists, update its config
     instead of failing.
   - Provide a clean uninstall/reinstall path (needed for dev debugging).
5. **Auto-restart on crash, auto-start with Windows.**

   - Configure NSSM `AppExit` restart policy and service start type =
     Automatic.
6. **The launcher must never assume a service is already running.**

   - Always check both services' status before opening the browser.
   - If not running, start them via NSSM/`Start-Service`, then poll the
     port/health endpoint until ready — with a bounded timeout, never an
     infinite wait.
   - On timeout, show a clear, non-technical error message to the end
     user (not a stack trace); never fail silently.
7. **No absolute paths hardcoded to a dev machine.**

   - Every path in the scripts must be derived from `$PSScriptRoot` or
     from `.env`, not hardcoded like `C:\Users\...`.
8. **`.env.example` only adds a new variable, never changes existing ones.**

   - Add one variable, e.g. `DASHBOARD_URL` (defaulting to the current
     automation dashboard URL) — so Phase 10 only needs to change this
     value to the public domain, with no launcher code changes required.
9. **Manual dev commands must keep working after Phase 9.**

   - The existing commands in the plan's "Current commands" section
     (`npm start`, running `python src/web_app.py` by hand) must still
     work for dev/debug purposes. NSSM is an additional layer, not a
     replacement for manual dev workflows.
10. **New files must land exactly where the plan specifies:**

    - `scripts/service-install.ps1` (new)
    - `scripts/launcher/` (new) — launcher source/build config
    - Do not create new top-level directories outside the plan.
11. **Required evidence before marking Phase 9 DONE:**

    - Run `scripts/service-install.ps1` on a clean machine (or clearly
      document test steps if a real Windows machine isn't available in
      this environment) → both services reach Running state.
    - Kill one service's process → confirm NSSM auto-restarts it.
    - Simulate/perform a reboot → both services come back up
      automatically with no manual login/start required.
    - Double-click the launcher → the browser opens on the correct
      dashboard URL, with no terminal window visible.
    - Update `LPA_POP_PO_Automation_Implementation_Plan.md`: Phase 9 →
      DONE, Slice K → DONE, and the Current Status Summary table
      updated accordingly.
    - If any of the above cannot be verified in the current environment
      (e.g. no Windows machine available for testing), state that
      explicitly instead of marking it DONE.

---

## 9. What This Rule File Deliberately Does Not Cover

- Automated UI tests for the dashboard (Playwright coverage for
  `web/automation.html` is a Phase 9 testing decision, not this rule file).
- Any change to the Phase 6 job state machine beyond the additive
  `autoPrint` field already approved in the plan.
- Multi-page routing, since the dashboard is one page by design.

If 7.2 implementation surfaces a real need for any of the above, raise it
explicitly rather than expanding scope silently.
