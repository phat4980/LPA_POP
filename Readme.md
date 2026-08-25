# LPA POP

LPA POP combines purchase-order (PO) PDF files by store code and annotates
the merged output with quantities. It provides:

- A Python Web2 service with a browser UI and REST/SSE API.
- A Python desktop GUI and CLI for local PO processing.
- A Node.js/TypeScript automation service for Circle K BizTrade, Web2
  processing, PDF download, logging, and printing.

The Python PO engine remains in `src/core.py`. The Node.js service calls it
through the Web2 HTTP API; it does not duplicate the merge logic.

## 1. Architecture

```text
Browser
  |
  +--> Python Web2 UI/API       http://127.0.0.1:8088
  |
  +--> Node automation API      http://127.0.0.1:8090
                                  |
                                  +--> Circle K BizTrade via Playwright
                                  +--> Python Web2 upload/process API
                                  +--> PDF output and SumatraPDF printing
                                  +--> storage/db/automation.sqlite
```

| Component          | Location                     | Responsibility                                |
| ------------------ | ---------------------------- | --------------------------------------------- |
| PO engine          | `src/core.py`              | Read, extract, merge, and annotate PO pages   |
| Web2 API/UI        | `src/web_app.py`, `web/` | Upload/path jobs, progress, PDF download, SSE |
| Desktop/CLI        | `src/po_merge_tool_gui.py` | Local GUI and command-line workflows          |
| Automation service | `apps/automation/`         | Circle K workflow, job API, logs, printing    |
| Print script       | `scripts/print.ps1`        | Invoke the configured Windows printer         |
| Runtime artifacts  | `output/`, `storage/`    | PDFs, job data, and automation SQLite logs    |

## 2. Requirements

- Windows
- Python 3.10 or newer
- Node.js 22 or newer
- npm 10 or newer
- A configured Circle K BizTrade account for automation
- The configured Brother printer and SumatraPDF files for printing

## 3. Initial Setup

Run these commands from the repository root in PowerShell.

### 3.1 Install Python dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 Install Node dependencies

```powershell
Push-Location apps\automation
npm install
Copy-Item .env.example .env
Pop-Location
```

Edit `apps/automation/.env` before starting automation. Set at least:

```text
CIRCLEK_BASE_URL=...
CIRCLEK_USERNAME=...
CIRCLEK_PASSWORD=...
AUTOMATION_OUTPUT_DIR=../../output
PRINTER_NAME=Brother HL-L2320D series
```

Keep `.env` out of source control. Do not commit passwords, browser state,
production PDFs, or generated logs.

## 4. Run Locally

Use two PowerShell terminals.

### 4.1 Start the Python Web2 service

From the repository root:

```powershell
.venv\Scripts\python.exe src\web_app.py
```

Verify that `http://127.0.0.1:8088` opens in a browser.

### 4.2 Start the Node automation service

From `apps/automation`:

```powershell
npm start
```

Open the automation dashboard at:
`http://127.0.0.1:8088/automation.html`

The automation API is available at `http://127.0.0.1:8090`.

## 5. Verify the Installation

Run from `apps/automation`:

```powershell
npm run build
npm run test
```

The tests cover job transitions, Web2 workflow integration, HTTP/SSE
endpoints, printing behavior, log retention, and Circle K flow boundaries.
Live Circle K and printer smoke tests require valid local configuration:

```powershell
npm run smoke:login
npm run automation:circlek-po-inbox
```

Do not run live smoke tests against production data without an isolated
delivery date and output directory.

## 6. Use the Application

### 6.1 Automation dashboard

1. Start Web2 and the automation service.
2. Open `web/automation.html` through Web2.
3. Select a delivery date and configure optional print settings.
4. Click Execute once.
5. Monitor progress and the merged INFO/WARNING/ERROR log stream.
6. Download or preview the final PDF.
7. Print explicitly, or enable auto-print before starting the job.

The automation job state flow is:

```text
QUEUED -> LOGGING_IN -> DOWNLOADING -> PROCESSING -> FINAL_READY
                                                     |
                                                     +--> PRINTING -> COMPLETED
                                                     +--> PRINT_FAILED
```

The final PDF remains available after a print failure. The log database
keeps entries for the configured retention period, three days by default.

### 6.2 Desktop GUI

From the repository root:

```powershell
.venv\Scripts\python.exe src\po_merge_tool_gui.py --gui
```

### 6.3 CLI

```powershell
.venv\Scripts\python.exe src\po_merge_tool_gui.py `
  --input-folder .\po `
  --list-file .\MCH.csv `
  --output .\output\PO_FINAL.pdf
```

The store list may be a TXT or CSV file. CSV columns support store code,
store name, and staff mapping. The merge reports missing/extra store codes
and writes the calculated quantity onto each output page.

## 7. API Map

### Python Web2 API (`8088`)

| Method  | Path                      | Purpose                                 |
| ------- | ------------------------- | --------------------------------------- |
| GET     | `/api/health`           | Health check                            |
| POST    | `/api/jobs`             | Create a path-based processing job      |
| POST    | `/api/jobs/upload`      | Create an upload-based processing job   |
| GET     | `/api/jobs/{id}`        | Read job status and summary             |
| GET     | `/api/jobs/{id}/events` | Stream progress and log events over SSE |
| GET     | `/api/jobs/{id}/pdf`    | Download the final PDF                  |
| GET/PUT | `/api/settings`         | Read or update Web2 settings            |
| GET     | `/api/staff`            | Read staff mappings from a store list   |

### Automation API (`8090`)

| Method | Path                                   | Purpose                             |
| ------ | -------------------------------------- | ----------------------------------- |
| POST   | `/api/automation/jobs`               | Start an automation job             |
| GET    | `/api/automation/jobs/{id}`          | Read automation job status          |
| GET    | `/api/automation/jobs/{id}/events`   | Stream merged leveled logs over SSE |
| GET    | `/api/automation/jobs/{id}/files`    | Read source and final file metadata |
| GET    | `/api/automation/jobs/{id}/download` | Download the final PDF              |
| POST   | `/api/automation/jobs/{id}/print`    | Print a ready PDF                   |

## 8. Configuration Reference

The automation service reads `apps/automation/.env` through
`apps/automation/src/config/environment.ts`.

| Variable                       | Default                                | Notes                                    |
| ------------------------------ | -------------------------------------- | ---------------------------------------- |
| `AUTOMATION_HOST`            | `127.0.0.1`                          | Bind address                             |
| `AUTOMATION_PORT`            | `8090`                               | Automation API port                      |
| `WEB2_BASE_URL`              | `http://127.0.0.1:8088`              | Python Web2 base URL                     |
| `WEB2_LIST_FILE`             | `../../MCH.csv`                      | Store list used for processing           |
| `CIRCLEK_BASE_URL`           | none                                   | Required login URL                       |
| `CIRCLEK_USERNAME`           | none                                   | Required; keep secret                    |
| `CIRCLEK_PASSWORD`           | none                                   | Required; keep secret                    |
| `CIRCLEK_HEADLESS`           | `true`                               | Set`false` for local browser diagnosis |
| `AUTOMATION_OUTPUT_DIR`      | none                                   | Required output directory                |
| `PRINTER_NAME`               | `Brother HL-L2320D series`           | Windows printer queue                    |
| `PRINT_TIMEOUT_MS`           | `90000`                              | Print operation timeout                  |
| `AUTOMATION_DATABASE_PATH`   | `../../storage/db/automation.sqlite` | SQLite log database                      |
| `LOG_RETENTION_DAYS`         | `3`                                  | Log cleanup retention                    |
| `AUTOMATION_ALLOWED_ORIGINS` | localhost Web2 origins                 | CORS allow-list                          |

Relative paths are resolved from the `apps/automation` working directory.
For production, use absolute paths when the service is launched by a task
or Windows service.

## 9. Production Use

The current production deployment is a Windows-hosted, local-only setup.
The printer is USB-connected to the same machine that runs the automation
service.

### 9.1 Production preparation

1. Create a dedicated Windows account or service account with access to the
   Circle K account, output folders, printer queue, and SumatraPDF.
2. Install the pinned Python and Node.js versions listed above.
3. Create the virtual environment and run `pip install -r requirements.txt`.
4. Run `npm install` in `apps/automation`.
5. Create `.env` from `apps/automation/.env.example` and use absolute paths
   for output, print script, and database where appropriate.
6. The service installer automatically installs the Playwright browser into
  a shared path for the Windows service account when it is missing. To
  pre-install it manually, use:

  ```powershell
  $env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\storage\playwright"
  cd apps\automation
  npx playwright install chromium
  ```

7. Confirm the printer queue with `Get-Printer` and set the exact queue name
   in `PRINTER_NAME`.
8. Confirm Web2 health, a test PDF, and a test print before processing real
   POs.

After these checks, install or update both Windows services:

```powershell
.\scripts\service-install.ps1
```

Create a desktop launcher with the application icon:

```powershell
.\scripts\launcher\create-desktop-shortcut.ps1
```

### 9.2 Desktop launcher flow

Run the following one time in PowerShell from the repository root:

```powershell
.\scripts\launcher\create-desktop-shortcut.ps1
```

Expected output:

```text
Shortcut created: C:\Users\<user>\Desktop\LPA POP.lnk
```

Then:

1. Open the Desktop.
2. Double-click `LPA POP`.
3. The launcher starts any stopped LPA POP service.
4. It waits up to 30 seconds for Web2 and automation to be ready.
5. It opens the URL configured by `DASHBOARD_URL`.

The shortcut calls `wscript.exe` directly, so it does not depend on the
`.vbs` file association and does not open a terminal window. The generated
shortcut uses `assets/icon/app.ico`. To change the displayed name, pass a
custom name when creating it:

```powershell
.\scripts\launcher\create-desktop-shortcut.ps1 -ShortcutName "LPA POP Automation"
```

If services are missing or do not become ready within 30 seconds, the
launcher shows a simple error message. It does not open the dashboard early.

### 9.3 Production startup

Start Web2 first, then the automation service:

```powershell
.venv\Scripts\python.exe src\web_app.py
```

```powershell
Set-Location apps\automation
npm start
```

Keep the dashboard bound to localhost unless an authenticated reverse proxy
and an explicit remote-access design are in place. The application does not
yet provide built-in authentication, automatic Windows service installation,
or restart recovery for in-flight jobs.

### 9.4 Production checklist

- Back up `storage/db/automation.sqlite` and required output directories.
- Monitor `po_merge_tool.log` and the automation process output.
- Keep `storage/`, `output/`, `.env`, and production PDFs out of commits.
- Test PDF download after every Web2 or Node deployment.
- Test printing with the configured queue after printer or Windows changes.
- Review retained logs before changing `LOG_RETENTION_DAYS`.
- Do not expose port `8090` directly to the public internet.

## 10. Runtime Data and Troubleshooting

| Data                    | Location                                 |
| ----------------------- | ---------------------------------------- |
| Web2 settings           | `%APPDATA%\LPA_POP\settings.json`      |
| Web2 log                | `po_merge_tool.log`                    |
| Web2 job files          | `%APPDATA%\LPA_POP\jobs`               |
| Automation output       | `output/` or `AUTOMATION_OUTPUT_DIR` |
| Automation log database | `storage/db/automation.sqlite`         |

Common checks:

- **Dashboard does not load:** start Web2 and use port `8088`.
- **Automation cannot start:** check required `.env` values and run
  `npm run build`.
- **Processing fails:** verify Web2 is reachable and `WEB2_LIST_FILE` exists.
- **Print fails:** verify the Windows queue name, SumatraPDF files, file
  permissions, and `PRINT_TIMEOUT_MS`.
- **Circle K login fails:** set `CIRCLEK_HEADLESS=false` for local diagnosis;
  never record credentials in screenshots or logs.

## 11. Desktop Build

The current PyInstaller build targets the desktop GUI:

```powershell
compile\build.bat
```

The Node automation service is currently run from source with `npm start`.
Windows service installation and one-click startup are separate deployment
work and are not included in this repository yet.
