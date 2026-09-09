import React, { useEffect, useState } from 'react';
import { Send, Settings } from 'lucide-react';
import { useProspects } from '../../hooks/useProspects';
import { useFollowUpQueue, daysSinceSent } from '../../hooks/useFollowUpQueue';
import { useTemplates } from '../../hooks/useTemplates';
import { useMessages } from '../../hooks/useMessages';
import { AddProspectModal } from '../../components/outreach/AddProspectModal';
import { ProspectDrawer } from '../../components/outreach/ProspectDrawer';
import { TemplateManager } from '../../components/outreach/TemplateManager';
import { personaliseMessage, pickBestTemplate } from '../../utils/messagePersonaliser';
import type { LinkedInProspect, ProspectInsert, ProspectStatus } from '../../types/outreach';
import { getTestDriveReferrals, type TestDriveReferral } from '../../api/adminTestDrive';
import { AdminLayout } from './AdminLayout';

export function OutreachPage(): React.ReactElement {
  const { prospects, loading, error, createProspect, updateProspect, updateStatus } = useProspects();
  const { createMessage } = useMessages();
  const { templates } = useTemplates();
  const followUpQueue = useFollowUpQueue(prospects);

  const [showAdd, setShowAdd] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [selectedProspect, setSelectedProspect] = useState<LinkedInProspect | null>(null);
  const [filterFollowUp, setFilterFollowUp] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [draftWarning, setDraftWarning] = useState<string | null>(null);

  // AIQ-1566 (BUG-260717-3D77): people a tester recommended during the test campaign.
  // Read-only — soft-fails to an empty list so a referral outage never blocks outreach.
  const [referrals, setReferrals] = useState<TestDriveReferral[]>([]);
  const [prefill, setPrefill] = useState<Record<string, string> | undefined>(undefined);
  useEffect(() => {
    let active = true;
    getTestDriveReferrals()
      .then((r) => { if (active) setReferrals(r); })
      .catch(() => { if (active) setReferrals([]); });
    return () => { active = false; };
  }, []);

  // A referral has no LinkedIn URL or company name (both required on linkedin_prospects),
  // so it can't become a prospect row on its own — the admin still supplies those. We match
  // on the name (the only field the two share; the table has no email/phone column) purely
  // to mark what's already been added, never to hide or auto-merge anything.
  const prospectNames = new Set(prospects.map((p) => p.full_name.trim().toLowerCase()));
  const referralAdded = (r: TestDriveReferral): boolean =>
    !!r.referral_name && prospectNames.has(r.referral_name.trim().toLowerCase());

  const addReferralAsProspect = (r: TestDriveReferral): void => {
    setPrefill({
      full_name: r.referral_name ?? '',
      job_title: r.referral_company_role ?? '',
      notes: [
        `Referred by ${r.referred_by ?? 'a tester'} in the test-drive survey.`,
        r.referral_contact ? `Contact given: ${r.referral_contact}` : null,
        r.referral_consent
          ? 'The referrer confirmed they are happy to be contacted.'
          : 'NOT CONSENTED — the referrer did not confirm contact. Do not reach out yet.',
      ].filter(Boolean).join(' '),
      corridor_relevance: '',
    });
    setShowAdd(true);
  };

  const handleAddProspect = async (data: ProspectInsert): Promise<void> => {
    const prospect = await createProspect(data);
    const template = pickBestTemplate(templates, 'initial');
    if (template) {
      const body = personaliseMessage(template.body_template, prospect);
      await createMessage({
        prospect_id: prospect.id,
        message_type: 'initial',
        body,
        status: 'draft',
        subject_line: null,
        personalisation_notes: `Generated from template: ${template.name}`,
        approved_at: null,
        sent_at: null,
        copied_to_clipboard_at: null,
      });
      await updateStatus(prospect.id, 'message_drafted');
      setDraftWarning(null);
    } else {
      setDraftWarning('No active initial template — open Settings ⚙ to add one, then regenerate the draft from the prospect drawer.');
    }
  };

  // Auto-clear filter when the follow-up queue drains
  useEffect(() => {
    if (followUpQueue.length === 0) setFilterFollowUp(false);
  }, [followUpQueue.length]);

  // Keep selectedProspect in sync when the list updates (e.g. status change from drawer)
  const syncedProspect = selectedProspect
    ? (prospects.find((p) => p.id === selectedProspect.id) ?? selectedProspect)
    : null;

  const displayProspects = filterFollowUp
    ? followUpQueue
    : showArchived
      ? prospects
      : prospects.filter((p) => p.status !== 'archived' && p.status !== 'not_interested');

  return (
    // BUG-260717-3D77: this page rendered standalone — the only admin surface with no
    // sidebar and no breadcrumb, so there was no way to tell where you were or navigate
    // out. AdminLayout supplies both (sidebar + "ReloPass admin / Outreach"), plus the
    // page container and PageHeader, so the local p-6/max-w-6xl wrapper and the duplicate
    // <h1> are dropped and the actions move to the layout's headerRight slot. Same shape
    // as AdminTestDrive.tsx.
    <AdminLayout
      title="Outreach"
      subtitle={`LinkedIn Outreach CRM — prospects, drafts and follow-ups. ${prospects.length} total.`}
      headerRight={
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTemplates(true)}
            className="p-2 text-gray-500 hover:text-navy-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            title="Manage message templates"
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="bg-navy-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-navy-800 transition-colors"
          >
            + Add prospect
          </button>
        </div>
      }
    >

      {/* Follow-up banner */}
      {followUpQueue.length > 0 && (
        <div className="mb-4 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
          <span>
            ⚠️ {followUpQueue.length} prospect{followUpQueue.length !== 1 ? 's' : ''} haven&apos;t replied in 10+ days — follow-up drafts are ready.
          </span>
          <button
            className="ml-auto underline font-medium whitespace-nowrap"
            onClick={() => setFilterFollowUp((v) => !v)}
          >
            {filterFollowUp ? 'Show all →' : 'Review →'}
          </button>
        </div>
      )}

      {draftWarning && (
        <div className="mb-4 flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
          <span className="flex-1">⚙ {draftWarning}</span>
          <button onClick={() => setDraftWarning(null)} className="text-amber-600 hover:text-amber-800 flex-shrink-0">✕</button>
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          Failed to load prospects: {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-sm">Loading…</div>
      ) : displayProspects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Send className="w-10 h-10 text-gray-500 mb-4" />
          {filterFollowUp ? (
            <p className="text-gray-500 font-medium">No follow-ups due right now.</p>
          ) : (
            <>
              <p className="text-gray-500 font-medium mb-1">No prospects yet</p>
              <p className="text-gray-500 text-sm">Click &quot;+ Add prospect&quot; to get started.</p>
            </>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Role</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Corridor</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Sent</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Days</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayProspects.map((p) => (
                <ProspectRow
                  key={p.id}
                  prospect={p}
                  onOpen={() => setSelectedProspect(p)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Archived toggle */}
      {!filterFollowUp && (
        <div className="mt-3 text-center">
          <button
            onClick={() => setShowArchived((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-600 underline"
          >
            {showArchived ? 'Hide archived / not interested' : 'Show archived / not interested'}
          </button>
        </div>
      )}

      {/* AIQ-1566: referrals from the test campaign — so a recommended contact never has to
          be re-typed. Read-only; "Add as prospect" pre-fills the form (the admin still
          supplies the LinkedIn URL + company, which a referral simply doesn't carry). */}
      {referrals.length > 0 && (
        <div className="mt-8" data-testid="td-referrals">
          <div className="mb-2 flex items-baseline gap-2">
            <h2 className="text-sm font-semibold text-navy-900">Referrals from the test campaign</h2>
            <span className="text-xs text-gray-500">{referrals.length} recommended</span>
          </div>
          <p className="mb-3 text-xs text-gray-500">
            People a tester recommended you contact. Nothing here has been messaged — adding one
            just pre-fills the prospect form.
          </p>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Role</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Contact given</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Referred by</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Consent</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {referrals.map((r, idx) => {
                  const added = referralAdded(r);
                  return (
                    <tr key={`${r.referral_name ?? 'anon'}-${idx}`} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-navy-900">{r.referral_name || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">{r.referral_company_role || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">{r.referral_contact || '—'}</td>
                      <td className="px-4 py-3 text-gray-500">{r.referred_by || '—'}</td>
                      <td className="px-4 py-3">
                        {r.referral_consent ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">
                            Happy to be contacted
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800">
                            Not consented — don&apos;t contact yet
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {added ? (
                          <span className="text-xs text-gray-500">Already a prospect</span>
                        ) : (
                          <button
                            onClick={() => addReferralAsProspect(r)}
                            className="text-xs font-medium text-navy-700 hover:text-navy-900 underline"
                          >
                            Add as prospect →
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AddProspectModal
        open={showAdd}
        onClose={() => { setShowAdd(false); setPrefill(undefined); }}
        onSave={handleAddProspect}
        prefill={prefill}
        source={prefill ? 'test-drive-referral' : undefined}
      />

      <TemplateManager
        open={showTemplates}
        onClose={() => setShowTemplates(false)}
      />

      <ProspectDrawer
        prospect={syncedProspect}
        templates={templates}
        onClose={() => setSelectedProspect(null)}
        onUpdateProspect={updateProspect}
        onUpdateStatus={(id, status, extra) => updateStatus(id, status, extra)}
      />
    </AdminLayout>
  );
}

function ProspectRow({
  prospect: p,
  onOpen,
}: {
  prospect: LinkedInProspect;
  onOpen: () => void;
}): React.ReactElement {
  const days = daysSinceSent(p);
  const daysOverdue = days !== null && days >= 10 && !p.follow_up_sent_at && p.status === 'message_sent';

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 font-medium text-navy-900">
        <a
          href={p.linkedin_url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {p.full_name}
        </a>
      </td>
      <td className="px-4 py-3 text-gray-700">{p.company_name}</td>
      <td className="px-4 py-3 text-gray-600">{p.job_title}</td>
      <td className="px-4 py-3">
        {p.corridor_relevance ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-700">
            {p.corridor_relevance}
          </span>
        ) : (
          <span className="text-gray-500">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <StatusPill status={p.status} />
      </td>
      <td className="px-4 py-3 text-gray-500">
        {p.message_sent_at
          ? new Date(p.message_sent_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
          : <span className="text-gray-500">—</span>
        }
      </td>
      <td className="px-4 py-3">
        {days !== null ? (
          <span className={`text-xs font-medium ${daysOverdue ? 'text-red-600' : 'text-gray-500'}`}>
            {days}d{daysOverdue ? ' ⚠' : ''}
          </span>
        ) : (
          <span className="text-gray-500">—</span>
        )}
      </td>
      <td className="px-4 py-3">
        <button
          onClick={onOpen}
          className="text-xs text-navy-600 hover:text-navy-800 font-medium"
        >
          Open →
        </button>
      </td>
    </tr>
  );
}

const STATUS_LABELS: Record<ProspectStatus, string> = {
  flagged:         'Flagged',
  message_drafted: 'Drafted',
  message_sent:    'Sent',
  replied:         'Replied',
  follow_up_sent:  'Follow-up sent',
  converted:       'Converted',
  not_interested:  'Not interested',
  archived:        'Archived',
};

export const STATUS_CLASSES: Record<ProspectStatus, string> = {
  flagged:         'bg-gray-100 text-gray-600',
  message_drafted: 'bg-blue-50 text-blue-700',
  message_sent:    'bg-navy-50 text-navy-800',
  replied:         'bg-green-50 text-green-700',
  follow_up_sent:  'bg-yellow-50 text-yellow-700',
  converted:       'bg-teal-50 text-teal-700',
  not_interested:  'bg-red-50 text-red-600',
  archived:        'bg-gray-100 text-gray-500',
};

function StatusPill({ status }: { status: ProspectStatus }): React.ReactElement {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_CLASSES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export default OutreachPage;
