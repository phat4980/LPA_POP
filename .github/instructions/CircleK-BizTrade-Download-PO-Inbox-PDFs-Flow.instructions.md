# CircleK BizTrade — Download PO Inbox PDFs

## 1. Purpose

Automate the process of retrieving and downloading PDF documents for all purchase orders (POs) available in the Circle K BizTrade PO Inbox.

The workflow should:

1. Navigate to Circle K BizTrade.
2. Authenticate.
3. Open PO Inbox.
4. Set the date filter to the next calendar day.
5. Search for available POs.
6. Select all POs on the current page.
7. Generate the batch PDF.
8. Download the generated PDF.
9. Return to PO Inbox.
10. Navigate to the next page.
11. Repeat the download process until all pages have been processed.

---

# 2. Preconditions

- Circle K BizTrade is accessible.
- Valid credentials are available through the configured secure environment.
- The browser can access the application.
- The user has permission to access PO Inbox and download PO documents.

Credentials must never be hard-coded or exposed.

---

# 3. Entry Point

Start from:

```text
https://circlekvn-biz.b2b.com.my/circlek_vn/auth/login
```

If an existing authenticated browser session is available, reuse it instead of logging in again.

---

# 4. Authentication

## Objective

Authenticate into Circle K BizTrade.

## Flow

1. Open the Circle K BizTrade login page.
2. Inspect the current page.
3. Identify the Username/Email input.
4. Identify the Password input.
5. Load credentials from the configured secure environment.
6. Fill the credentials.
7. Submit the login form.
8. Verify that the authenticated application state is reached.

Do not expose credentials in:

- prompts
- logs
- screenshots
- generated files
- final responses

Do not assume login succeeded merely because the login button was clicked.

---

# 5. Navigate to PO Inbox

After successful authentication:

1. Locate the sidebar navigation.
2. Locate the `Chứng từ` menu item.
3. Hover over `Chứng từ`.
4. Inspect the submenu.
5. Select `Inbox Đơn Đặt hàng`.
6. Verify that the PO Inbox page has loaded.

The target business function is:

**Chứng từ → Inbox Đơn Đặt hàng**

The implementation should discover the current UI dynamically.

Do not depend on a fixed DOM hierarchy if a more stable semantic locator is available.

---

# 6. Set Date Filter

## Objective

Set the relevant date filter to the **next calendar day**.

The date must be calculated dynamically at runtime.

Do not hard-code a specific date such as:

```text
24/08/2026
```

The workflow should work regardless of the current date.

---

## Date Picker Flow

1. Identify the date input/control associated with the required date filter.
2. Open the date picker.
3. Inspect the currently displayed calendar.
4. Determine the current date shown by the application/browser.
5. Calculate the next calendar day.
6. Select that exact date.
7. Verify that the date input reflects the expected next-day value.

---

## Date Selection Rules

The date-selection behavior should be implemented as a reusable utility/operation.

The utility should:

```text
Current date
    ↓
Calculate next calendar day
    ↓
Determine target month/year
    ↓
Open date picker
    ↓
Navigate calendar if necessary
    ↓
Select target date
    ↓
Verify selected date
```

Do not hard-code:

- current month
- current year
- day number
- calendar position
- number of clicks required to reach the target date

The date picker may display days belonging to adjacent months. Select the target date using its actual date identity rather than relying only on the visible day number.

---

## Calendar Navigation

If the target date is not currently visible:

1. Inspect the currently displayed month/year.
2. Determine whether the target date is in a different month/year.
3. Navigate the calendar accordingly.
4. Re-inspect the calendar after navigation.
5. Select the target date.

Avoid blindly clicking the `next` button a fixed number of times.

---

# 7. Search

After the correct date has been selected:

1. Locate the search action.
2. Trigger the search.
3. Wait for the results state.
4. Verify that the PO list/table has loaded.

Expected business action:

**Tìm kiếm**

Do not consider the search complete solely because the button click succeeded.

Verify that the result area has updated.

---

# 8. Process Current PO Page

After search results are available:

1. Inspect the PO table/list.
2. Determine whether there are selectable PO records.
3. If PO records are available, select all POs on the current page.
4. Verify that the expected records are selected.
5. Trigger the batch PDF generation.

The "select all" operation represents:

**Select all POs on the current page.**

Do not select records outside the current page.

---

# 9. Select All POs

Use the application's "Select All" functionality when available.

The known UI concept is:

**Select All**

Previously observed implementation:

```html
<input id="checkall" class="table-checkbox-all" type="checkbox" name="checkall" title="Select All">
```

This is implementation context only.

Prefer discovering the current accessible element dynamically.

After selecting all:

- verify that the checkbox is selected
- verify that the intended current-page records are selected

If the page contains no PO records:

1. Do not attempt batch printing.
2. Continue according to the pagination rules.
3. Do not create an empty PDF.

---

# 10. Generate Batch PDF

After all current-page POs are selected:

1. Locate the batch print action.
2. Trigger the action corresponding to **In theo lô**.
3. Wait for the PDF viewer/new tab to open.
4. Detect the newly opened page/tab.
5. Verify that the new page represents the generated PDF.

Previously observed implementation:

```html
<button id="btn-batch-print"
        class="btn btn-lightblue"
        data-action="printBatch">
    In theo lô
</button>
```

Do not rely on this exact selector if the current UI provides a more reliable locator.

Do not use undocumented APIs to generate or retrieve the PDF.

The PDF must be generated through the application's normal UI workflow.

---

# 11. PDF Download

After the PDF viewer opens:

1. Identify the browser PDF viewer download control.
2. Trigger the download.
3. Wait for the download to complete.
4. Verify that the download succeeded.
5. Save the downloaded PDF into the configured automation output directory.

## Output Directory

The output directory must be provided through the automation configuration.

Do not hard-code an absolute local filesystem path in the workflow.

Example local configuration:

```env
AUTOMATION_OUTPUT_DIR=./output
```

---

# 12. PDF Download Verification

A successful PDF workflow requires evidence that the download actually occurred.

Do not report success merely because:

- the PDF viewer opened
- the download button was clicked
- no browser error was shown

Verify the actual download event/artifact.

The downloaded file should:

- exist
- be a PDF
- correspond to the current batch operation

---

# 13. Return to Circle K PO Inbox

After the PDF has been downloaded:

1. Return to the Circle K BizTrade PO Inbox page.
2. Reuse the existing authenticated session when possible.
3. Verify that the PO Inbox page is available.
4. Preserve the current workflow context where possible.

Do not unnecessarily restart the browser or authenticate again.

---

# 14. Pagination

## Objective

Process every available PO Inbox page.

Pagination must be handled dynamically.

The workflow should inspect the current pagination state and determine whether another page exists.

Previously observed pagination concepts include:

- `Trang đầu`
- `Trước`
- current page indicator such as `1 of 2`
- page number
- `Tiếp theo`
- `Trang cuối`

These labels are business/UI context and should not be treated as immutable DOM selectors.

---

# 15. Next Page Utility

Pagination should be implemented as a reusable operation/utility.

Conceptually:

```text
Current page
    ↓
Inspect pagination state
    ↓
Determine whether next page exists
    ↓
If next page exists
    ↓
Navigate to next page
    ↓
Wait for page/result state
    ↓
Verify page changed
    ↓
Process page
```

Do not hard-code:

```text
2 pages
```

or:

```text
click "Tiếp theo" once
```

The workflow must support:

- 1 page
- 2 pages
- multiple pages
- dynamically changing page counts

---

# 16. Pagination Safety

Before navigating to the next page:

1. Inspect the current page indicator.
2. Determine whether a next page exists.
3. Ensure the next-page action is enabled/available.
4. Navigate to the next page.
5. Verify that the page index changed.

Do not repeatedly click `Tiếp theo` without verifying page changes.

Do not continue if the next-page control is disabled.

---

# 17. Main Processing Loop

The overall PO processing logic should follow:

```text
Open PO Inbox
      ↓
Set next-day date
      ↓
Search
      ↓
Process current page
      │
      ├── Select all POs
      ├── Generate batch PDF
      ├── Open PDF viewer
      └── Download PDF
      ↓
Return to PO Inbox
      ↓
Is another page available?
      │
      ├── YES → Navigate next page
      │             ↓
      │        Process current page
      │             ↓
      │        Repeat
      │
      └── NO → Complete
```

---

# 18. Page Processing Rules

Each page should be treated as an independent processing unit.

For each page:

```text
Inspect
→ determine PO availability
→ select current-page POs
→ generate PDF
→ download PDF
→ verify download
→ return to PO Inbox
```

Do not assume that the UI state from the previous page remains valid.

Re-inspect the current page after navigation.

---

# 19. Duplicate Prevention

The automation must avoid duplicate downloads caused by accidental repeated actions.

Before repeating a potentially state-changing operation:

1. Determine whether the previous operation already succeeded.
2. Verify the current browser state.
3. Continue only when necessary.

Particularly important for:

- batch PDF generation
- download
- pagination

Do not blindly retry a batch-print operation if it may already have generated a PDF.

---

# 20. Error Recovery

If a step fails:

```text
Failure
   ↓
Inspect current browser state
   ↓
Determine whether the action actually succeeded
   ↓
Recover from current state
   ↓
Retry only when justified
   ↓
Verify
```

Examples:

### PDF viewer does not open

Check whether:

- a new tab opened
- a popup opened
- the current page changed
- the application displayed an error

Do not immediately repeat batch printing.

### Download fails

Check whether:

- the PDF viewer is still open
- the download has already started
- the browser blocked the download
- a download artifact exists

### Pagination fails

Check whether:

- the current page actually changed
- the next-page control is enabled
- the application is still loading
- the current page already represents the final page

---

# 21. No Arbitrary Waiting

Do not use fixed sleeps such as:

```text
sleep 5 seconds
```

Use observable conditions:

- page loaded
- search results updated
- date picker opened
- PDF viewer opened
- download completed
- pagination changed
- expected element became available

---

# 22. No Undocumented API

The workflow must be performed through the application's intended browser UI.

Do not:

- reverse-engineer internal APIs
- call undocumented endpoints
- bypass UI workflows
- directly manipulate backend data
- retrieve PDFs through undocumented network endpoints

Use Playwright MCP/browser interaction.

---

# 23. Locator Strategy

Do not hard-code every observed selector into this flow document.

The automation agent should discover the current UI dynamically.

Known implementation details are provided only as hints when they help identify a business action.

Prefer:

1. accessible role/name
2. label
3. visible business text
4. stable application attributes
5. stable CSS
6. XPath only when necessary

Avoid brittle selectors based on:

- nth-child
- generated classes
- deep DOM hierarchy
- coordinates
- visual position

---

# 24. Dynamic UI Principle

The HTML examples in this document represent previously observed application behavior.

They are NOT guaranteed to remain unchanged.

If the current UI differs:

1. Inspect the current UI.
2. Identify the equivalent business action.
3. Use the current reliable element.
4. Continue the workflow if the business behavior remains equivalent.

Do not fail solely because an implementation detail changed.

---

# 25. Completion Criteria

The workflow is complete only when:

1. The next-day date was applied.
2. Search results were processed.
3. Every PO Inbox page has been evaluated.
4. Each page containing POs has had its POs selected.
5. Batch PDF generation was completed for each applicable page.
6. The corresponding PDF download was verified.
7. No additional PO Inbox page remains.

Final state:

```text
All applicable PO Inbox pages processed
+
All applicable batch PDFs downloaded
=
Workflow complete
```

---

# 26. Final Result

Report:

- number of pages processed
- number of PDF batches downloaded
- any pages skipped because no POs were available
- any failures that could not be recovered

Do not include:

- username
- password
- session information
- cookies
- authentication tokens
- unnecessary PO-sensitive data
