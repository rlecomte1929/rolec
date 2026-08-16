/**
 * Counsel attestation — admin API + the tokenized public reviewer API.
 * Pairs with backend/app/routers/attestation.py.
 *
 * The public calls deliberately DO NOT go through `./client`. That wrapper attaches the
 * ReloPass session token, and the whole point of the reviewer flow is that it works for
 * someone with no account: an external lawyer opening a link. Sending an Authorization
 * header would at best be ignored and at worst leak whichever session happened to be in
 * localStorage on that machine into a request made on behalf of a third party.
 */
import axios from 'axios';
import { apiGet, apiPost } from './client';

const API = import.meta.env.VITE_API_URL || 'https://api.relopass.com';

export type AttestationDecision = 'pending' | 'approved' | 'amended' | 'rejected';

export interface AttestationChecklistItem {
  id: string;
  title: string;
  claim: string | null;
  source_url: string | null;
  evidence: string | null;
  pillar: string | null;
  validity: string | null;
  confidence: string | null;
  decision: AttestationDecision;
  reviewer_comment: string | null;
  proposed_amendment: string | null;
}

/** Exactly what the tokenized reviewer receives. No case, employee or company data. */
export interface AttestationPublicView {
  corridor_label: string;
  purpose: string;
  scope: string;
  status: string;
  title: string | null;
  disclaimer_version: string;
  disclaimer_text: string;
  content_hash: string;
  expires_at: string | null;
  items: AttestationChecklistItem[];
  signed_at: string | null;
}

export interface AttestationSignature {
  id: string;
  signer_name: string;
  signer_org: string | null;
  signer_credential: string | null;
  signature_method: string;
  signed_content_hash: string;
  disclaimer_version: string;
  signed_at: string;
  supersedes_signature_id: string | null;
}

export interface AttestationAdmin {
  id: string;
  country_code: string;
  purpose: string;
  scope: string;
  title: string | null;
  status: string;
  requested_by: string;
  reviewer_org: string | null;
  reviewer_name: string | null;
  reviewer_email: string | null;
  reviewer_credential: string | null;
  content_snapshot_hash: string;
  disclaimer_version: string | null;
  token_expires_at: string | null;
  sent_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  item_count: number;
  items: AttestationChecklistItem[];
  signature: AttestationSignature | null;
}

/** The only response that ever carries the raw token. Show it once; it is unrecoverable. */
export interface AttestationCreated {
  request: AttestationAdmin;
  review_token: string;
  review_url: string;
  token_expires_at: string | null;
  warning: string;
}

export interface AttestationPromoteResult {
  request_id: string;
  promoted_item_ids: string[];
  promoted_count: number;
  attested_by: string | null;
  skipped_not_approved: string[];
}

// ── admin (authenticated) ────────────────────────────────────────────────────

export const listAttestations = (): Promise<AttestationAdmin[]> => apiGet('/api/admin/attestations');

export const getAttestation = (id: string): Promise<AttestationAdmin> =>
  apiGet(`/api/admin/attestations/${encodeURIComponent(id)}`);

export const createAttestation = (body: {
  country_code: string;
  purpose?: string;
  title?: string;
  reviewer_org?: string;
  reviewer_name?: string;
  reviewer_email?: string;
  reviewer_credential?: string;
  requirement_item_ids?: string[];
  ttl_days?: number;
}): Promise<AttestationCreated> => apiPost('/api/admin/attestations', body);

export const sendAttestation = (id: string): Promise<AttestationAdmin> =>
  apiPost(`/api/admin/attestations/${encodeURIComponent(id)}/send`, {});

export const promoteAttestation = (id: string): Promise<AttestationPromoteResult> =>
  apiPost(`/api/admin/attestations/${encodeURIComponent(id)}/promote`, {});

// ── public (token-scoped, deliberately unauthenticated) ──────────────────────

export const fetchAttestationByToken = async (token: string): Promise<AttestationPublicView> => {
  const { data } = await axios.get<AttestationPublicView>(
    `${API}/api/public/attestations/${encodeURIComponent(token)}`,
  );
  return data;
};

export const decideAttestationItem = async (
  token: string,
  itemId: string,
  body: { decision: 'approved' | 'amended' | 'rejected'; reviewer_comment?: string; proposed_amendment?: string },
): Promise<AttestationPublicView> => {
  const { data } = await axios.post<AttestationPublicView>(
    `${API}/api/public/attestations/${encodeURIComponent(token)}/items/${encodeURIComponent(itemId)}`,
    body,
  );
  return data;
};

export const signAttestation = async (
  token: string,
  body: {
    signer_name: string;
    signer_email: string;
    signer_org?: string;
    signer_credential?: string;
    signature_method?: string;
    /** Echoed back from the view. The server rejects a mismatch with 409. */
    content_hash: string;
    agreed_to_disclaimer: boolean;
  },
): Promise<AttestationPublicView> => {
  const { data } = await axios.post<AttestationPublicView>(
    `${API}/api/public/attestations/${encodeURIComponent(token)}/sign`,
    body,
  );
  return data;
};
