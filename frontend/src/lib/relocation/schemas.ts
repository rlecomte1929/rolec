// Foundation for the Relocation Navigator multi-agent workflow.
// Keep this file schema-first and free of agent logic.

export const RELOCATION_PROFILE_FIELD_NAMES = [
  "origin_country",
  "destination_country",
  "move_date",
  "employment_type",
  "employer_country",
  "works_remote",
  "notes",
  "has_corporate_tax_support",
] as const;

export type RelocationProfileFieldName =
  (typeof RELOCATION_PROFILE_FIELD_NAMES)[number];

export type EmploymentType =
  | "employee"
  | "self_employed"
  | "student"
  | "unemployed"
  | "other";

export interface RelocationProfile {
  origin_country: string | null;
  destination_country: string | null;
  move_date: string | null; // ISO date string YYYY-MM-DD
  employment_type: EmploymentType | null;
  employer_country: string | null;
  has_corporate_tax_support: boolean;
  works_remote: boolean | null;
  notes: string | null;
  // Convention: empty strings should be normalized to null upstream.
  missing_fields: RelocationProfileFieldName[];
}

export type PlanPhase = "pre_move" | "arrival" | "first_tax_year";
export type PlanCategory = "tax" | "social_security" | "registration" | "other";

export interface PlanItem {
  phase: PlanPhase;
  category: PlanCategory;
  title: string;
  description: string;
}

export interface RelocationPlan {
  items: PlanItem[];
  key_risks: string | null;
  assumptions: string | null;
}

export interface SourceLink {
  country: string;
  title: string;
  url: string;
}

export interface ResearchSummary {
  origin_summary: string;
  destination_summary: string;
  origin_sources: SourceLink[];
  destination_sources: SourceLink[];
}

export interface ChecklistItem {
  phase: PlanPhase;
  title: string;
  description: string;
  due_date: string | null; // ISO date string YYYY-MM-DD
  relative_to_move: string | null;
}

export interface RelocationChecklist {
  items: ChecklistItem[];
}

export interface ClarificationOutput {
  text: string;
}

export interface DraftOutputs {
  final_markdown: string;
  email_template_hr: string | null;
}
