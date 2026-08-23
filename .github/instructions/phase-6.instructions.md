
# Phase 6 — Automation Job Orchestration

## Purpose

Introduce a lightweight Node.js automation job orchestration layer around the existing Circle K Playwright automation and downstream Python processing.

The architecture must remain **simple, explicit, testable, and replaceable**.

> Do not introduce infrastructure that is not required by the current workflow.

---

## 1. System Architecture

This repository contains two main systems.

### Node.js / TypeScript — `apps/automation/`

Responsible for:

- Playwright web automation
- Circle K workflow
- Automation job orchestration
- Automation artifacts
- Automation API

### Python — `src/`

Existing Web 2 processing system.

**Important existing component:** `src/jobs.py`

This Python job manager is **NOT** the same as the Node Automation Job.

> Do not replace, migrate, duplicate, or silently modify Python job logic.

The Node job may reference a Python job through `pythonJobId`.

Conceptually:

```
Node Automation Job
        |
        | pythonJobId
        v
Python Job Manager
        |
        v
Web 2 Processing
```

Keep this boundary explicit.

---

## 2. Existing Circle K Automation

Phase 1–5 Circle K automation is already implemented and validated.

Existing components may include:

- `AutomationConfig`
- `BrowserSession`
- `LoginPage`
- `POInboxPage`
- `DateUtil`
- `DatePicker`
- `Pagination`
- PDF generation
- PDF download
- Circle K workflow

**Reuse these components.**

- Do **NOT** rewrite working Playwright functionality merely to introduce orchestration.
- The job orchestration layer should call the existing workflow.
- The job domain must not depend directly on Playwright implementation details.
- Do not modify Phase 1–5 code unless a future task explicitly requires it.

---

## 3. Automation Job

The Node application owns `automationJobId`.

**Do not use as job ID:**

- `deliveryDate`
- `filename`
- `pythonJobId`

**Minimum job data:**

| Field               |
| ------------------- |
| `automationJobId` |
| `deliveryDate`    |
| `status`          |
| `currentStep`     |
| `progress`        |
| `downloadedCount` |
| `totalCount`      |
| `pythonJobId`     |
| `sourceFiles`     |
| `finalFile`       |
| `error`           |
| `createdAt`       |
| `startedAt`       |
| `completedAt`     |

Use strong TypeScript types. Avoid `any` for core domain models.

**The `AutomationJob` must NOT contain:**

- Playwright `Page`
- `Browser`
- `BrowserContext`
- `Locator`
- HTTP request/response objects
- Credentials
- Cookies
- Authentication tokens

---

## 4. Job Lifecycle

**Canonical lifecycle:**

```
QUEUED
   |
   v
LOGGING_IN
   |
   v
DOWNLOADING
   |
   v
PROCESSING
   |
   v
FINAL_READY
   |
   v
PRINTING
   |
   v
COMPLETED
```

**Failure states:**

```
LOGGING_IN
DOWNLOADING
PROCESSING
      |
      v
    FAILED

PRINTING
    |
    v
PRINT_FAILED
```

---

## 5. State Transitions

**Only these transitions are initially valid:**

- `QUEUED` → `LOGGING_IN`
- `LOGGING_IN` → `DOWNLOADING`
- `LOGGING_IN` → `FAILED`
- `DOWNLOADING` → `PROCESSING`
- `DOWNLOADING` → `FAILED`
- `PROCESSING` → `FINAL_READY`
- `PROCESSING` → `FAILED`
- `FINAL_READY` → `PRINTING`
- `PRINTING` → `COMPLETED`
- `PRINTING` → `PRINT_FAILED`

Invalid transitions must be rejected.

**Examples that must fail:**

- `QUEUED` → `COMPLETED`
- `QUEUED` → `PRINTING`
- `COMPLETED` → `PROCESSING`
- `FAILED` → `COMPLETED`

State transitions must be:

- Explicit
- Centralized
- Deterministic
- Unit-testable

> Do not implement state transition rules inside HTTP controllers.
> Do not add states without a demonstrated business requirement.

---

## 6. Current Step

`currentStep` represents a business-level operation.

**Prefer a small set such as:**

- `QUEUED`
- `LOGIN`
- `DOWNLOAD`
- `PROCESS`
- `FINALIZE`
- `PRINT`

**These should NOT become job states** (they are internal automation actions):

- `CLICK_LOGIN`
- `FILL_USERNAME`
- `OPEN_DATE_PICKER`
- `CLICK_SEARCH`
- `CLICK_CHECK_ALL`

---

## 7. Progress

`progress` must represent actual execution progress.

**Rules:**

- Initial progress = `0`
- Completed job = `100`
- Never report `100` before `COMPLETED`
- Do not fabricate progress
- Prefer deriving progress from actual work

Progress may be derived from:

- Pages processed
- Files downloaded
- Processing stages

The exact progress calculation may evolve independently from the state model.

---

## 8. File Tracking

**Required fields:**

- `downloadedCount`
- `totalCount`
- `sourceFiles`
- `finalFile`

**Rules:**

- Increment `downloadedCount` only after successful download verification
- Do not fabricate `totalCount`
- Represent unknown total explicitly
- `finalFile` must only be set after the file actually exists and is verified

Prefer structured source file data:

```typescript
interface AutomationSourceFile {
  path: string;
  name: string;
  size?: number;
}
```

> Do not use opaque comma-separated strings.

---

## 9. Layering

**Preferred architecture:**

```
API / Controller
       |
       v
AutomationJobService
       |
       v
AutomationJobRepository
       |
       v
AutomationWorkflow
       |
       +---- Playwright
       |
       +---- Python integration
```

### Controller

Responsible for:

- Request validation
- Calling services
- HTTP response mapping

**Must NOT:**

- Execute Playwright
- Manage browser lifecycle
- Implement state transitions
- Manipulate repository internals
- Contain business workflow logic

### Service

Responsible for:

- Job orchestration
- Lifecycle updates
- Progress updates
- Workflow coordination

### Repository

Responsible for:

- Storing jobs
- Retrieving jobs
- Updating jobs
- Hiding persistence implementation

---

## 10. Repository

Use an explicit repository abstraction.

```
AutomationJobRepository
        |
        +-- InMemoryAutomationJobRepository
        |
        +-- SQLiteAutomationJobRepository (future)
```

**Minimum operations:**

- `create`
- `getById`
- `update`
- Do not expose internal mutable storage directly.
- Do not couple the domain to: `Map`, SQLite, filesystem, HTTP.

---

## 11. Persistence Strategy

Initial implementation may use **in-memory storage** when restart recovery is explicitly deferred.

**If using in-memory storage:**

- Document that jobs disappear after process restart
- Do not pretend it is persistent
- Keep the repository replaceable

When history, retry, or restart recovery becomes necessary, use **SQLite** as the next persistence option.

**Do NOT introduce, without a demonstrated requirement:**

- Redis
- Kafka
- RabbitMQ
- Message brokers
- Distributed workers

---

## 12. Job Creation

```
POST /api/automation/jobs
        |
        v
Create AutomationJob
        |
        v
QUEUED
        |
        v
Background execution
```

**On creation:**

| Field               | Initial value     |
| ------------------- | ----------------- |
| `status`          | `QUEUED`        |
| `progress`        | `0`             |
| `downloadedCount` | `0`             |
| `createdAt`       | current timestamp |
| `startedAt`       | `null`          |
| `completedAt`     | `null`          |
| `error`           | `null`          |
| `pythonJobId`     | `null`          |
| `finalFile`       | `null`          |

- Do not invent `totalCount`.
- Do not wait for the entire automation workflow during HTTP job creation.

---

## 13. Asynchronous Execution

The job workflow should run asynchronously.

```
HTTP request
     |
     v
Create job
     |
     v
Return automationJobId
     |
     v
Background execution
     |
     v
State updates
     |
     v
COMPLETED / FAILED
```

Use the simplest mechanism supported by the current Node architecture.

> Do not introduce a message broker merely to achieve asynchronous execution.

---

## 14. API

**Initial API:**

- `POST /api/automation/jobs`
- `GET /api/automation/jobs/:id`
- `GET /api/automation/jobs/:id/events`
- `GET /api/automation/jobs/:id/files`

### `POST /api/automation/jobs`

Creates a job and returns its ID/current state.

### `GET /api/automation/jobs/:id`

Returns:

- `automationJobId`
- `deliveryDate`
- `status`
- `currentStep`
- `progress`
- `downloadedCount`
- `totalCount`
- `pythonJobId`
- `sourceFiles`
- `finalFile`
- `error`
- `createdAt`
- `startedAt`
- `completedAt`

> Never expose credentials or browser/session information.

### `GET /api/automation/jobs/:id/events`

Returns meaningful lifecycle events.

### `GET /api/automation/jobs/:id/files`

Returns files belonging to that job only.

> Never expose arbitrary filesystem paths.

---

## 15. Job Events

Events represent meaningful business lifecycle changes.

**Examples:**

- `JOB_CREATED`
- `LOGIN_STARTED` / `LOGIN_COMPLETED`
- `DOWNLOAD_STARTED` / `DOWNLOAD_COMPLETED`
- `PROCESSING_STARTED` / `PROCESSING_COMPLETED`
- `FINAL_READY`
- `PRINT_STARTED` / `PRINT_COMPLETED`
- `JOB_FAILED`
- `PRINT_FAILED`

> Do not create events for every Playwright action.

Events should be useful for:

- UI
- Monitoring
- Debugging
- Future integrations

---

## 16. Python Integration

Python is an external processing system.

Use `pythonJobId` to associate the Node automation job with the Python job.

- Do not duplicate Python business logic in Node.
- Do not modify `src/jobs.py` unless a dedicated integration task explicitly requires it.
- Node and Python job states do not have to be identical.
- Define the integration contract explicitly.

---

## 17. Concurrency

Do not assume multiple automation jobs are safe to run concurrently.

**Before enabling concurrency, verify:**

- Browser isolation
- Browser context isolation
- Output directory isolation
- Filename uniqueness
- Python job isolation
- Shared resources

Until this is verified: **prefer serialized execution.**

> Do not introduce concurrency only for theoretical performance.

---

## 18. Retry

Do not implement automatic retry by default.

Retry semantics must be explicitly defined first. Consider side effects from:

- PDF generation
- File downloads
- Python processing
- Printing
- Final artifact creation

> Do not blindly rerun the entire workflow.

---

## 19. Error Handling

**When a job fails:**

- Transition to the correct failure state
- Populate `error`
- Preserve useful diagnostic context
- Stop unsafe downstream operations
- Clean up browser resources

> Never silently swallow errors.
> Never mark a job `COMPLETED` if required work failed.

**Useful diagnostic context may include:**

- `automationJobId`
- `deliveryDate`
- `status`
- `currentStep`
- Page
- Action
- Current URL
- `error`
- Artifact path

---

## 20. Logging

Logs should identify the automation job:

```
[JOB abc123] Created
[JOB abc123] LOGIN_STARTED
[JOB abc123] DOWNLOAD_STARTED
[JOB abc123] Processing page 2/3
[JOB abc123] FINAL_READY
[JOB abc123] COMPLETED
```

**Never log:**

- Username
- Password
- Tokens
- Cookies
- Session secrets

> Prefer business-level logs over raw Playwright noise.

---

## 21. Security

Credentials must remain in environment configuration.

**Never expose credentials through:**

- API responses
- Logs
- Job events
- Errors
- Screenshots
- Artifacts
- Job metadata
- Do not hard-code credentials.
- Do not expose authentication tokens or browser session data.

---

## 22. Testing

### Unit Tests

- Job creation
- Default state
- Valid transitions
- Invalid transitions
- Repository behavior
- Missing jobs
- Duplicate IDs
- Progress rules

### Integration Tests

- `POST /api/automation/jobs`
- `GET /api/automation/jobs/:id`
- `GET /api/automation/jobs/:id/events`
- `GET /api/automation/jobs/:id/files`

> Do not require Circle K for every orchestration test.

### E2E

Existing Circle K Playwright smoke/E2E tests remain the validation for the real web workflow.

> Do not replace them with mocks.

---

## 23. Change Strategy

**For every Phase 6 implementation task:**

1. Inspect the existing code first.
2. Reuse existing architecture.
3. Make the smallest safe change.
4. Preserve Phase 1–5 behavior.
5. Implement only the requested scope.
6. Run TypeScript diagnostics.
7. Run `npm run build`.
8. Run relevant tests.
9. Run relevant existing smoke tests when practical.
10. Report changed files and validation.

> Do not modify unrelated files.

---

## 24. Scope Control

Phase 6 is **ONLY** automation job orchestration.

**Do not introduce unrelated infrastructure:**

- Redis
- Kafka
- RabbitMQ
- Kubernetes
- Distributed workers
- Complex schedulers
- AI orchestration
- Undocumented backend APIs

> Prefer simple architecture. Do not over-engineer for hypothetical future requirements.

---

## 25. Phase 6 Definition of Done

Phase 6 is complete when:

- [ ] `AutomationJob` is explicitly modeled.
- [ ] State transitions are explicit and validated.
- [ ] Repository abstraction exists.
- [ ] Jobs can be created.
- [ ] Jobs can execute asynchronously.
- [ ] Job status can be queried.
- [ ] Job events can be queried.
- [ ] Job files can be queried.
- [ ] Progress reflects actual work.
- [ ] Failure states are reliable.
- [ ] Browser resources are cleaned up.
- [ ] Existing Circle K automation remains functional.
- [ ] Python `src/jobs.py` remains intact unless explicitly required.
- [ ] Credentials remain protected.
- [ ] Persistence can migrate to SQLite later.
- [ ] Relevant tests pass.
- [ ] TypeScript diagnostics pass.
- [ ] `npm run build` passes.

---

## 26. Agent Working Rules

**When implementing any Phase 6 task:**

1. Read this instruction before coding.
2. Inspect existing code before creating new abstractions.
3. Reuse existing components.
4. Prefer composition over duplication.
5. Keep domain logic independent from infrastructure.
6. Keep business rules explicit.
7. Avoid speculative abstractions.
8. Do not implement future phases unless requested.
9. Stop when the requested task is complete.
10. Report exactly what changed and how it was validated.
