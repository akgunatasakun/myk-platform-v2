// Calendar read-model tipleri

export type CalendarCategory = "training" | "payment" | "equipment" | "athlete";
export type CalendarSeverity = "info" | "warning" | "critical";

export type CalendarSourceType =
  | "training_session"
  | "payment"
  | "equipment_maintenance"
  | "equipment_insurance"
  | "athlete_license"
  | "athlete_visa"
  | "athlete_health";

export interface CalendarEvent {
  id: string;                      // "{source_type}:{uuid}"
  source_type: CalendarSourceType;
  category: CalendarCategory;
  title: string;
  date: string;                    // YYYY-MM-DD
  severity: CalendarSeverity;
  detail?: string | null;
  person_name?: string | null;
}

export interface CalendarEventsOut {
  events: CalendarEvent[];
  date_from: string;
  date_to: string;
  total: number;
}
