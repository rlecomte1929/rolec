drop extension if exists "pg_net";

create sequence "public"."answers_id_seq";

create sequence "public"."employee_answers_id_seq";


  create table "public"."admin_allowlist" (
    "email" text not null,
    "enabled" integer not null default 1,
    "added_by_user_id" text,
    "created_at" text not null
      );



  create table "public"."admin_sessions" (
    "token" text not null,
    "actor_user_id" text not null,
    "target_user_id" text not null,
    "mode" text not null,
    "created_at" text not null
      );



  create table "public"."answers" (
    "id" integer not null default nextval('public.answers_id_seq'::regclass),
    "user_id" text not null,
    "question_id" text not null,
    "answer_json" text not null,
    "is_unknown" integer not null default 0,
    "created_at" text not null
      );



  create table "public"."assignment_invites" (
    "id" text not null,
    "case_id" text not null,
    "hr_user_id" text not null,
    "employee_identifier" text not null,
    "token" text not null,
    "status" text not null,
    "created_at" text not null
      );



  create table "public"."audit_log" (
    "id" text not null,
    "actor_user_id" text not null,
    "action_type" text not null,
    "target_type" text not null,
    "target_id" text,
    "reason" text,
    "metadata_json" text,
    "created_at" text not null
      );



  create table "public"."case_assignments" (
    "id" text not null,
    "case_id" text not null,
    "hr_user_id" text not null,
    "employee_user_id" text,
    "employee_identifier" text not null,
    "status" text not null,
    "created_at" text not null,
    "updated_at" text not null,
    "submitted_at" text,
    "hr_notes" text,
    "decision" text
      );



  create table "public"."case_requirements_snapshots" (
    "id" character varying not null,
    "case_id" character varying,
    "dest_country" character varying not null,
    "purpose" character varying not null,
    "created_at" timestamp without time zone not null,
    "snapshot_json" text not null,
    "sources_json" text not null
      );



  create table "public"."companies" (
    "id" text not null,
    "name" text not null,
    "country" text,
    "size_band" text,
    "created_at" text not null,
    "address" text,
    "phone" text,
    "hr_contact" text
      );



  create table "public"."compliance_actions" (
    "id" text not null,
    "assignment_id" text not null,
    "check_id" text not null,
    "action_type" text not null,
    "notes" text,
    "actor_user_id" text not null,
    "created_at" text not null
      );



  create table "public"."compliance_reports" (
    "id" text not null,
    "assignment_id" text not null,
    "report_json" text not null,
    "created_at" text not null
      );



  create table "public"."compliance_runs" (
    "id" text not null,
    "assignment_id" text not null,
    "report_json" text not null,
    "created_at" text not null
      );



  create table "public"."country_profiles" (
    "id" character varying not null,
    "country_code" character varying,
    "last_updated_at" timestamp without time zone,
    "confidence_score" double precision,
    "notes" text
      );



  create table "public"."eligibility_overrides" (
    "id" text not null,
    "assignment_id" text not null,
    "category" text not null,
    "allowed" integer not null default 1,
    "expires_at" text,
    "note" text,
    "created_by_user_id" text not null,
    "created_at" text not null
      );



  create table "public"."employee_answers" (
    "id" integer not null default nextval('public.employee_answers_id_seq'::regclass),
    "assignment_id" text not null,
    "question_id" text not null,
    "answer_json" text not null,
    "created_at" text not null
      );



  create table "public"."employee_profiles" (
    "assignment_id" text not null,
    "profile_json" text not null,
    "updated_at" text not null
      );



  create table "public"."employees" (
    "id" text not null,
    "company_id" text not null,
    "profile_id" text not null,
    "band" text,
    "assignment_type" text,
    "relocation_case_id" text,
    "status" text,
    "created_at" text not null
      );



  create table "public"."hr_policies" (
    "id" text not null,
    "policy_json" text not null,
    "status" text not null default 'draft'::text,
    "company_entity" text,
    "effective_date" text,
    "created_at" text not null,
    "updated_at" text not null,
    "created_by" text,
    "version" integer not null default 1
      );



  create table "public"."hr_users" (
    "id" text not null,
    "company_id" text not null,
    "profile_id" text not null,
    "permissions_json" text,
    "created_at" text not null
      );



  create table "public"."messages" (
    "id" text not null,
    "assignment_id" text,
    "hr_user_id" text,
    "employee_identifier" text,
    "subject" text not null,
    "body" text not null,
    "status" text not null default 'draft'::text,
    "created_at" text not null
      );



  create table "public"."policy_exceptions" (
    "id" text not null,
    "assignment_id" text not null,
    "category" text not null,
    "status" text not null,
    "reason" text,
    "requested_amount" real,
    "requested_by" text not null,
    "created_at" text not null,
    "updated_at" text not null
      );



  create table "public"."profile_state" (
    "user_id" text not null,
    "profile_json" text not null,
    "updated_at" text not null
      );



  create table "public"."profiles" (
    "id" text not null,
    "role" text not null,
    "email" text,
    "full_name" text,
    "company_id" text,
    "created_at" text not null
      );



  create table "public"."relocation_cases" (
    "id" text not null,
    "hr_user_id" text not null,
    "profile_json" text not null,
    "created_at" text not null,
    "updated_at" text not null,
    "company_id" text,
    "employee_id" text,
    "status" text,
    "stage" text,
    "host_country" text,
    "home_country" text
      );



  create table "public"."requirement_items" (
    "id" character varying not null,
    "country_code" character varying,
    "purpose" character varying not null,
    "pillar" character varying not null,
    "title" character varying not null,
    "description" text not null,
    "severity" character varying not null,
    "owner" character varying not null,
    "required_fields_json" text not null,
    "citations_json" text not null,
    "last_verified_at" timestamp without time zone not null
      );



  create table "public"."rp_debug_kv" (
    "id" text not null,
    "key" text not null,
    "value" text not null,
    "updated_at" text not null
      );



  create table "public"."sessions" (
    "token" text not null,
    "user_id" text not null,
    "created_at" text not null
      );



  create table "public"."source_records" (
    "id" character varying not null,
    "country_code" character varying,
    "url" character varying not null,
    "title" character varying not null,
    "publisher_domain" character varying not null,
    "retrieved_at" timestamp without time zone not null,
    "snippet" text,
    "content_hash" character varying not null
      );



  create table "public"."support_case_notes" (
    "id" text not null,
    "support_case_id" text not null,
    "author_user_id" text not null,
    "note" text not null,
    "created_at" text not null
      );



  create table "public"."support_cases" (
    "id" text not null,
    "company_id" text not null,
    "created_by_profile_id" text not null,
    "employee_id" text,
    "hr_profile_id" text,
    "category" text not null,
    "severity" text not null,
    "status" text not null,
    "summary" text,
    "last_error_code" text,
    "last_error_context_json" text,
    "created_at" text not null,
    "updated_at" text not null
      );



  create table "public"."users" (
    "id" text not null,
    "username" text,
    "email" text,
    "password_hash" text,
    "role" text not null,
    "name" text,
    "created_at" text not null
      );



  create table "public"."wizard_cases" (
    "id" character varying not null,
    "draft_json" text not null,
    "created_at" timestamp without time zone not null default now(),
    "updated_at" timestamp without time zone not null default now(),
    "origin_country" character varying,
    "origin_city" character varying,
    "dest_country" character varying,
    "dest_city" character varying,
    "purpose" character varying,
    "target_move_date" date,
    "flags_json" text,
    "status" character varying not null,
    "requirements_snapshot_id" character varying
      );


alter sequence "public"."answers_id_seq" owned by "public"."answers"."id";

alter sequence "public"."employee_answers_id_seq" owned by "public"."employee_answers"."id";

CREATE UNIQUE INDEX admin_allowlist_pkey ON public.admin_allowlist USING btree (email);

CREATE UNIQUE INDEX admin_sessions_pkey ON public.admin_sessions USING btree (token);

CREATE UNIQUE INDEX answers_pkey ON public.answers USING btree (id);

CREATE UNIQUE INDEX assignment_invites_pkey ON public.assignment_invites USING btree (id);

CREATE UNIQUE INDEX audit_log_pkey ON public.audit_log USING btree (id);

CREATE UNIQUE INDEX case_assignments_pkey ON public.case_assignments USING btree (id);

CREATE UNIQUE INDEX case_requirements_snapshots_pkey ON public.case_requirements_snapshots USING btree (id);

CREATE UNIQUE INDEX companies_pkey ON public.companies USING btree (id);

CREATE UNIQUE INDEX compliance_actions_pkey ON public.compliance_actions USING btree (id);

CREATE UNIQUE INDEX compliance_reports_pkey ON public.compliance_reports USING btree (id);

CREATE UNIQUE INDEX compliance_runs_pkey ON public.compliance_runs USING btree (id);

CREATE UNIQUE INDEX country_profiles_pkey ON public.country_profiles USING btree (id);

CREATE UNIQUE INDEX eligibility_overrides_pkey ON public.eligibility_overrides USING btree (id);

CREATE UNIQUE INDEX employee_answers_pkey ON public.employee_answers USING btree (id);

CREATE UNIQUE INDEX employee_profiles_pkey ON public.employee_profiles USING btree (assignment_id);

CREATE UNIQUE INDEX employees_pkey ON public.employees USING btree (id);

CREATE UNIQUE INDEX hr_policies_pkey ON public.hr_policies USING btree (id);

CREATE UNIQUE INDEX hr_users_pkey ON public.hr_users USING btree (id);

CREATE INDEX idx_companies_name ON public.companies USING btree (name);

CREATE INDEX idx_profiles_email ON public.profiles USING btree (email);

CREATE INDEX idx_relocation_cases_status ON public.relocation_cases USING btree (status);

CREATE INDEX idx_support_cases_severity ON public.support_cases USING btree (severity);

CREATE INDEX idx_support_cases_status ON public.support_cases USING btree (status);

CREATE INDEX ix_case_requirements_snapshots_case_id ON public.case_requirements_snapshots USING btree (case_id);

CREATE INDEX ix_case_requirements_snapshots_id ON public.case_requirements_snapshots USING btree (id);

CREATE INDEX ix_country_profiles_country_code ON public.country_profiles USING btree (country_code);

CREATE INDEX ix_country_profiles_id ON public.country_profiles USING btree (id);

CREATE INDEX ix_requirement_items_country_code ON public.requirement_items USING btree (country_code);

CREATE INDEX ix_requirement_items_id ON public.requirement_items USING btree (id);

CREATE INDEX ix_source_records_country_code ON public.source_records USING btree (country_code);

CREATE INDEX ix_source_records_id ON public.source_records USING btree (id);

CREATE INDEX ix_wizard_cases_id ON public.wizard_cases USING btree (id);

CREATE UNIQUE INDEX messages_pkey ON public.messages USING btree (id);

CREATE UNIQUE INDEX policy_exceptions_pkey ON public.policy_exceptions USING btree (id);

CREATE UNIQUE INDEX profile_state_pkey ON public.profile_state USING btree (user_id);

CREATE UNIQUE INDEX profiles_pkey ON public.profiles USING btree (id);

CREATE UNIQUE INDEX relocation_cases_pkey ON public.relocation_cases USING btree (id);

CREATE UNIQUE INDEX requirement_items_pkey ON public.requirement_items USING btree (id);

CREATE UNIQUE INDEX rp_debug_kv_key_key ON public.rp_debug_kv USING btree (key);

CREATE UNIQUE INDEX rp_debug_kv_pkey ON public.rp_debug_kv USING btree (id);

CREATE UNIQUE INDEX sessions_pkey ON public.sessions USING btree (token);

CREATE UNIQUE INDEX source_records_content_hash_key ON public.source_records USING btree (content_hash);

CREATE UNIQUE INDEX source_records_pkey ON public.source_records USING btree (id);

CREATE UNIQUE INDEX support_case_notes_pkey ON public.support_case_notes USING btree (id);

CREATE UNIQUE INDEX support_cases_pkey ON public.support_cases USING btree (id);

CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email);

CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id);

CREATE UNIQUE INDEX users_username_key ON public.users USING btree (username);

CREATE UNIQUE INDEX wizard_cases_pkey ON public.wizard_cases USING btree (id);

alter table "public"."admin_allowlist" add constraint "admin_allowlist_pkey" PRIMARY KEY using index "admin_allowlist_pkey";

alter table "public"."admin_sessions" add constraint "admin_sessions_pkey" PRIMARY KEY using index "admin_sessions_pkey";

alter table "public"."answers" add constraint "answers_pkey" PRIMARY KEY using index "answers_pkey";

alter table "public"."assignment_invites" add constraint "assignment_invites_pkey" PRIMARY KEY using index "assignment_invites_pkey";

alter table "public"."audit_log" add constraint "audit_log_pkey" PRIMARY KEY using index "audit_log_pkey";

alter table "public"."case_assignments" add constraint "case_assignments_pkey" PRIMARY KEY using index "case_assignments_pkey";

alter table "public"."case_requirements_snapshots" add constraint "case_requirements_snapshots_pkey" PRIMARY KEY using index "case_requirements_snapshots_pkey";

alter table "public"."companies" add constraint "companies_pkey" PRIMARY KEY using index "companies_pkey";

alter table "public"."compliance_actions" add constraint "compliance_actions_pkey" PRIMARY KEY using index "compliance_actions_pkey";

alter table "public"."compliance_reports" add constraint "compliance_reports_pkey" PRIMARY KEY using index "compliance_reports_pkey";

alter table "public"."compliance_runs" add constraint "compliance_runs_pkey" PRIMARY KEY using index "compliance_runs_pkey";

alter table "public"."country_profiles" add constraint "country_profiles_pkey" PRIMARY KEY using index "country_profiles_pkey";

alter table "public"."eligibility_overrides" add constraint "eligibility_overrides_pkey" PRIMARY KEY using index "eligibility_overrides_pkey";

alter table "public"."employee_answers" add constraint "employee_answers_pkey" PRIMARY KEY using index "employee_answers_pkey";

alter table "public"."employee_profiles" add constraint "employee_profiles_pkey" PRIMARY KEY using index "employee_profiles_pkey";

alter table "public"."employees" add constraint "employees_pkey" PRIMARY KEY using index "employees_pkey";

alter table "public"."hr_policies" add constraint "hr_policies_pkey" PRIMARY KEY using index "hr_policies_pkey";

alter table "public"."hr_users" add constraint "hr_users_pkey" PRIMARY KEY using index "hr_users_pkey";

alter table "public"."messages" add constraint "messages_pkey" PRIMARY KEY using index "messages_pkey";

alter table "public"."policy_exceptions" add constraint "policy_exceptions_pkey" PRIMARY KEY using index "policy_exceptions_pkey";

alter table "public"."profile_state" add constraint "profile_state_pkey" PRIMARY KEY using index "profile_state_pkey";

alter table "public"."profiles" add constraint "profiles_pkey" PRIMARY KEY using index "profiles_pkey";

alter table "public"."relocation_cases" add constraint "relocation_cases_pkey" PRIMARY KEY using index "relocation_cases_pkey";

alter table "public"."requirement_items" add constraint "requirement_items_pkey" PRIMARY KEY using index "requirement_items_pkey";

alter table "public"."rp_debug_kv" add constraint "rp_debug_kv_pkey" PRIMARY KEY using index "rp_debug_kv_pkey";

alter table "public"."sessions" add constraint "sessions_pkey" PRIMARY KEY using index "sessions_pkey";

alter table "public"."source_records" add constraint "source_records_pkey" PRIMARY KEY using index "source_records_pkey";

alter table "public"."support_case_notes" add constraint "support_case_notes_pkey" PRIMARY KEY using index "support_case_notes_pkey";

alter table "public"."support_cases" add constraint "support_cases_pkey" PRIMARY KEY using index "support_cases_pkey";

alter table "public"."users" add constraint "users_pkey" PRIMARY KEY using index "users_pkey";

alter table "public"."wizard_cases" add constraint "wizard_cases_pkey" PRIMARY KEY using index "wizard_cases_pkey";

alter table "public"."rp_debug_kv" add constraint "rp_debug_kv_key_key" UNIQUE using index "rp_debug_kv_key_key";

alter table "public"."source_records" add constraint "source_records_content_hash_key" UNIQUE using index "source_records_content_hash_key";

alter table "public"."users" add constraint "users_email_key" UNIQUE using index "users_email_key";

alter table "public"."users" add constraint "users_username_key" UNIQUE using index "users_username_key";

grant delete on table "public"."admin_allowlist" to "anon";

grant insert on table "public"."admin_allowlist" to "anon";

grant references on table "public"."admin_allowlist" to "anon";

grant select on table "public"."admin_allowlist" to "anon";

grant trigger on table "public"."admin_allowlist" to "anon";

grant truncate on table "public"."admin_allowlist" to "anon";

grant update on table "public"."admin_allowlist" to "anon";

grant delete on table "public"."admin_allowlist" to "authenticated";

grant insert on table "public"."admin_allowlist" to "authenticated";

grant references on table "public"."admin_allowlist" to "authenticated";

grant select on table "public"."admin_allowlist" to "authenticated";

grant trigger on table "public"."admin_allowlist" to "authenticated";

grant truncate on table "public"."admin_allowlist" to "authenticated";

grant update on table "public"."admin_allowlist" to "authenticated";

grant delete on table "public"."admin_allowlist" to "service_role";

grant insert on table "public"."admin_allowlist" to "service_role";

grant references on table "public"."admin_allowlist" to "service_role";

grant select on table "public"."admin_allowlist" to "service_role";

grant trigger on table "public"."admin_allowlist" to "service_role";

grant truncate on table "public"."admin_allowlist" to "service_role";

grant update on table "public"."admin_allowlist" to "service_role";

grant delete on table "public"."admin_sessions" to "anon";

grant insert on table "public"."admin_sessions" to "anon";

grant references on table "public"."admin_sessions" to "anon";

grant select on table "public"."admin_sessions" to "anon";

grant trigger on table "public"."admin_sessions" to "anon";

grant truncate on table "public"."admin_sessions" to "anon";

grant update on table "public"."admin_sessions" to "anon";

grant delete on table "public"."admin_sessions" to "authenticated";

grant insert on table "public"."admin_sessions" to "authenticated";

grant references on table "public"."admin_sessions" to "authenticated";

grant select on table "public"."admin_sessions" to "authenticated";

grant trigger on table "public"."admin_sessions" to "authenticated";

grant truncate on table "public"."admin_sessions" to "authenticated";

grant update on table "public"."admin_sessions" to "authenticated";

grant delete on table "public"."admin_sessions" to "service_role";

grant insert on table "public"."admin_sessions" to "service_role";

grant references on table "public"."admin_sessions" to "service_role";

grant select on table "public"."admin_sessions" to "service_role";

grant trigger on table "public"."admin_sessions" to "service_role";

grant truncate on table "public"."admin_sessions" to "service_role";

grant update on table "public"."admin_sessions" to "service_role";

grant delete on table "public"."answers" to "anon";

grant insert on table "public"."answers" to "anon";

grant references on table "public"."answers" to "anon";

grant select on table "public"."answers" to "anon";

grant trigger on table "public"."answers" to "anon";

grant truncate on table "public"."answers" to "anon";

grant update on table "public"."answers" to "anon";

grant delete on table "public"."answers" to "authenticated";

grant insert on table "public"."answers" to "authenticated";

grant references on table "public"."answers" to "authenticated";

grant select on table "public"."answers" to "authenticated";

grant trigger on table "public"."answers" to "authenticated";

grant truncate on table "public"."answers" to "authenticated";

grant update on table "public"."answers" to "authenticated";

grant delete on table "public"."answers" to "service_role";

grant insert on table "public"."answers" to "service_role";

grant references on table "public"."answers" to "service_role";

grant select on table "public"."answers" to "service_role";

grant trigger on table "public"."answers" to "service_role";

grant truncate on table "public"."answers" to "service_role";

grant update on table "public"."answers" to "service_role";

grant delete on table "public"."assignment_invites" to "anon";

grant insert on table "public"."assignment_invites" to "anon";

grant references on table "public"."assignment_invites" to "anon";

grant select on table "public"."assignment_invites" to "anon";

grant trigger on table "public"."assignment_invites" to "anon";

grant truncate on table "public"."assignment_invites" to "anon";

grant update on table "public"."assignment_invites" to "anon";

grant delete on table "public"."assignment_invites" to "authenticated";

grant insert on table "public"."assignment_invites" to "authenticated";

grant references on table "public"."assignment_invites" to "authenticated";

grant select on table "public"."assignment_invites" to "authenticated";

grant trigger on table "public"."assignment_invites" to "authenticated";

grant truncate on table "public"."assignment_invites" to "authenticated";

grant update on table "public"."assignment_invites" to "authenticated";

grant delete on table "public"."assignment_invites" to "service_role";

grant insert on table "public"."assignment_invites" to "service_role";

grant references on table "public"."assignment_invites" to "service_role";

grant select on table "public"."assignment_invites" to "service_role";

grant trigger on table "public"."assignment_invites" to "service_role";

grant truncate on table "public"."assignment_invites" to "service_role";

grant update on table "public"."assignment_invites" to "service_role";

grant delete on table "public"."audit_log" to "anon";

grant insert on table "public"."audit_log" to "anon";

grant references on table "public"."audit_log" to "anon";

grant select on table "public"."audit_log" to "anon";

grant trigger on table "public"."audit_log" to "anon";

grant truncate on table "public"."audit_log" to "anon";

grant update on table "public"."audit_log" to "anon";

grant delete on table "public"."audit_log" to "authenticated";

grant insert on table "public"."audit_log" to "authenticated";

grant references on table "public"."audit_log" to "authenticated";

grant select on table "public"."audit_log" to "authenticated";

grant trigger on table "public"."audit_log" to "authenticated";

grant truncate on table "public"."audit_log" to "authenticated";

grant update on table "public"."audit_log" to "authenticated";

grant delete on table "public"."audit_log" to "service_role";

grant insert on table "public"."audit_log" to "service_role";

grant references on table "public"."audit_log" to "service_role";

grant select on table "public"."audit_log" to "service_role";

grant trigger on table "public"."audit_log" to "service_role";

grant truncate on table "public"."audit_log" to "service_role";

grant update on table "public"."audit_log" to "service_role";

grant delete on table "public"."case_assignments" to "anon";

grant insert on table "public"."case_assignments" to "anon";

grant references on table "public"."case_assignments" to "anon";

grant select on table "public"."case_assignments" to "anon";

grant trigger on table "public"."case_assignments" to "anon";

grant truncate on table "public"."case_assignments" to "anon";

grant update on table "public"."case_assignments" to "anon";

grant delete on table "public"."case_assignments" to "authenticated";

grant insert on table "public"."case_assignments" to "authenticated";

grant references on table "public"."case_assignments" to "authenticated";

grant select on table "public"."case_assignments" to "authenticated";

grant trigger on table "public"."case_assignments" to "authenticated";

grant truncate on table "public"."case_assignments" to "authenticated";

grant update on table "public"."case_assignments" to "authenticated";

grant delete on table "public"."case_assignments" to "service_role";

grant insert on table "public"."case_assignments" to "service_role";

grant references on table "public"."case_assignments" to "service_role";

grant select on table "public"."case_assignments" to "service_role";

grant trigger on table "public"."case_assignments" to "service_role";

grant truncate on table "public"."case_assignments" to "service_role";

grant update on table "public"."case_assignments" to "service_role";

grant delete on table "public"."case_requirements_snapshots" to "anon";

grant insert on table "public"."case_requirements_snapshots" to "anon";

grant references on table "public"."case_requirements_snapshots" to "anon";

grant select on table "public"."case_requirements_snapshots" to "anon";

grant trigger on table "public"."case_requirements_snapshots" to "anon";

grant truncate on table "public"."case_requirements_snapshots" to "anon";

grant update on table "public"."case_requirements_snapshots" to "anon";

grant delete on table "public"."case_requirements_snapshots" to "authenticated";

grant insert on table "public"."case_requirements_snapshots" to "authenticated";

grant references on table "public"."case_requirements_snapshots" to "authenticated";

grant select on table "public"."case_requirements_snapshots" to "authenticated";

grant trigger on table "public"."case_requirements_snapshots" to "authenticated";

grant truncate on table "public"."case_requirements_snapshots" to "authenticated";

grant update on table "public"."case_requirements_snapshots" to "authenticated";

grant delete on table "public"."case_requirements_snapshots" to "service_role";

grant insert on table "public"."case_requirements_snapshots" to "service_role";

grant references on table "public"."case_requirements_snapshots" to "service_role";

grant select on table "public"."case_requirements_snapshots" to "service_role";

grant trigger on table "public"."case_requirements_snapshots" to "service_role";

grant truncate on table "public"."case_requirements_snapshots" to "service_role";

grant update on table "public"."case_requirements_snapshots" to "service_role";

grant delete on table "public"."companies" to "anon";

grant insert on table "public"."companies" to "anon";

grant references on table "public"."companies" to "anon";

grant select on table "public"."companies" to "anon";

grant trigger on table "public"."companies" to "anon";

grant truncate on table "public"."companies" to "anon";

grant update on table "public"."companies" to "anon";

grant delete on table "public"."companies" to "authenticated";

grant insert on table "public"."companies" to "authenticated";

grant references on table "public"."companies" to "authenticated";

grant select on table "public"."companies" to "authenticated";

grant trigger on table "public"."companies" to "authenticated";

grant truncate on table "public"."companies" to "authenticated";

grant update on table "public"."companies" to "authenticated";

grant delete on table "public"."companies" to "service_role";

grant insert on table "public"."companies" to "service_role";

grant references on table "public"."companies" to "service_role";

grant select on table "public"."companies" to "service_role";

grant trigger on table "public"."companies" to "service_role";

grant truncate on table "public"."companies" to "service_role";

grant update on table "public"."companies" to "service_role";

grant delete on table "public"."compliance_actions" to "anon";

grant insert on table "public"."compliance_actions" to "anon";

grant references on table "public"."compliance_actions" to "anon";

grant select on table "public"."compliance_actions" to "anon";

grant trigger on table "public"."compliance_actions" to "anon";

grant truncate on table "public"."compliance_actions" to "anon";

grant update on table "public"."compliance_actions" to "anon";

grant delete on table "public"."compliance_actions" to "authenticated";

grant insert on table "public"."compliance_actions" to "authenticated";

grant references on table "public"."compliance_actions" to "authenticated";

grant select on table "public"."compliance_actions" to "authenticated";

grant trigger on table "public"."compliance_actions" to "authenticated";

grant truncate on table "public"."compliance_actions" to "authenticated";

grant update on table "public"."compliance_actions" to "authenticated";

grant delete on table "public"."compliance_actions" to "service_role";

grant insert on table "public"."compliance_actions" to "service_role";

grant references on table "public"."compliance_actions" to "service_role";

grant select on table "public"."compliance_actions" to "service_role";

grant trigger on table "public"."compliance_actions" to "service_role";

grant truncate on table "public"."compliance_actions" to "service_role";

grant update on table "public"."compliance_actions" to "service_role";

grant delete on table "public"."compliance_reports" to "anon";

grant insert on table "public"."compliance_reports" to "anon";

grant references on table "public"."compliance_reports" to "anon";

grant select on table "public"."compliance_reports" to "anon";

grant trigger on table "public"."compliance_reports" to "anon";

grant truncate on table "public"."compliance_reports" to "anon";

grant update on table "public"."compliance_reports" to "anon";

grant delete on table "public"."compliance_reports" to "authenticated";

grant insert on table "public"."compliance_reports" to "authenticated";

grant references on table "public"."compliance_reports" to "authenticated";

grant select on table "public"."compliance_reports" to "authenticated";

grant trigger on table "public"."compliance_reports" to "authenticated";

grant truncate on table "public"."compliance_reports" to "authenticated";

grant update on table "public"."compliance_reports" to "authenticated";

grant delete on table "public"."compliance_reports" to "service_role";

grant insert on table "public"."compliance_reports" to "service_role";

grant references on table "public"."compliance_reports" to "service_role";

grant select on table "public"."compliance_reports" to "service_role";

grant trigger on table "public"."compliance_reports" to "service_role";

grant truncate on table "public"."compliance_reports" to "service_role";

grant update on table "public"."compliance_reports" to "service_role";

grant delete on table "public"."compliance_runs" to "anon";

grant insert on table "public"."compliance_runs" to "anon";

grant references on table "public"."compliance_runs" to "anon";

grant select on table "public"."compliance_runs" to "anon";

grant trigger on table "public"."compliance_runs" to "anon";

grant truncate on table "public"."compliance_runs" to "anon";

grant update on table "public"."compliance_runs" to "anon";

grant delete on table "public"."compliance_runs" to "authenticated";

grant insert on table "public"."compliance_runs" to "authenticated";

grant references on table "public"."compliance_runs" to "authenticated";

grant select on table "public"."compliance_runs" to "authenticated";

grant trigger on table "public"."compliance_runs" to "authenticated";

grant truncate on table "public"."compliance_runs" to "authenticated";

grant update on table "public"."compliance_runs" to "authenticated";

grant delete on table "public"."compliance_runs" to "service_role";

grant insert on table "public"."compliance_runs" to "service_role";

grant references on table "public"."compliance_runs" to "service_role";

grant select on table "public"."compliance_runs" to "service_role";

grant trigger on table "public"."compliance_runs" to "service_role";

grant truncate on table "public"."compliance_runs" to "service_role";

grant update on table "public"."compliance_runs" to "service_role";

grant delete on table "public"."country_profiles" to "anon";

grant insert on table "public"."country_profiles" to "anon";

grant references on table "public"."country_profiles" to "anon";

grant select on table "public"."country_profiles" to "anon";

grant trigger on table "public"."country_profiles" to "anon";

grant truncate on table "public"."country_profiles" to "anon";

grant update on table "public"."country_profiles" to "anon";

grant delete on table "public"."country_profiles" to "authenticated";

grant insert on table "public"."country_profiles" to "authenticated";

grant references on table "public"."country_profiles" to "authenticated";

grant select on table "public"."country_profiles" to "authenticated";

grant trigger on table "public"."country_profiles" to "authenticated";

grant truncate on table "public"."country_profiles" to "authenticated";

grant update on table "public"."country_profiles" to "authenticated";

grant delete on table "public"."country_profiles" to "service_role";

grant insert on table "public"."country_profiles" to "service_role";

grant references on table "public"."country_profiles" to "service_role";

grant select on table "public"."country_profiles" to "service_role";

grant trigger on table "public"."country_profiles" to "service_role";

grant truncate on table "public"."country_profiles" to "service_role";

grant update on table "public"."country_profiles" to "service_role";

grant delete on table "public"."eligibility_overrides" to "anon";

grant insert on table "public"."eligibility_overrides" to "anon";

grant references on table "public"."eligibility_overrides" to "anon";

grant select on table "public"."eligibility_overrides" to "anon";

grant trigger on table "public"."eligibility_overrides" to "anon";

grant truncate on table "public"."eligibility_overrides" to "anon";

grant update on table "public"."eligibility_overrides" to "anon";

grant delete on table "public"."eligibility_overrides" to "authenticated";

grant insert on table "public"."eligibility_overrides" to "authenticated";

grant references on table "public"."eligibility_overrides" to "authenticated";

grant select on table "public"."eligibility_overrides" to "authenticated";

grant trigger on table "public"."eligibility_overrides" to "authenticated";

grant truncate on table "public"."eligibility_overrides" to "authenticated";

grant update on table "public"."eligibility_overrides" to "authenticated";

grant delete on table "public"."eligibility_overrides" to "service_role";

grant insert on table "public"."eligibility_overrides" to "service_role";

grant references on table "public"."eligibility_overrides" to "service_role";

grant select on table "public"."eligibility_overrides" to "service_role";

grant trigger on table "public"."eligibility_overrides" to "service_role";

grant truncate on table "public"."eligibility_overrides" to "service_role";

grant update on table "public"."eligibility_overrides" to "service_role";

grant delete on table "public"."employee_answers" to "anon";

grant insert on table "public"."employee_answers" to "anon";

grant references on table "public"."employee_answers" to "anon";

grant select on table "public"."employee_answers" to "anon";

grant trigger on table "public"."employee_answers" to "anon";

grant truncate on table "public"."employee_answers" to "anon";

grant update on table "public"."employee_answers" to "anon";

grant delete on table "public"."employee_answers" to "authenticated";

grant insert on table "public"."employee_answers" to "authenticated";

grant references on table "public"."employee_answers" to "authenticated";

grant select on table "public"."employee_answers" to "authenticated";

grant trigger on table "public"."employee_answers" to "authenticated";

grant truncate on table "public"."employee_answers" to "authenticated";

grant update on table "public"."employee_answers" to "authenticated";

grant delete on table "public"."employee_answers" to "service_role";

grant insert on table "public"."employee_answers" to "service_role";

grant references on table "public"."employee_answers" to "service_role";

grant select on table "public"."employee_answers" to "service_role";

grant trigger on table "public"."employee_answers" to "service_role";

grant truncate on table "public"."employee_answers" to "service_role";

grant update on table "public"."employee_answers" to "service_role";

grant delete on table "public"."employee_profiles" to "anon";

grant insert on table "public"."employee_profiles" to "anon";

grant references on table "public"."employee_profiles" to "anon";

grant select on table "public"."employee_profiles" to "anon";

grant trigger on table "public"."employee_profiles" to "anon";

grant truncate on table "public"."employee_profiles" to "anon";

grant update on table "public"."employee_profiles" to "anon";

grant delete on table "public"."employee_profiles" to "authenticated";

grant insert on table "public"."employee_profiles" to "authenticated";

grant references on table "public"."employee_profiles" to "authenticated";

grant select on table "public"."employee_profiles" to "authenticated";

grant trigger on table "public"."employee_profiles" to "authenticated";

grant truncate on table "public"."employee_profiles" to "authenticated";

grant update on table "public"."employee_profiles" to "authenticated";

grant delete on table "public"."employee_profiles" to "service_role";

grant insert on table "public"."employee_profiles" to "service_role";

grant references on table "public"."employee_profiles" to "service_role";

grant select on table "public"."employee_profiles" to "service_role";

grant trigger on table "public"."employee_profiles" to "service_role";

grant truncate on table "public"."employee_profiles" to "service_role";

grant update on table "public"."employee_profiles" to "service_role";

grant delete on table "public"."employees" to "anon";

grant insert on table "public"."employees" to "anon";

grant references on table "public"."employees" to "anon";

grant select on table "public"."employees" to "anon";

grant trigger on table "public"."employees" to "anon";

grant truncate on table "public"."employees" to "anon";

grant update on table "public"."employees" to "anon";

grant delete on table "public"."employees" to "authenticated";

grant insert on table "public"."employees" to "authenticated";

grant references on table "public"."employees" to "authenticated";

grant select on table "public"."employees" to "authenticated";

grant trigger on table "public"."employees" to "authenticated";

grant truncate on table "public"."employees" to "authenticated";

grant update on table "public"."employees" to "authenticated";

grant delete on table "public"."employees" to "service_role";

grant insert on table "public"."employees" to "service_role";

grant references on table "public"."employees" to "service_role";

grant select on table "public"."employees" to "service_role";

grant trigger on table "public"."employees" to "service_role";

grant truncate on table "public"."employees" to "service_role";

grant update on table "public"."employees" to "service_role";

grant delete on table "public"."hr_policies" to "anon";

grant insert on table "public"."hr_policies" to "anon";

grant references on table "public"."hr_policies" to "anon";

grant select on table "public"."hr_policies" to "anon";

grant trigger on table "public"."hr_policies" to "anon";

grant truncate on table "public"."hr_policies" to "anon";

grant update on table "public"."hr_policies" to "anon";

grant delete on table "public"."hr_policies" to "authenticated";

grant insert on table "public"."hr_policies" to "authenticated";

grant references on table "public"."hr_policies" to "authenticated";

grant select on table "public"."hr_policies" to "authenticated";

grant trigger on table "public"."hr_policies" to "authenticated";

grant truncate on table "public"."hr_policies" to "authenticated";

grant update on table "public"."hr_policies" to "authenticated";

grant delete on table "public"."hr_policies" to "service_role";

grant insert on table "public"."hr_policies" to "service_role";

grant references on table "public"."hr_policies" to "service_role";

grant select on table "public"."hr_policies" to "service_role";

grant trigger on table "public"."hr_policies" to "service_role";

grant truncate on table "public"."hr_policies" to "service_role";

grant update on table "public"."hr_policies" to "service_role";

grant delete on table "public"."hr_users" to "anon";

grant insert on table "public"."hr_users" to "anon";

grant references on table "public"."hr_users" to "anon";

grant select on table "public"."hr_users" to "anon";

grant trigger on table "public"."hr_users" to "anon";

grant truncate on table "public"."hr_users" to "anon";

grant update on table "public"."hr_users" to "anon";

grant delete on table "public"."hr_users" to "authenticated";

grant insert on table "public"."hr_users" to "authenticated";

grant references on table "public"."hr_users" to "authenticated";

grant select on table "public"."hr_users" to "authenticated";

grant trigger on table "public"."hr_users" to "authenticated";

grant truncate on table "public"."hr_users" to "authenticated";

grant update on table "public"."hr_users" to "authenticated";

grant delete on table "public"."hr_users" to "service_role";

grant insert on table "public"."hr_users" to "service_role";

grant references on table "public"."hr_users" to "service_role";

grant select on table "public"."hr_users" to "service_role";

grant trigger on table "public"."hr_users" to "service_role";

grant truncate on table "public"."hr_users" to "service_role";

grant update on table "public"."hr_users" to "service_role";

grant delete on table "public"."messages" to "anon";

grant insert on table "public"."messages" to "anon";

grant references on table "public"."messages" to "anon";

grant select on table "public"."messages" to "anon";

grant trigger on table "public"."messages" to "anon";

grant truncate on table "public"."messages" to "anon";

grant update on table "public"."messages" to "anon";

grant delete on table "public"."messages" to "authenticated";

grant insert on table "public"."messages" to "authenticated";

grant references on table "public"."messages" to "authenticated";

grant select on table "public"."messages" to "authenticated";

grant trigger on table "public"."messages" to "authenticated";

grant truncate on table "public"."messages" to "authenticated";

grant update on table "public"."messages" to "authenticated";

grant delete on table "public"."messages" to "service_role";

grant insert on table "public"."messages" to "service_role";

grant references on table "public"."messages" to "service_role";

grant select on table "public"."messages" to "service_role";

grant trigger on table "public"."messages" to "service_role";

grant truncate on table "public"."messages" to "service_role";

grant update on table "public"."messages" to "service_role";

grant delete on table "public"."policy_exceptions" to "anon";

grant insert on table "public"."policy_exceptions" to "anon";

grant references on table "public"."policy_exceptions" to "anon";

grant select on table "public"."policy_exceptions" to "anon";

grant trigger on table "public"."policy_exceptions" to "anon";

grant truncate on table "public"."policy_exceptions" to "anon";

grant update on table "public"."policy_exceptions" to "anon";

grant delete on table "public"."policy_exceptions" to "authenticated";

grant insert on table "public"."policy_exceptions" to "authenticated";

grant references on table "public"."policy_exceptions" to "authenticated";

grant select on table "public"."policy_exceptions" to "authenticated";

grant trigger on table "public"."policy_exceptions" to "authenticated";

grant truncate on table "public"."policy_exceptions" to "authenticated";

grant update on table "public"."policy_exceptions" to "authenticated";

grant delete on table "public"."policy_exceptions" to "service_role";

grant insert on table "public"."policy_exceptions" to "service_role";

grant references on table "public"."policy_exceptions" to "service_role";

grant select on table "public"."policy_exceptions" to "service_role";

grant trigger on table "public"."policy_exceptions" to "service_role";

grant truncate on table "public"."policy_exceptions" to "service_role";

grant update on table "public"."policy_exceptions" to "service_role";

grant delete on table "public"."profile_state" to "anon";

grant insert on table "public"."profile_state" to "anon";

grant references on table "public"."profile_state" to "anon";

grant select on table "public"."profile_state" to "anon";

grant trigger on table "public"."profile_state" to "anon";

grant truncate on table "public"."profile_state" to "anon";

grant update on table "public"."profile_state" to "anon";

grant delete on table "public"."profile_state" to "authenticated";

grant insert on table "public"."profile_state" to "authenticated";

grant references on table "public"."profile_state" to "authenticated";

grant select on table "public"."profile_state" to "authenticated";

grant trigger on table "public"."profile_state" to "authenticated";

grant truncate on table "public"."profile_state" to "authenticated";

grant update on table "public"."profile_state" to "authenticated";

grant delete on table "public"."profile_state" to "service_role";

grant insert on table "public"."profile_state" to "service_role";

grant references on table "public"."profile_state" to "service_role";

grant select on table "public"."profile_state" to "service_role";

grant trigger on table "public"."profile_state" to "service_role";

grant truncate on table "public"."profile_state" to "service_role";

grant update on table "public"."profile_state" to "service_role";

grant delete on table "public"."profiles" to "anon";

grant insert on table "public"."profiles" to "anon";

grant references on table "public"."profiles" to "anon";

grant select on table "public"."profiles" to "anon";

grant trigger on table "public"."profiles" to "anon";

grant truncate on table "public"."profiles" to "anon";

grant update on table "public"."profiles" to "anon";

grant delete on table "public"."profiles" to "authenticated";

grant insert on table "public"."profiles" to "authenticated";

grant references on table "public"."profiles" to "authenticated";

grant select on table "public"."profiles" to "authenticated";

grant trigger on table "public"."profiles" to "authenticated";

grant truncate on table "public"."profiles" to "authenticated";

grant update on table "public"."profiles" to "authenticated";

grant delete on table "public"."profiles" to "service_role";

grant insert on table "public"."profiles" to "service_role";

grant references on table "public"."profiles" to "service_role";

grant select on table "public"."profiles" to "service_role";

grant trigger on table "public"."profiles" to "service_role";

grant truncate on table "public"."profiles" to "service_role";

grant update on table "public"."profiles" to "service_role";

grant delete on table "public"."relocation_cases" to "anon";

grant insert on table "public"."relocation_cases" to "anon";

grant references on table "public"."relocation_cases" to "anon";

grant select on table "public"."relocation_cases" to "anon";

grant trigger on table "public"."relocation_cases" to "anon";

grant truncate on table "public"."relocation_cases" to "anon";

grant update on table "public"."relocation_cases" to "anon";

grant delete on table "public"."relocation_cases" to "authenticated";

grant insert on table "public"."relocation_cases" to "authenticated";

grant references on table "public"."relocation_cases" to "authenticated";

grant select on table "public"."relocation_cases" to "authenticated";

grant trigger on table "public"."relocation_cases" to "authenticated";

grant truncate on table "public"."relocation_cases" to "authenticated";

grant update on table "public"."relocation_cases" to "authenticated";

grant delete on table "public"."relocation_cases" to "service_role";

grant insert on table "public"."relocation_cases" to "service_role";

grant references on table "public"."relocation_cases" to "service_role";

grant select on table "public"."relocation_cases" to "service_role";

grant trigger on table "public"."relocation_cases" to "service_role";

grant truncate on table "public"."relocation_cases" to "service_role";

grant update on table "public"."relocation_cases" to "service_role";

grant delete on table "public"."requirement_items" to "anon";

grant insert on table "public"."requirement_items" to "anon";

grant references on table "public"."requirement_items" to "anon";

grant select on table "public"."requirement_items" to "anon";

grant trigger on table "public"."requirement_items" to "anon";

grant truncate on table "public"."requirement_items" to "anon";

grant update on table "public"."requirement_items" to "anon";

grant delete on table "public"."requirement_items" to "authenticated";

grant insert on table "public"."requirement_items" to "authenticated";

grant references on table "public"."requirement_items" to "authenticated";

grant select on table "public"."requirement_items" to "authenticated";

grant trigger on table "public"."requirement_items" to "authenticated";

grant truncate on table "public"."requirement_items" to "authenticated";

grant update on table "public"."requirement_items" to "authenticated";

grant delete on table "public"."requirement_items" to "service_role";

grant insert on table "public"."requirement_items" to "service_role";

grant references on table "public"."requirement_items" to "service_role";

grant select on table "public"."requirement_items" to "service_role";

grant trigger on table "public"."requirement_items" to "service_role";

grant truncate on table "public"."requirement_items" to "service_role";

grant update on table "public"."requirement_items" to "service_role";

grant delete on table "public"."rp_debug_kv" to "anon";

grant insert on table "public"."rp_debug_kv" to "anon";

grant references on table "public"."rp_debug_kv" to "anon";

grant select on table "public"."rp_debug_kv" to "anon";

grant trigger on table "public"."rp_debug_kv" to "anon";

grant truncate on table "public"."rp_debug_kv" to "anon";

grant update on table "public"."rp_debug_kv" to "anon";

grant delete on table "public"."rp_debug_kv" to "authenticated";

grant insert on table "public"."rp_debug_kv" to "authenticated";

grant references on table "public"."rp_debug_kv" to "authenticated";

grant select on table "public"."rp_debug_kv" to "authenticated";

grant trigger on table "public"."rp_debug_kv" to "authenticated";

grant truncate on table "public"."rp_debug_kv" to "authenticated";

grant update on table "public"."rp_debug_kv" to "authenticated";

grant delete on table "public"."rp_debug_kv" to "service_role";

grant insert on table "public"."rp_debug_kv" to "service_role";

grant references on table "public"."rp_debug_kv" to "service_role";

grant select on table "public"."rp_debug_kv" to "service_role";

grant trigger on table "public"."rp_debug_kv" to "service_role";

grant truncate on table "public"."rp_debug_kv" to "service_role";

grant update on table "public"."rp_debug_kv" to "service_role";

grant delete on table "public"."sessions" to "anon";

grant insert on table "public"."sessions" to "anon";

grant references on table "public"."sessions" to "anon";

grant select on table "public"."sessions" to "anon";

grant trigger on table "public"."sessions" to "anon";

grant truncate on table "public"."sessions" to "anon";

grant update on table "public"."sessions" to "anon";

grant delete on table "public"."sessions" to "authenticated";

grant insert on table "public"."sessions" to "authenticated";

grant references on table "public"."sessions" to "authenticated";

grant select on table "public"."sessions" to "authenticated";

grant trigger on table "public"."sessions" to "authenticated";

grant truncate on table "public"."sessions" to "authenticated";

grant update on table "public"."sessions" to "authenticated";

grant delete on table "public"."sessions" to "service_role";

grant insert on table "public"."sessions" to "service_role";

grant references on table "public"."sessions" to "service_role";

grant select on table "public"."sessions" to "service_role";

grant trigger on table "public"."sessions" to "service_role";

grant truncate on table "public"."sessions" to "service_role";

grant update on table "public"."sessions" to "service_role";

grant delete on table "public"."source_records" to "anon";

grant insert on table "public"."source_records" to "anon";

grant references on table "public"."source_records" to "anon";

grant select on table "public"."source_records" to "anon";

grant trigger on table "public"."source_records" to "anon";

grant truncate on table "public"."source_records" to "anon";

grant update on table "public"."source_records" to "anon";

grant delete on table "public"."source_records" to "authenticated";

grant insert on table "public"."source_records" to "authenticated";

grant references on table "public"."source_records" to "authenticated";

grant select on table "public"."source_records" to "authenticated";

grant trigger on table "public"."source_records" to "authenticated";

grant truncate on table "public"."source_records" to "authenticated";

grant update on table "public"."source_records" to "authenticated";

grant delete on table "public"."source_records" to "service_role";

grant insert on table "public"."source_records" to "service_role";

grant references on table "public"."source_records" to "service_role";

grant select on table "public"."source_records" to "service_role";

grant trigger on table "public"."source_records" to "service_role";

grant truncate on table "public"."source_records" to "service_role";

grant update on table "public"."source_records" to "service_role";

grant delete on table "public"."support_case_notes" to "anon";

grant insert on table "public"."support_case_notes" to "anon";

grant references on table "public"."support_case_notes" to "anon";

grant select on table "public"."support_case_notes" to "anon";

grant trigger on table "public"."support_case_notes" to "anon";

grant truncate on table "public"."support_case_notes" to "anon";

grant update on table "public"."support_case_notes" to "anon";

grant delete on table "public"."support_case_notes" to "authenticated";

grant insert on table "public"."support_case_notes" to "authenticated";

grant references on table "public"."support_case_notes" to "authenticated";

grant select on table "public"."support_case_notes" to "authenticated";

grant trigger on table "public"."support_case_notes" to "authenticated";

grant truncate on table "public"."support_case_notes" to "authenticated";

grant update on table "public"."support_case_notes" to "authenticated";

grant delete on table "public"."support_case_notes" to "service_role";

grant insert on table "public"."support_case_notes" to "service_role";

grant references on table "public"."support_case_notes" to "service_role";

grant select on table "public"."support_case_notes" to "service_role";

grant trigger on table "public"."support_case_notes" to "service_role";

grant truncate on table "public"."support_case_notes" to "service_role";

grant update on table "public"."support_case_notes" to "service_role";

grant delete on table "public"."support_cases" to "anon";

grant insert on table "public"."support_cases" to "anon";

grant references on table "public"."support_cases" to "anon";

grant select on table "public"."support_cases" to "anon";

grant trigger on table "public"."support_cases" to "anon";

grant truncate on table "public"."support_cases" to "anon";

grant update on table "public"."support_cases" to "anon";

grant delete on table "public"."support_cases" to "authenticated";

grant insert on table "public"."support_cases" to "authenticated";

grant references on table "public"."support_cases" to "authenticated";

grant select on table "public"."support_cases" to "authenticated";

grant trigger on table "public"."support_cases" to "authenticated";

grant truncate on table "public"."support_cases" to "authenticated";

grant update on table "public"."support_cases" to "authenticated";

grant delete on table "public"."support_cases" to "service_role";

grant insert on table "public"."support_cases" to "service_role";

grant references on table "public"."support_cases" to "service_role";

grant select on table "public"."support_cases" to "service_role";

grant trigger on table "public"."support_cases" to "service_role";

grant truncate on table "public"."support_cases" to "service_role";

grant update on table "public"."support_cases" to "service_role";

grant delete on table "public"."users" to "anon";

grant insert on table "public"."users" to "anon";

grant references on table "public"."users" to "anon";

grant select on table "public"."users" to "anon";

grant trigger on table "public"."users" to "anon";

grant truncate on table "public"."users" to "anon";

grant update on table "public"."users" to "anon";

grant delete on table "public"."users" to "authenticated";

grant insert on table "public"."users" to "authenticated";

grant references on table "public"."users" to "authenticated";

grant select on table "public"."users" to "authenticated";

grant trigger on table "public"."users" to "authenticated";

grant truncate on table "public"."users" to "authenticated";

grant update on table "public"."users" to "authenticated";

grant delete on table "public"."users" to "service_role";

grant insert on table "public"."users" to "service_role";

grant references on table "public"."users" to "service_role";

grant select on table "public"."users" to "service_role";

grant trigger on table "public"."users" to "service_role";

grant truncate on table "public"."users" to "service_role";

grant update on table "public"."users" to "service_role";

grant delete on table "public"."wizard_cases" to "anon";

grant insert on table "public"."wizard_cases" to "anon";

grant references on table "public"."wizard_cases" to "anon";

grant select on table "public"."wizard_cases" to "anon";

grant trigger on table "public"."wizard_cases" to "anon";

grant truncate on table "public"."wizard_cases" to "anon";

grant update on table "public"."wizard_cases" to "anon";

grant delete on table "public"."wizard_cases" to "authenticated";

grant insert on table "public"."wizard_cases" to "authenticated";

grant references on table "public"."wizard_cases" to "authenticated";

grant select on table "public"."wizard_cases" to "authenticated";

grant trigger on table "public"."wizard_cases" to "authenticated";

grant truncate on table "public"."wizard_cases" to "authenticated";

grant update on table "public"."wizard_cases" to "authenticated";

grant delete on table "public"."wizard_cases" to "service_role";

grant insert on table "public"."wizard_cases" to "service_role";

grant references on table "public"."wizard_cases" to "service_role";

grant select on table "public"."wizard_cases" to "service_role";

grant trigger on table "public"."wizard_cases" to "service_role";

grant truncate on table "public"."wizard_cases" to "service_role";

grant update on table "public"."wizard_cases" to "service_role";


