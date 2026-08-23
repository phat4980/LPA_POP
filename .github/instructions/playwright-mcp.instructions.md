---
name: Playwright MCP Rules
description: "Use when using Playwright MCP to discover, inspect, or validate Circle K BizTrade UI behavior for the LPA POP automation project. Covers safe browser exploration, evidence capture, selector design, POM mapping, and the boundary between MCP discovery and production TypeScript runtime."
applyTo: "apps/automation/**/*.ts"
---
# Playwright MCP Rules for LPA POP

## Purpose and boundary

- Use Playwright MCP as a development and discovery aid for the Circle K BizTrade UI.
- Keep production browser automation in `apps/automation/src` using the installed Playwright package and the existing TypeScript POM structure.
- Do not move Python code, duplicate PO parsing or Qty logic, or make MCP a runtime dependency of the Python Web 2.
- Preserve the existing Web 2 boundary at `http://127.0.0.1:8088`; use HTTP through a service class for integration.
- Keep the automation service independently runnable and configurable through environment variables.

## Required discovery workflow

1. Confirm the target environment and use only an approved test account, test date, and test data.
2. Open the target page and inspect the rendered UI before proposing selectors.
3. Record the observed page state, user-visible labels, navigation result, and download/print behavior.
4. Exercise the smallest useful vertical slice first:
   `Launch -> Login -> Open PO page -> Select one delivery date -> Download one page/file`.
5. Verify the selected date visibly before triggering a download.
6. Capture a screenshot and structured failure context for failed login, navigation, date selection, pagination, or download.
7. Translate confirmed observations into POM code and a focused test; do not copy exploratory MCP code into production files.

## MCP interaction rules

- Prefer `read_page`, role/name inspection, labels, visible text, and stable attributes before `click_element` or `type_in_page`.
- Use `navigate_page`, `open_browser_page`, `click_element`, `type_in_page`, `hover_element`, `handle_dialog`, `screenshot_page`, and `run_playwright_code` only for the approved discovery or validation scenario.
- Do not use arbitrary sleeps. Wait for a visible state, URL condition, network-safe UI state, download event, or other explicit condition.
- Do not probe undocumented Circle K internal APIs, hidden endpoints, or private application state.
- Do not bypass authentication, MFA, access controls, bot protections, or security warnings.
- Avoid destructive actions and real business submissions. Downloading a controlled test artifact is the default terminal action.
- Do not expose passwords, tokens, cookies, storage state, personal data, or downloaded business documents in chat, screenshots, logs, commits, or reports.
- Never save or commit Playwright storage state. Keep browser artifacts in ignored, isolated job directories.

## Selector and POM standards

- Prefer selectors in this order: accessible role/name, label, stable test or data attribute, stable semantic text, then a narrowly scoped CSS selector.
- Avoid positional selectors, generated class names, brittle XPath, arbitrary parent traversal, and selectors based only on styling.
- Keep selector definitions in `apps/automation/src/circlek/locators/`.
- Keep page-level actions and assertions in `apps/automation/src/circlek/pages/`.
- Keep reusable widgets such as pagination in `apps/automation/src/circlek/components/`.
- Keep business sequences in `apps/automation/src/flows/`; pages must not call Web 2 or filesystem services.
- Keep HTTP and filesystem boundaries in `apps/automation/src/services/`; services must not know browser selectors.
- Keep job coordination and state transitions in `apps/automation/src/jobs/`; `main.ts` only composes dependencies.
- If a selector is not confirmed in the real UI, mark it as pending and do not present it as production-ready.

## Evidence and implementation handoff

For each confirmed UI behavior, retain only non-sensitive evidence:

- page or flow name
- user-visible control text or semantic role
- expected state before and after the action
- URL pattern or navigation result, excluding secrets
- download filename pattern and isolated output location
- screenshot path on failure
- selector rationale and confidence

Before declaring a proof complete, verify all of the following:

- the selected delivery date is visible and correct
- exactly one controlled artifact is downloaded
- the artifact is isolated under the job directory
- a failure reports the phase and produces a screenshot
- the implementation compiles with `npm run build`
- no credential or storage-state material entered the repository

## Phase discipline

- Phase 3 is limited to one-page proof. Do not implement pagination, retries, persistent job storage, printing, dashboard integration, or broad API changes until the proof is stable.
- Phase 4 must detect whether the next-page control is enabled and stop based on UI state, never a hard-coded page count.
- Cross-runtime integration requires the existing multipart Web 2 endpoint and a documented contract under `packages/contracts/openapi.yaml`.
- Keep changes small, reversible, and anchored to observed behavior. Do not rewrite `src/core.py` or restructure existing Python folders to support browser discovery.
