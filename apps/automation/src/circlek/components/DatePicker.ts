import type { Locator, Page } from "playwright";

const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export class DatePicker {
  constructor(
    private readonly page: Page,
    private readonly input: Locator,
  ) {}

  async selectDate(targetDate: Date): Promise<void> {
    this.assertValidDate(targetDate);
    const calendar = this.page.locator(".datepicker:visible");
    const daysView = calendar.locator(".datepicker-days:visible");
    const monthHeader = daysView.locator('[data-action="pickerSwitch"]');

    await this.input.click();
    await daysView.waitFor({ state: "visible" });
    await this.navigateToMonth(monthHeader, daysView, targetDate);

    const calendarDay = daysView.locator(
      `[data-action="selectDay"][data-day="${this.formatCalendarDate(targetDate)}"]`,
    );
    if (await calendarDay.count() !== 1 || !(await calendarDay.isEnabled())) {
      throw new Error("Target date is not selectable in the Circle K date picker.");
    }

    await calendarDay.click();

    const expectedInputValue = this.formatInputDate(targetDate);
    const actualInputValue = await this.input.inputValue();
    if (actualInputValue !== expectedInputValue) {
      throw new Error("Circle K date input did not reflect the selected date.");
    }
  }

  private async navigateToMonth(
    monthHeader: Locator,
    daysView: Locator,
    targetDate: Date,
  ): Promise<void> {
    const targetMonthIndex = targetDate.getFullYear() * 12 + targetDate.getMonth();
    let displayedMonth = this.parseDisplayedMonth(await monthHeader.textContent());

    while (displayedMonth.index !== targetMonthIndex) {
      const previousHeaderText = await monthHeader.textContent();
      const action = displayedMonth.index < targetMonthIndex ? "next" : "previous";
      await daysView.locator(`[data-action="${action}"]`).click();
      await this.page.waitForFunction(
        ({ header, previousText }) => header.textContent !== previousText,
        { header: await monthHeader.elementHandle(), previousText: previousHeaderText },
      );
      displayedMonth = this.parseDisplayedMonth(await monthHeader.textContent());
    }
  }

  private parseDisplayedMonth(headerText: string | null): { index: number } {
    const match = headerText?.trim().match(/^([A-Za-z]+)\s+(\d{4})$/);
    const month = match ? monthNames.indexOf(match[1]) : -1;
    const year = match ? Number(match[2]) : Number.NaN;
    if (month < 0 || Number.isNaN(year)) {
      throw new Error("Circle K date picker month header could not be read.");
    }

    return { index: year * 12 + month };
  }

  private formatCalendarDate(date: Date): string {
    return `${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}/${date.getFullYear()}`;
  }

  private formatInputDate(date: Date): string {
    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}/${date.getFullYear()}`;
  }

  private assertValidDate(date: Date): void {
    if (Number.isNaN(date.getTime())) {
      throw new RangeError("Cannot select an invalid date.");
    }
  }
}