import assert from "node:assert/strict";
import test from "node:test";
import { poInboxLocators } from "../locators/poInboxLocators.js";

test("poInboxLocators exposes both From and To delivery date selectors", () => {
  assert.equal(poInboxLocators.deliveryDateFrom.selector, 'input[name="deliveryDateFrom"]');
  // RED: this will fail until deliveryDateTo is added
  const loc = poInboxLocators as Record<string, unknown>;
  assert.ok("deliveryDateTo" in loc, "deliveryDateTo locator must exist");
  assert.equal((loc["deliveryDateTo"] as { selector: string }).selector, 'input[name="deliveryDateTo"]');
});

test("POInboxPage.selectDeliveryDate fills BOTH From and To with same date (past/current/future)", async (t) => {
  const calls: Array<{ selector: string; date: Date }> = [];

  t.mock.module("../components/DatePicker.js", {
    namedExports: {
      DatePicker: class {
        constructor(private page: unknown, private input: { _selector: string }) {}
        async selectDate(date: Date) {
          calls.push({ selector: (this.input as unknown as { _selector: string })._selector, date });
        }
      },
    },
  });

  // Mock page.locator to return an object carrying selector for assertion
  function createMockPage() {
    return {
      locator(selector: string) {
        return { _selector: selector } as unknown as { _selector: string };
      },
      getByRole: () => ({ hover: async () => {}, click: async () => {} }),
      getByText: () => ({ count: async () => 1, click: async () => {} }),
      waitForLoadState: async () => {},
      title: async () => "Inbox Đơn Đặt Hàng",
    } as unknown as import("playwright").Page;
  }

  const { POInboxPage } = await import("./POInboxPage.js");

  for (const iso of ["2026-08-20", "2026-08-26", "2026-09-10"]) {
    calls.length = 0;
    const page = createMockPage();
    const poPage = new POInboxPage(page);
    const target = new Date(`${iso}T00:00:00`);
    await poPage.selectDeliveryDate(target);

    assert.equal(calls.length, 2, `expected 2 DatePicker calls for ${iso}, got ${calls.length}`);
    assert.equal(calls[0].selector, poInboxLocators.deliveryDateFrom.selector);
    // This will fail until To is implemented
    assert.equal(calls[1].selector, (poInboxLocators as unknown as { deliveryDateTo: { selector: string } }).deliveryDateTo.selector);
    assert.equal(calls[0].date.getTime(), target.getTime());
    assert.equal(calls[1].date.getTime(), target.getTime());
    assert.equal(calls[0].date.getTime(), calls[1].date.getTime(), "From and To must be same date");
  }
});

test("POInboxPage exposes getDeliveryDateToValue for verification", async () => {
  const { POInboxPage } = await import("./POInboxPage.js");
  const page = {
    locator: (sel: string) => ({ inputValue: async () => (sel.includes("deliveryDateTo") ? "26/08/2026" : "26/08/2026") }),
  } as unknown as import("playwright").Page;
  const poPage = new POInboxPage(page);
  // RED: will fail until method exists
  assert.equal(typeof (poPage as unknown as { getDeliveryDateToValue?: unknown }).getDeliveryDateToValue, "function");
  const val = await (poPage as unknown as { getDeliveryDateToValue: () => Promise<string> }).getDeliveryDateToValue();
  assert.equal(val, "26/08/2026");
});
