/**
 * crisis-templates.ts — HUMAN-7E
 * ─────────────────────────────────────────────────────────────────────────────
 * Brand-voice-compliant crisis response templates for major incident scenarios.
 * Used by the support triage agent (SUPPORT-4C / support-router.ts) and the
 * escalation playbook (HUMAN-7D) when a ticket is classified as a crisis event.
 *
 * Scenarios:
 *   supplier_no_show   — supplier fails to appear at scheduled appointment
 *   platform_outage    — ReloPass platform is unavailable or severely degraded
 *   data_breach        — potential or confirmed data / privacy incident
 *   payment_failure    — payment to supplier or employee fails
 *   legal_complaint    — formal legal complaint received
 *
 * ReloPass brand voice rules (mirrors relopass-brand-voice skill):
 *   ✓ Professional but warm — we take incidents seriously without being cold
 *   ✓ First-person plural ("we", "our team") — never "I" or "the system"
 *   ✓ No jargon ("ping", "syncing", "looping in", "touch base")
 *   ✓ Clear next steps with specific timeframes
 *   ✓ Escalation path explicit in internalAlert
 *   ✓ Signed "The ReloPass Team"
 *   ✓ {{placeholder}} syntax for runtime substitution
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type CrisisScenario =
  | "supplier_no_show"
  | "platform_outage"
  | "data_breach"
  | "payment_failure"
  | "legal_complaint";

export interface CrisisTemplate {
  /** Discriminant — matches the CrisisScenario union */
  scenario: CrisisScenario;
  /** How urgent: 'high' (serious but manageable) or 'critical' (all-hands) */
  severity: "high" | "critical";
  /** Subject line for the customer-facing email */
  customerSubject: string;
  /**
   * Body for the customer-facing email.
   * Runtime substitution placeholders use {{snake_case}} syntax.
   * Common placeholders: {{employee_name}}, {{company_name}},
   * {{incident_date}}, {{reference_number}}, {{next_step}}.
   */
  customerBody: string;
  /** Short alert message sent to Romain / on-call Slack channel */
  internalAlert: string;
  /** Whether a human must review and approve before the email is sent */
  escalationRequired: boolean;
  /** Target response SLA in minutes (time-to-first-contact with affected party) */
  slaMinutes: number;
}

// ─── Templates ────────────────────────────────────────────────────────────────

export const CRISIS_TEMPLATES: Record<CrisisScenario, CrisisTemplate> = {
  // ── 1. Supplier No-Show ────────────────────────────────────────────────────
  supplier_no_show: {
    scenario: "supplier_no_show",
    severity: "high",
    customerSubject: "Urgent: we are arranging an alternative for your appointment today",
    customerBody: `Hi {{employee_name}},

We are aware that your scheduled appointment with {{supplier_name}} on {{incident_date}} did not go ahead as planned. We sincerely apologise for the disruption this has caused to your relocation.

Our team is actively working to arrange an alternative provider. We expect to have a confirmed replacement within {{replacement_sla_hours}} hours, and we will contact you as soon as arrangements are confirmed.

In the meantime, please do not re-schedule directly with {{supplier_name}} — we will manage this on your behalf.

If you have any urgent concerns, please reply to this email and a member of our team will respond promptly.

We are sorry for the inconvenience and will do everything we can to keep your relocation on track.

Best regards,
The ReloPass Team
support@relopass.com`,
    internalAlert:
      "🚨 SUPPLIER NO-SHOW — {{supplier_name}} did not attend appointment for {{employee_name}} ({{company_name}}) on {{incident_date}}. " +
      "ACTION: Find replacement within 2 hours. Notify Romain immediately. Reference: {{reference_number}}.",
    escalationRequired: true,
    slaMinutes: 15,
  },

  // ── 2. Platform Outage ─────────────────────────────────────────────────────
  platform_outage: {
    scenario: "platform_outage",
    severity: "critical",
    customerSubject: "ReloPass service interruption — we are working to restore access",
    customerBody: `Hi {{employee_name}},

We are writing to let you know that ReloPass is currently experiencing a service interruption that may be affecting your access to the platform. We apologise for any inconvenience this causes.

Our engineering team identified the issue at {{incident_time}} and is working to restore full service as quickly as possible. We expect the platform to be back online by {{estimated_restoration_time}}.

You do not need to take any action. Any data you have already submitted is safe and will not be affected.

We will send a follow-up email once service has been fully restored. For real-time updates, please visit our status page at status.relopass.com.

Thank you for your patience.

Best regards,
The ReloPass Team
support@relopass.com`,
    internalAlert:
      "🔴 PLATFORM OUTAGE — Service unavailable since {{incident_time}}. " +
      "ACTION: Tech Lead to investigate immediately. Update status.relopass.com within 10 minutes. RCA due within 24h. " +
      "Notify all affected companies. Reference: {{reference_number}}.",
    escalationRequired: true,
    slaMinutes: 10,
  },

  // ── 3. Data Breach ─────────────────────────────────────────────────────────
  data_breach: {
    scenario: "data_breach",
    severity: "critical",
    customerSubject: "Important notice regarding your data security",
    customerBody: `Hi {{employee_name}},

We are writing to inform you of a potential security incident that may have affected data associated with your account at {{company_name}}.

We detected an anomaly on {{incident_date}} and immediately took steps to contain the situation. Our security team is conducting a full investigation to determine the scope and nature of the incident.

At this stage, we believe the following information may have been affected: {{affected_data_types}}. We have no evidence that any information has been misused.

We take the security and privacy of your data extremely seriously. Out of an abundance of caution, we recommend that you:
1. Change your ReloPass password at your earliest convenience.
2. Be vigilant of any unsolicited communications that reference your relocation.
3. Contact us immediately if you notice anything suspicious.

We will provide a further update within 72 hours as our investigation progresses. If you have any questions in the meantime, please contact our security team at security@relopass.com.

We sincerely apologise for any concern this may cause.

Best regards,
The ReloPass Team
security@relopass.com`,
    internalAlert:
      "🔴 DATA BREACH ALERT — Potential incident detected on {{incident_date}}. " +
      "ACTION: CEO + Legal to be notified immediately. GDPR 72-hour regulatory notification clock starts now. " +
      "Security team to begin forensic investigation. Do NOT send customer email without Legal sign-off. " +
      "Reference: {{reference_number}}.",
    escalationRequired: true,
    slaMinutes: 30,
  },

  // ── 4. Payment Failure ─────────────────────────────────────────────────────
  payment_failure: {
    scenario: "payment_failure",
    severity: "high",
    customerSubject: "Action required: payment issue with your relocation services",
    customerBody: `Hi {{employee_name}},

We are writing to let you know that a payment related to your relocation with {{company_name}} was not processed successfully on {{incident_date}}.

The payment of {{amount}} {{currency}} to {{supplier_name}} for {{service_description}} was declined. This may affect the scheduling or delivery of the associated service.

Our finance team has been notified and is working to resolve this as a priority. We expect to confirm the status of the payment within {{resolution_sla_hours}} hours.

You do not need to contact {{supplier_name}} directly — we are handling this on your behalf.

If you have any questions or concerns, please reply to this email and a member of our team will be in touch promptly.

We apologise for any disruption this may cause to your relocation.

Best regards,
The ReloPass Team
support@relopass.com`,
    internalAlert:
      "⚠️ PAYMENT FAILURE — {{amount}} {{currency}} to {{supplier_name}} for {{employee_name}} ({{company_name}}) failed on {{incident_date}}. " +
      "ACTION: Finance to investigate and retry within 24h. Contact supplier to prevent service suspension. " +
      "Reference: {{reference_number}}.",
    escalationRequired: true,
    slaMinutes: 60,
  },

  // ── 5. Legal Complaint ─────────────────────────────────────────────────────
  legal_complaint: {
    scenario: "legal_complaint",
    severity: "critical",
    customerSubject: "We have received your complaint and are reviewing it",
    customerBody: `Dear {{complainant_name}},

Thank you for bringing your concern to our attention. We have received your formal complaint dated {{complaint_date}} regarding {{complaint_subject}}.

We take all complaints seriously and are committed to addressing your concerns thoroughly and fairly. Our team will review the details of your complaint and respond with a full written response within {{response_sla_days}} business days.

If you need to provide any additional information or documentation in support of your complaint, please reply to this email.

Your complaint reference number is: {{reference_number}}. Please use this reference in any future correspondence.

We are sorry to hear that your experience with ReloPass has not met your expectations. We value the opportunity to address this directly.

Best regards,
The ReloPass Team
legal@relopass.com`,
    internalAlert:
      "⚖️ LEGAL COMPLAINT RECEIVED — Formal complaint from {{complainant_name}} regarding {{complaint_subject}}, dated {{complaint_date}}. " +
      "ACTION: CEO + external counsel to be notified within 1 hour. Do NOT send customer email without Legal review. " +
      "Acknowledge receipt within 24h. Reference: {{reference_number}}.",
    escalationRequired: true,
    slaMinutes: 60,
  },
};

// ─── Helper ───────────────────────────────────────────────────────────────────

/**
 * Retrieve the CrisisTemplate for a given scenario.
 *
 * Throws a descriptive error for unknown scenarios rather than silently
 * returning undefined — callers must handle every scenario explicitly.
 *
 * @example
 * const template = getCrisisTemplate("platform_outage");
 * console.log(template.slaMinutes); // 10
 */
export function getCrisisTemplate(scenario: CrisisScenario): CrisisTemplate {
  const template = CRISIS_TEMPLATES[scenario];
  if (!template) {
    throw new Error(
      `getCrisisTemplate: unknown scenario "${scenario}". ` +
        `Valid scenarios are: ${Object.keys(CRISIS_TEMPLATES).join(", ")}.`
    );
  }
  return template;
}

// ─── Placeholder substitution utility ────────────────────────────────────────

export type PlaceholderValues = Record<string, string>;

/**
 * Substitute {{placeholder}} tokens in a template string with runtime values.
 * Unmatched placeholders are left as-is so missing values are visible.
 *
 * @example
 * const body = substitutePlaceholders(template.customerBody, {
 *   employee_name: "Marc Bouchard",
 *   company_name: "Aurora Energy",
 * });
 */
export function substitutePlaceholders(
  text: string,
  values: PlaceholderValues
): string {
  return text.replace(/\{\{(\w+)\}\}/g, (_match, key) => {
    return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : `{{${key}}}`;
  });
}

// ─── Scenario metadata ────────────────────────────────────────────────────────

export const CRISIS_SCENARIO_LABELS: Record<CrisisScenario, string> = {
  supplier_no_show: "Supplier No-Show",
  platform_outage: "Platform Outage",
  data_breach: "Data / Privacy Breach",
  payment_failure: "Payment Failure",
  legal_complaint: "Legal Complaint",
};
