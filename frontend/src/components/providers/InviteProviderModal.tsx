/**
 * InviteProviderModal — 2-step flow:
 *   Step 1: pick an existing provider OR create a new one.
 *   Step 2: confirm email + send invite (POST /api/hr/providers/invite).
 *
 * The modal calls onInviteSent when the invite is confirmed so the parent
 * can re-fetch the provider list.
 */
import React, { useEffect, useState } from 'react';
import {
  listOrgProviders,
  createProvider,
  inviteProvider,
} from '../../api/providers';
import type { ProviderItem } from '../../api/providers';
import { Input, Button } from '../antigravity';

type Step = 'pick' | 'confirm';

interface InviteProviderModalProps {
  caseId: string;
  /** Pre-selected provider — skips step 1. */
  preselectedProvider?: ProviderItem;
  onInviteSent: () => void;
  onClose: () => void;
}

export const InviteProviderModal: React.FC<InviteProviderModalProps> = ({
  caseId,
  preselectedProvider,
  onInviteSent,
  onClose,
}) => {
  // ── Step 1 state ───────────────────────────────────────────────────────────
  const [step, setStep] = useState<Step>(preselectedProvider ? 'confirm' : 'pick');
  const [orgProviders, setOrgProviders] = useState<ProviderItem[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [search, setSearch] = useState('');
  const [mode, setMode] = useState<'existing' | 'new'>('existing');

  // new provider form
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newServiceType, setNewServiceType] = useState('');

  // ── Step 2 state ───────────────────────────────────────────────────────────
  const [selected, setSelected] = useState<ProviderItem | null>(preselectedProvider ?? null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteDevLink, setInviteDevLink] = useState<string | null>(null);

  // ── Shared state ───────────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Load org providers on mount (step 1)
  useEffect(() => {
    if (step !== 'pick') return;
    setLoadingProviders(true);
    listOrgProviders()
      .then(setOrgProviders)
      .finally(() => setLoadingProviders(false));
  }, [step]);

  // Pre-fill invite email from provider record
  useEffect(() => {
    if (selected?.email) setInviteEmail(selected.email);
  }, [selected]);

  // ── Step 1 handlers ────────────────────────────────────────────────────────

  const handlePickExisting = (p: ProviderItem) => {
    setSelected(p);
    setStep('confirm');
  };

  const handleCreateAndProceed = async () => {
    if (!newName.trim()) { setError('Provider name is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const created = await createProvider({
        name:         newName.trim(),
        email:        newEmail.trim() || undefined,
        phone:        newPhone.trim() || undefined,
        service_type: newServiceType.trim() || undefined,
      });
      setSelected(created);
      setStep('confirm');
    } catch {
      setError('Failed to create provider. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // ── Step 2 handlers ────────────────────────────────────────────────────────

  const handleSendInvite = async () => {
    if (!selected) return;
    if (!inviteEmail.trim()) { setError('Email address is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const result = await inviteProvider({
        provider_id: selected.id,
        email:       inviteEmail.trim(),
        case_id:     caseId,
      });
      if (result.magic_link) {
        // Dev mode: show link so tester can open it
        setInviteDevLink(result.magic_link);
      } else {
        onInviteSent();
        onClose();
      }
    } catch {
      setError('Failed to send invite. Please try again.');
      setSaving(false);
    }
  };

  const filteredProviders = orgProviders.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto">

        {/* ── Dev-mode success ─────────────────────────────────────────────── */}
        {inviteDevLink && (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-[#0b2b43]">Invite sent ✓</h2>
            <div className="rounded-lg border border-[#fcd34d] bg-[#fffbeb] p-3">
              <p className="text-xs font-semibold text-[#92400e] mb-1">
                Dev mode — no RESEND_API_KEY set
              </p>
              <p className="text-xs text-[#78350f] mb-2">
                Copy this magic link to test the provider portal:
              </p>
              <input
                readOnly
                value={inviteDevLink}
                className="w-full text-xs rounded border border-[#fcd34d] bg-white px-2 py-1.5 font-mono"
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
            </div>
            <div className="flex justify-end">
              <Button onClick={() => { onInviteSent(); onClose(); }}>Done</Button>
            </div>
          </div>
        )}

        {/* ── Step 1: pick / create ─────────────────────────────────────── */}
        {!inviteDevLink && step === 'pick' && (
          <>
            <h2 className="text-base font-semibold text-[#0b2b43] mb-1">Invite a provider</h2>
            <p className="text-sm text-[#6b7280] mb-4">
              Choose an existing provider or add a new one.
            </p>

            {/* Toggle */}
            <div className="flex gap-0 mb-4 rounded-lg border border-[#e2e8f0] overflow-hidden w-fit">
              {(['existing', 'new'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setError(''); }}
                  className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                    mode === m
                      ? 'bg-[#0b2b43] text-white'
                      : 'bg-white text-[#374151] hover:bg-[#f9fafb]'
                  }`}
                >
                  {m === 'existing' ? 'Existing provider' : 'New provider'}
                </button>
              ))}
            </div>

            {mode === 'existing' ? (
              <>
                <Input
                  value={search}
                  onChange={setSearch}
                  placeholder="Search providers…"
                  fullWidth
                />
                <div className="mt-3 space-y-1 max-h-60 overflow-y-auto">
                  {loadingProviders ? (
                    <p className="text-sm text-[#94a3b8] py-4 text-center">Loading…</p>
                  ) : filteredProviders.length === 0 ? (
                    <p className="text-sm text-[#94a3b8] py-4 text-center">No providers found.</p>
                  ) : (
                    filteredProviders.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => handlePickExisting(p)}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border border-[#e2e8f0] hover:border-[#93c5fd] hover:bg-[#eff6ff] text-left transition-colors"
                      >
                        <div className="w-8 h-8 rounded-full bg-[#0b2b43] text-white text-xs font-semibold flex items-center justify-center shrink-0">
                          {p.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div className="text-sm font-medium text-[#0b2b43]">{p.name}</div>
                          {p.service_type && (
                            <div className="text-xs text-[#6b7280]">{p.service_type}</div>
                          )}
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-3">
                <Input
                  label="Name *"
                  value={newName}
                  onChange={setNewName}
                  placeholder="e.g. Paris Relocation Partners"
                  fullWidth
                  disabled={saving}
                />
                <Input
                  label="Email"
                  type="email"
                  value={newEmail}
                  onChange={setNewEmail}
                  placeholder="contact@provider.com"
                  fullWidth
                  disabled={saving}
                />
                <Input
                  label="Phone"
                  value={newPhone}
                  onChange={setNewPhone}
                  placeholder="+33 1 23 45 67 89"
                  fullWidth
                  disabled={saving}
                />
                <Input
                  label="Service type"
                  value={newServiceType}
                  onChange={setNewServiceType}
                  placeholder="e.g. Housing, Moving, Legal, Tax"
                  fullWidth
                  disabled={saving}
                />
                {error && <p className="text-sm text-[#dc2626]">{error}</p>}
                <div className="flex justify-end gap-3 pt-1">
                  <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
                  <button
                    onClick={handleCreateAndProceed}
                    disabled={saving}
                    className="px-4 py-2 rounded-lg bg-[#0b2b43] text-white text-sm font-semibold hover:bg-[#1a3d5c] disabled:opacity-50 transition-colors"
                  >
                    {saving ? 'Creating…' : 'Create & continue'}
                  </button>
                </div>
              </div>
            )}

            {mode === 'existing' && (
              <div className="flex justify-end mt-4">
                <Button variant="outline" onClick={onClose}>Cancel</Button>
              </div>
            )}
          </>
        )}

        {/* ── Step 2: confirm email + send ─────────────────────────────── */}
        {!inviteDevLink && step === 'confirm' && selected && (
          <>
            <h2 className="text-base font-semibold text-[#0b2b43] mb-1">Send invite</h2>
            <p className="text-sm text-[#6b7280] mb-4">
              Inviting <span className="font-medium text-[#374151]">{selected.name}</span> to this case.
              They will receive a magic link giving access to their task portal.
            </p>

            <div className="space-y-4">
              <Input
                label="Send invite to *"
                type="email"
                value={inviteEmail}
                onChange={setInviteEmail}
                placeholder="provider@example.com"
                fullWidth
                disabled={saving}
              />

              <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2.5 text-xs text-[#6b7280] space-y-1">
                <div>
                  <span className="font-medium text-[#374151]">Provider: </span>
                  {selected.name}
                  {selected.service_type && ` · ${selected.service_type}`}
                </div>
                <div>
                  <span className="font-medium text-[#374151]">Case: </span>
                  {caseId}
                </div>
                <div>
                  <span className="font-medium text-[#374151]">Link expires: </span>
                  7 days
                </div>
              </div>

              {error && <p className="text-sm text-[#dc2626]">{error}</p>}

              <div className="flex justify-between gap-3 pt-1">
                {!preselectedProvider && (
                  <button
                    onClick={() => { setStep('pick'); setError(''); }}
                    className="text-sm text-[#6b7280] hover:text-[#374151]"
                    disabled={saving}
                  >
                    ← Back
                  </button>
                )}
                <div className="flex gap-3 ml-auto">
                  <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
                  <button
                    onClick={handleSendInvite}
                    disabled={saving}
                    className="px-4 py-2 rounded-lg bg-[#0b2b43] text-white text-sm font-semibold hover:bg-[#1a3d5c] disabled:opacity-50 transition-colors"
                  >
                    {saving ? 'Sending…' : 'Send invite'}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
