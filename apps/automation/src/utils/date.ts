export function getNextCalendarDay(date: Date = new Date()): Date {
  if (Number.isNaN(date.getTime())) {
    throw new RangeError("Cannot calculate a calendar day from an invalid date.");
  }

  const nextDay = new Date(date.getTime());
  nextDay.setDate(nextDay.getDate() + 1);
  return nextDay;
}