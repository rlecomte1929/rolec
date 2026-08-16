/**
 * `/attest/:token` — the external counsel's review surface. PUBLIC by design: no account,
 * no login, the token in the URL is the only credential.
 *
 * Deliberately no app chrome — no sidebar, no product nav, no "upgrade" anything. The
 * reader is a lawyer at another firm doing a professional review, not a ReloPass user, and
 * anything that reads as marketing undermines the seriousness of what they are signing.
 *
 * Nothing here is authenticated, so nothing here may show anything personal. The payload
 * the backend serves is a whitelist of corridor-legal fields (see AttestationPublicView);
 * this page renders that and nothing else. Do not add a lookup that joins a case.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  AttestationChecklistItem,
  AttestationPublicView,
  decideAttestationItem,
  fetchAttestationByToken,
  signAttestation,
} from '../../api/attestation';

const DECISION_STYLES: Record<string, string> = {
  approved: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  amended: 'bg-amber-50 text-amber-800 border-amber-200',
  rejected: 'bg-rose-50 text-rose-800 border-rose-200',
  pending: 'bg-slate-50 text-slate-600 border-slate-200',
};

const ItemCard: React.FC<{
  item: AttestationChecklistItem;
  disabled: boolean;
  onDecide: (id: string, decision: 'approved' | 'amended' | 'rejected', comment?: string, amendment?: string) => void;
}> = ({ item, disabled, onDecide }) => {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState(item.reviewer_comment || '');
  const [amendment, setAmendment] = useState(item.proposed_amendment || '');

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-navy-900">{item.title}</h3>
        <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${DECISION_STYLES[item.decision] || DECISION_STYLES.pending}`}>
          {item.decision}
        </span>
      </div>

      {item.claim && <p className="mt-2 text-sm leading-relaxed text-slate-700">{item.claim}</p>}

      <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs text-slate-500 sm:grid-cols-2">
        {item.pillar && (
          <div><dt className="inline font-medium">Category: </dt><dd className="inline">{item.pillar}</dd></div>
        )}
        {item.validity && (
          <div><dt className="inline font-medium">Timing: </dt><dd className="inline">{item.validity}</dd></div>
        )}
        {item.confidence && (
          <div><dt className="inline font-medium">Our confidence: </dt><dd className="inline">{item.confidence}</dd></div>
        )}
        {item.source_url && (
          <div className="truncate">
            <dt className="inline font-medium">Source: </dt>
            <dd className="inline">
              <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="text-accent-700 underline">
                {item.source_url}
              </a>
            </dd>
          </div>
        )}
      </dl>

      {item.reviewer_comment && (
        <p className="mt-3 rounded bg-slate-50 p-2 text-xs text-slate-600">
          <span className="font-medium">Your note: </span>{item.reviewer_comment}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button" disabled={disabled}
          onClick={() => onDecide(item.id, 'approved')}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button" disabled={disabled}
          onClick={() => setOpen((v) => !v)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-50"
        >
          {open ? 'Cancel' : 'Comment / request change'}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-2">
          <textarea
            value={comment} onChange={(e) => setComment(e.target.value)}
            placeholder="What is wrong, or what needs clarifying?"
            className="w-full rounded border border-slate-300 p-2 text-sm" rows={2}
            aria-label={`Comment on ${item.title}`}
          />
          <textarea
            value={amendment} onChange={(e) => setAmendment(e.target.value)}
            placeholder="Optional: the wording you would use instead"
            className="w-full rounded border border-slate-300 p-2 text-sm" rows={2}
            aria-label={`Proposed amendment for ${item.title}`}
          />
          <div className="flex gap-2">
            <button
              type="button" disabled={disabled || !comment.trim()}
              onClick={() => { onDecide(item.id, 'amended', comment, amendment); setOpen(false); }}
              className="rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Submit amendment
            </button>
            <button
              type="button" disabled={disabled || !comment.trim()}
              onClick={() => { onDecide(item.id, 'rejected', comment); setOpen(false); }}
              className="rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Reject this item
            </button>
          </div>
        </div>
      )}
    </li>
  );
};

export const AttestationReviewPage: React.FC = () => {
  const { token = '' } = useParams<{ token: string }>();
  const [view, setView] = useState<AttestationPublicView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [org, setOrg] = useState('');
  const [credential, setCredential] = useState('');
  const [agreed, setAgreed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setView(await fetchAttestationByToken(token));
      setError(null);
    } catch {
      // The backend returns an identical 404 for unknown, expired and not-yet-sent links
      // so the page cannot be used to probe which tokens exist. Mirror that here: one
      // message, no detail about which case we are in.
      setError('This attestation link is not valid, or it has expired.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const signed = !!view?.signed_at;
  const allDecided = useMemo(
    () => !!view?.items.length && view.items.every((i) => i.decision !== 'pending'),
    [view],
  );

  const onDecide = async (
    id: string, decision: 'approved' | 'amended' | 'rejected', comment?: string, amendment?: string,
  ) => {
    setBusy(true);
    try {
      setView(await decideAttestationItem(token, id, {
        decision, reviewer_comment: comment, proposed_amendment: amendment,
      }));
      setError(null);
    } catch {
      setError('That decision could not be saved. Reload the page and try again.');
    } finally {
      setBusy(false);
    }
  };

  const onSign = async () => {
    if (!view) return;
    setBusy(true);
    try {
      setView(await signAttestation(token, {
        signer_name: name.trim(),
        signer_email: email.trim(),
        signer_org: org.trim() || undefined,
        signer_credential: credential.trim() || undefined,
        signature_method: 'typed_name',
        // Echoed from the view the reviewer actually read. A 409 means the checklist moved
        // underneath them, and they must re-read before signing — never sign silently.
        content_hash: view.content_hash,
        agreed_to_disclaimer: agreed,
      }));
      setError(null);
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      setError(
        status === 409
          ? 'The checklist changed since you opened this page. Reload and review the current version before signing.'
          : 'The attestation could not be recorded. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <main className="mx-auto max-w-3xl p-8 text-slate-600">Loading the attestation…</main>;
  }

  if (error && !view) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <h1 className="text-xl font-semibold text-navy-900">Attestation unavailable</h1>
        <p className="mt-2 text-slate-600">{error}</p>
        <p className="mt-4 text-sm text-slate-500">
          If you believe this is a mistake, contact the person at ReloPass who sent you the link.
        </p>
      </main>
    );
  }

  if (!view) return null;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <header className="border-b border-slate-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent-700">
          Legal compliance attestation
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-navy-900">
          {view.title || `${view.corridor_label} — legal compliance attestation`}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Corridor destination: <span className="font-medium">{view.corridor_label}</span> · Purpose: {view.purpose} · Scope: {view.scope}
        </p>
        {view.expires_at && !signed && (
          <p className="mt-1 text-xs text-slate-500">
            This link expires on {new Date(view.expires_at).toLocaleDateString()}.
          </p>
        )}
      </header>

      {signed && (
        <div role="status" className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="font-medium text-emerald-900">Attestation recorded</p>
          <p className="mt-1 text-sm text-emerald-800">
            Signed on {new Date(view.signed_at as string).toLocaleString()}. This record is
            immutable — ReloPass cannot alter it. Nothing further is required from you.
          </p>
        </div>
      )}

      {error && view && (
        <div role="alert" className="mt-5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          {error}
        </div>
      )}

      <section className="mt-6">
        <h2 className="text-lg font-semibold text-navy-900">Requirements for review</h2>
        <p className="mt-1 text-sm text-slate-600">
          Each item below is a legal requirement we present to people relocating on this corridor.
          Approve the ones that are correct; comment or request a change on the ones that are not.
        </p>
        <ul className="mt-4 space-y-4">
          {view.items.map((item) => (
            <ItemCard key={item.id} item={item} disabled={busy || signed} onDecide={onDecide} />
          ))}
        </ul>
      </section>

      {!signed && (
        <section className="mt-8 rounded-lg border border-slate-300 bg-slate-50 p-5">
          <h2 className="text-lg font-semibold text-navy-900">Sign &amp; attest</h2>

          <p className="mt-3 whitespace-pre-line rounded border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-700">
            {view.disclaimer_text}
          </p>
          <p className="mt-1 text-xs text-slate-500">Disclaimer version {view.disclaimer_version}</p>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="font-medium text-slate-700">Full name</span>
              <input value={name} onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 p-2" autoComplete="name" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Email</span>
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email"
                className="mt-1 w-full rounded border border-slate-300 p-2" autoComplete="email" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Firm / organisation</span>
              <input value={org} onChange={(e) => setOrg(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 p-2" autoComplete="organization" />
            </label>
            <label className="text-sm">
              <span className="font-medium text-slate-700">Bar / registration number</span>
              <input value={credential} onChange={(e) => setCredential(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 p-2" />
            </label>
          </div>

          <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="mt-1" />
            <span>I attest to the above in my professional capacity.</span>
          </label>

          {!allDecided && (
            <p className="mt-3 text-sm text-amber-700">
              Every requirement must be approved, amended or rejected before you can sign.
            </p>
          )}

          <button
            type="button"
            disabled={busy || !allDecided || !agreed || !name.trim() || !email.trim()}
            onClick={onSign}
            className="mt-4 rounded-md bg-navy-900 px-5 py-2.5 font-medium text-white disabled:opacity-40"
          >
            Sign &amp; attest
          </button>
        </section>
      )}

      <footer className="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
        This page shows only the general legal requirements of a relocation corridor. It contains
        no personal data about any individual relocating person.
      </footer>
    </main>
  );
};

export default AttestationReviewPage;
