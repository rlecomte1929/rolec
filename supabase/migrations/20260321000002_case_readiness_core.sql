-- Case Readiness Core v1: reusable templates + per-assignment state (no duplicate template rows per case).

CREATE TABLE IF NOT EXISTS public.readiness_templates (
  id text PRIMARY KEY,
  destination_key text NOT NULL,
  route_key text NOT NULL DEFAULT 'employment',
  route_title text NOT NULL,
  employee_summary text NOT NULL DEFAULT '',
  hr_summary text NOT NULL DEFAULT '',
  internal_notes_hr text,
  watchouts_json text NOT NULL DEFAULT '[]',
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (destination_key, route_key)
);

CREATE INDEX IF NOT EXISTS idx_readiness_templates_dest ON public.readiness_templates (destination_key);

CREATE TABLE IF NOT EXISTS public.readiness_template_checklist_items (
  id text PRIMARY KEY,
  template_id text NOT NULL REFERENCES public.readiness_templates(id) ON DELETE CASCADE,
  sort_order integer NOT NULL DEFAULT 0,
  title text NOT NULL,
  owner_role text NOT NULL DEFAULT 'employee',
  required integer NOT NULL DEFAULT 1,
  depends_on_sort_order integer,
  notes_employee text,
  notes_hr text,
  stable_key text
);

CREATE INDEX IF NOT EXISTS idx_readiness_tmpl_chk_template
  ON public.readiness_template_checklist_items (template_id, sort_order);

CREATE TABLE IF NOT EXISTS public.readiness_template_milestones (
  id text PRIMARY KEY,
  template_id text NOT NULL REFERENCES public.readiness_templates(id) ON DELETE CASCADE,
  sort_order integer NOT NULL DEFAULT 0,
  phase text NOT NULL DEFAULT 'general',
  title text NOT NULL,
  body_employee text,
  body_hr text,
  owner_role text NOT NULL DEFAULT 'hr',
  relative_timing text
);

CREATE INDEX IF NOT EXISTS idx_readiness_tmpl_ms_template
  ON public.readiness_template_milestones (template_id, sort_order);

CREATE TABLE IF NOT EXISTS public.case_readiness (
  assignment_id text PRIMARY KEY,
  template_id text NOT NULL REFERENCES public.readiness_templates(id) ON DELETE RESTRICT,
  destination_key text NOT NULL,
  route_key text NOT NULL,
  case_note_hr text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_case_readiness_template ON public.case_readiness (template_id);

CREATE TABLE IF NOT EXISTS public.case_readiness_checklist_state (
  assignment_id text NOT NULL,
  template_checklist_id text NOT NULL REFERENCES public.readiness_template_checklist_items(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending',
  notes text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (assignment_id, template_checklist_id)
);

CREATE INDEX IF NOT EXISTS idx_crcs_assignment ON public.case_readiness_checklist_state (assignment_id);

CREATE TABLE IF NOT EXISTS public.case_readiness_milestone_state (
  assignment_id text NOT NULL,
  template_milestone_id text NOT NULL REFERENCES public.readiness_template_milestones(id) ON DELETE CASCADE,
  completed_at timestamptz,
  notes text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (assignment_id, template_milestone_id)
);

CREATE INDEX IF NOT EXISTS idx_crms_assignment ON public.case_readiness_milestone_state (assignment_id);

COMMENT ON TABLE public.readiness_templates IS 'Destination/route readiness pack templates; shared across companies.';
COMMENT ON TABLE public.case_readiness IS 'Links one assignment to the resolved template; no copy of template text.';
