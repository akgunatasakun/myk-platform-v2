import apiClient from "./client";
import type { CalendarEventsOut } from "../types/calendar";

export async function fetchCalendarEvents(
  dateFrom?: string,
  dateTo?: string
): Promise<CalendarEventsOut> {
  const params: Record<string, string> = {};
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const res = await apiClient.get<CalendarEventsOut>("/calendar/events", { params });
  return res.data;
}
