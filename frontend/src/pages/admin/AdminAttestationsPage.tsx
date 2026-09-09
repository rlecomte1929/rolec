/**
 * Admin → Attestations. Request a corridor legal review, track it, promote the result.
 *
 * The two-key rule from backend/app/routers/attestation.py is visible in this UI on
 * purpose: "Promote to attested" only appears once a request is `signed`, and it is a
 * separate, deliberate click. A reviewer signing does not change what ReloPass serves —
 * a human here decides that, after seeing who signed and what they approved.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  AttestationAdmin,
  AttestationCreated,
  createAttestation,
  listAttestations,
  promoteAttestation,
  sendAttestation,
} from '../../api/attestation';

export const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  sent: 'bg-blue-100 text-blue-800',
  in_review: 'bg-navy-50 text-navy-800',
  changes_requested: 'bg-amber-100 text-amber-800',
  signed: 'bg-emerald-100 text-emerald-800',
  revoked: 'bg-rose-100 text-rose-800',
};

export const AdminAttestationsPage: React.FC = () => {
  const [rows, setRows] = useState<AttestationAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<AttestationCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const [form, setForm] = useState({
    country_code: '', purpose: 'employment',
    reviewer_org: '', reviewer_name: '', reviewer_email: '', reviewer_credential: '',
  });

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listAttestations());
      setError(null);
    } catch {
      setError('Could not load attestations.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const onCreate = async () => {
    if (!form.country_code.trim()) return;
    setBusy(true);
    try {
      setCreated(await createAttestation({ ...form, country_code: form.country_code.trim() }));
      setCopied(false);
      setError(null);
      await refresh();
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Could not create the attestation request.');
    } finally {
      setBusy(false);
    }
  };

  const onSend = async (id: string) => {
    setBusy(true);
    try { await sendAttestation(id); await refresh(); }
    catch { setError('Could not send that request.'); }
    finally { setBusy(false); }
  };

  const onPromote = async (id: string) => {
    setBusy(true);
    try {
      const result = await promoteAttestation(id);
      setError(null);
      window.alert(
        `Promoted ${result.promoted_count} requirement(s) to attested by ${result.attested_by || 'counsel'}.` +
        (result.skipped_not_approved.length
          ? `\n\n${result.skipped_not_approved.length} item(s) were skipped because counsel did not approve them.`
          : ''),
      );
      await refresh();
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Could not promote that attestation.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-semibold text-navy-900">Counsel attestations</h1>
      <p className="mt-1 text-sm text-slate-600">
        Ask an external legal firm to review a corridor&apos;s legal requirements and sign off on them.
      </p>

      {error && (
        <div role="alert" className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {/* One-time link. Once this panel is dismissed the raw token is gone for good — only
          its SHA-256 was stored — so make that unmissable rather than a subtle hint. */}
      {created && (
        <div className="mt-5 rounded-lg border-2 border-amber-300 bg-amber-50 p-4">
          <h2 className="font-semibold text-amber-900">Reviewer link — shown once</h2>
          <p className="mt-1 text-sm text-amber-900">{created.warning}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded border border-amber-200 bg-white p-2 text-xs">
              {created.review_url}
            </code>
            <button
              type="button"
              onClick={() => { void navigator.clipboard?.writeText(created.review_url); setCopied(true); }}
              className="rounded bg-navy-900 px-3 py-2 text-sm font-medium text-white"
            >
              {copied ? 'Copied' : 'Copy link'}
            </button>
            <button
              type="button" onClick={() => setCreated(null)}
              className="rounded border border-amber-300 px-3 py-2 text-sm text-amber-900"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <section className="mt-6 rounded-lg border border-slate-200 p-4">
        <h2 className="font-semibold text-navy-900">Request an attestation</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <span className="font-medium text-slate-700">Corridor key</span>
            <input
              value={form.country_code}
              onChange={(e) => setForm({ ...form, country_code: e.target.value })}
              placeholder="NORWAY"
              className="mt-1 w-full rounded border border-slate-300 p-2"
            />
          </label>
          <label className="text-sm">
            <span className="font-medium text-slate-700">Purpose</span>
            <input value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}
              className="mt-1 w-full rounded border border-slate-300 p-2" />
          </label>
          <label className="text-sm">
            <span className="font-medium text-slate-700">Firm</span>
            <input value={form.reviewer_org} onChange={(e) => setForm({ ...form, reviewer_org: e.target.value })}
              className="mt-1 w-full rounded border border-slate-300 p-2" />
          </label>
          <label className="text-sm">
            <span className="font-medium text-slate-700">Reviewer name</span>
            <input value={form.reviewer_name} onChange={(e) => setForm({ ...form, reviewer_name: e.target.value })}
              className="mt-1 w-full rounded border border-slate-300 p-2" />
          </label>
          <label className="text-sm">
            <span className="font-medium text-slate-700">Reviewer email</span>
            <input value={form.reviewer_email} onChange={(e) => setForm({ ...form, reviewer_email: e.target.value })}
              type="email" className="mt-1 w-full rounded border border-slate-300 p-2" />
          </label>
          <label className="text-sm">
            <span className="font-medium text-slate-700">Bar / registration no.</span>
            <input value={form.reviewer_credential} onChange={(e) => setForm({ ...form, reviewer_credential: e.target.value })}
              className="mt-1 w-full rounded border border-slate-300 p-2" />
          </label>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Scope defaults to the corridor&apos;s approved legal requirements. Operational items
          (housing, lead time) are excluded.
        </p>
        <button
          type="button" disabled={busy || !form.country_code.trim()} onClick={onCreate}
          className="mt-3 rounded bg-navy-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Create request
        </button>
      </section>

      <section className="mt-8">
        <h2 className="font-semibold text-navy-900">Requests</h2>
        {loading ? (
          <p className="mt-3 text-sm text-slate-600">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">No attestation requests yet.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-4">Corridor</th>
                  <th className="py-2 pr-4">Reviewer</th>
                  <th className="py-2 pr-4">Items</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Signed</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium text-navy-900">{r.country_code}</td>
                    <td className="py-2 pr-4">{r.reviewer_org || r.reviewer_name || '—'}</td>
                    <td className="py-2 pr-4">{r.item_count}</td>
                    <td className="py-2 pr-4">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[r.status] || STATUS_STYLES.draft}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      {r.signature ? new Date(r.signature.signed_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2">
                      {r.status === 'draft' && (
                        <button type="button" disabled={busy} onClick={() => onSend(r.id)}
                          className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-40">
                          Mark sent
                        </button>
                      )}
                      {r.status === 'signed' && (
                        <button type="button" disabled={busy} onClick={() => onPromote(r.id)}
                          className="rounded bg-emerald-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-40">
                          Promote to attested
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default AdminAttestationsPage;
