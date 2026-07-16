/**
 * LinkedIn Outreach CRM API wrappers.
 *
 * The outreach feature used to query Supabase tables directly from the browser,
 * which required a live Supabase `authenticated` session admins don't reliably
 * have (they hold a ReloPass session token) — so the query ran as `anon` and
 * Postgres denied it. These wrappers go through the admin-gated FastAPI router
 * (`/api/admin/outreach/*`, service_role) via the shared client, which carries
 * the ReloPass bearer token — no Supabase session required.
 */
import { apiGet, apiPost, apiPatch, apiDelete } from './client';
import type {
  LinkedInProspect, ProspectInsert,
  MessageTemplate, TemplateInsert,
  ProspectReply, ReplyInsert,
  OutreachMessage, MessageInsert,
} from '../types/outreach';

const BASE = '/api/admin/outreach';
const q = (v: string) => encodeURIComponent(v);

// ── Prospects ────────────────────────────────────────────────────────────────
export const listProspects = () => apiGet<LinkedInProspect[]>(`${BASE}/prospects`);
export const createProspect = (data: ProspectInsert) =>
  apiPost<LinkedInProspect>(`${BASE}/prospects`, data);
export const updateProspectApi = (id: string, patch: Partial<LinkedInProspect>) =>
  apiPatch<LinkedInProspect>(`${BASE}/prospects/${q(id)}`, patch);
export const deleteProspectApi = (id: string) =>
  apiDelete<{ deleted: string }>(`${BASE}/prospects/${q(id)}`);

// ── Templates ────────────────────────────────────────────────────────────────
export const listTemplates = () => apiGet<MessageTemplate[]>(`${BASE}/templates`);
export const createTemplateApi = (data: TemplateInsert) =>
  apiPost<MessageTemplate>(`${BASE}/templates`, data);
export const updateTemplateApi = (id: string, patch: Partial<MessageTemplate>) =>
  apiPatch<MessageTemplate>(`${BASE}/templates/${q(id)}`, patch);
export const deleteTemplateApi = (id: string) =>
  apiDelete<{ deleted: string }>(`${BASE}/templates/${q(id)}`);

// ── Replies ──────────────────────────────────────────────────────────────────
export const listReplies = (prospectId: string) =>
  apiGet<ProspectReply[]>(`${BASE}/replies?prospect_id=${q(prospectId)}`);
export const createReply = (data: ReplyInsert) =>
  apiPost<ProspectReply>(`${BASE}/replies`, data);

// ── Messages ─────────────────────────────────────────────────────────────────
export const listMessages = (prospectId: string, status?: string) =>
  apiGet<OutreachMessage[]>(
    `${BASE}/messages?prospect_id=${q(prospectId)}${status ? `&status=${q(status)}` : ''}`,
  );
export const createMessageApi = (data: MessageInsert) =>
  apiPost<OutreachMessage>(`${BASE}/messages`, data);
export const updateMessageApi = (id: string, patch: Partial<OutreachMessage>) =>
  apiPatch<OutreachMessage>(`${BASE}/messages/${q(id)}`, patch);
