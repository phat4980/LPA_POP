import assert from "node:assert/strict";
import test from "node:test";
import { getNextCalendarDay } from "./date.js";

function localDateParts(date: Date): string {
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((part, index) => index === 0 ? String(part) : String(part).padStart(2, "0"))
    .join("-");
}

test("calculates the next normal calendar day", () => {
  const result = getNextCalendarDay(new Date(2026, 7, 23));

  assert.equal(localDateParts(result), "2026-08-24");
});

test("handles the end of a month", () => {
  const result = getNextCalendarDay(new Date(2026, 7, 31));

  assert.equal(localDateParts(result), "2026-09-01");
});

test("handles the end of a year", () => {
  const result = getNextCalendarDay(new Date(2026, 11, 31));

  assert.equal(localDateParts(result), "2027-01-01");
});