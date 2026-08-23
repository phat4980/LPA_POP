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

### Hardware & mechanism (confirmed)

- Target printer: **Brother HL-L2321D**, monochrome laser, **USB-only**
  (no network interface). The automation service must run on the same
  Windows host the printer is physically attached to.
- Default output: **simplex (1-sided)**. Do not enable duplex by default;
  the printer supports it, but PO output is one-sided unless a future
  phase adds a duplex option deliberately.
- Print invoker: **SumatraPDF (portable)**, vendored as a small binary
  under `scripts/` (e.g. `scripts/vendor/SumatraPDF.exe`), since neither
  PowerShell nor Windows offers a built-in, silent, exit-code-clean way to
  print a PDF to a named printer. `print.ps1` shells out to it, e.g.:

  ```powershell
  & $sumatraPath -print-to $PrinterName -print-settings "simplex" -silent $FilePath
  ```

  This is a print-invocation utility, not a build tool — it does not touch
  `web/` or `apps/automation`'s npm dependency tree.

### Service contract

- `PrintService.print(jobId: string): Promise<'COMPLETED' | 'PRINT_FAILED'>`
  is the entire public surface. No other method returns a raw
  shell/process result to the caller.
- Validate the final file exists on disk (not just that `finalFile` is set
  in job state) before invoking `print.ps1`.
- Invoke the printer via a fixed, configured script path and a fixed
  printer name (`"Brother HL-L2321D"`, or the exact Windows printer queue
  name — verify against `Get-Printer` on the target host, it may differ
  slightly from the model name) read from environment/config — **never
  interpolate the job ID, file path, or any request field directly into a
  shell command string.** Pass values as separate process arguments
  (`spawn`, not `exec`/string concatenation), so there is no
  shell-injection surface even though inputs are server-generated today.
- On any failure (script exit code, timeout, missing file, missing
  printer), return `PRINT_FAILED` and keep the job's `finalFile`
  untouched — printing never deletes or moves the source PDF.
- Log the attempt (job ID, timestamp, printer, outcome) without logging
  full file system paths beyond what's needed to debug — consistent with
  the Phase 9 credential/diagnostics-redaction rule already in the plan.

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

---

## 9. What This Rule File Deliberately Does Not Cover

- Automated UI tests for the dashboard (Playwright coverage for
  `web/automation.html` is a Phase 9 testing decision, not this rule file).
- Any change to the Phase 6 job state machine beyond the additive
  `autoPrint` field already approved in the plan.
- Multi-page routing, since the dashboard is one page by design.

If 7.2 implementation surfaces a real need for any of the above, raise it
explicitly rather than expanding scope silently.
