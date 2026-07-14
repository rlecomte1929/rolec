import React, { useMemo, useState } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Button, Card, Input } from '../../components/antigravity';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { servicesAPI } from '../../api/client';
import { RfqWorkflowDiagram } from '../../features/services/RfqWorkflowDiagram';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { buildRoute, type RouteKey } from '../../navigation/routes';
import { caseIdForAssignment, parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { track } from '../../analytics';

const SERVICE_LABELS: Record<string, string> = {
  living_areas: 'Living Areas',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurances: 'Insurance',
  electricity: 'Electricity',
};

// [AIQ-1515] Was "you ask shortlisted vendors for formal prices" — you didn't; HR did.
// [AIQ-1521] Now you DO: the request goes to the suppliers you picked, and they answer you
// directly. HR pre-approved who you may pick and what you may spend, and validates the offer you
// choose — they are the payer, not your postbox. This sentence describes the model; the banner
// after you send states what actually happened, which is the only place we assert a fact.
const RFQ_SUBTITLE =
  'RFQ means Request For Quotation: you ask your shortlisted providers for a formal price and compare their offers. Your HR team validates the one you choose.';

export const ServicesRfqNew: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, shortlist } = useServicesFlow();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();
  // [AIQ-1285] caseId from the path is authoritative; fall back to legacy ?assignment=.
  const { caseId: pathCaseId } = useParams<{ caseId?: string }>();
  const queryAssignmentId = useMemo(
    () => pathCaseId ?? parseAssignmentSearchParam(location.search),
    [pathCaseId, location.search],
  );
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );
  // AIQ-1334: employee case sub-routes are keyed by case_id — build with the resolved case_id.
  const routeCaseId = caseIdForAssignment(linkedSummaries, assignmentId) ?? pathCaseId ?? '';
  const caseStep = (key: RouteKey) => buildRoute(key, { caseId: routeCaseId });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  // [AIQ-1523] Suppliers the backend could not reach (a catalog item with no supplier on
  // record). The RFQ still goes to the rest — but the employee is told who was left out,
  // rather than us silently sending to fewer suppliers than they chose.
  const [unreachable, setUnreachable] = useState<string[]>([]);
  // [AIQ-1521] Who actually received the request, and who did not and why. Never assumed —
  // always read back from the response, because with supplier dispatch off nobody is emailed.
  const [contacted, setContacted] = useState<string[]>([]);
  const [notContacted, setNotContacted] = useState<Array<{ supplier: string; reason: string }>>([]);

  // [AIQ-1520] Several vendors may be shortlisted per service — iterate them all.
  const shortlisted = useMemo(() => {
    if (!recommendations) return [];
    const items: Array<{ service: string; vendor: { item_id: string; name: string } }> = [];
    for (const [category, res] of Object.entries(recommendations)) {
      for (const selectedId of shortlist.get(category) ?? []) {
        const vendor = res.recommendations.find((r) => r.item_id === selectedId);
        if (vendor) items.push({ service: category, vendor });
      }
    }
    return items;
  }, [recommendations, shortlist]);

  const handleSend = async () => {
    if (!assignmentId || sending || sent || shortlisted.length === 0) return;
    setSending(true);
    setSendError(null);
    try {
      // [AIQ-1523] This now creates a REAL RFQ (rfqs + one rfq_recipients row per supplier)
      // instead of a quote_requests row. That table was a dead end: no supplier could ever
      // answer it, and the HR payer view reads rfqs/quotes — which nothing wrote to. This is
      // the call that finally gives them a writer.
      //
      // Dedupe both lists: three shortlisted movers are ONE rfq item ("movers") and THREE
      // recipients, not three items.
      const services = Array.from(new Set(shortlisted.map(({ service }) => service)));
      const items = services.map((service) => {
        const serviceNotes = shortlisted
          .filter((s) => s.service === service)
          .map(({ vendor }) => {
            const note = (notes[vendor.item_id] || '').trim();
            return note ? `${vendor.name}: ${note}` : null;
          })
          .filter(Boolean)
          .join(' | ');
        // requirements is the per-service brief the supplier quotes against — so the note
        // belongs on ITS service, not smeared across every item.
        return { service_key: service, requirements: serviceNotes ? { notes: serviceNotes } : {} };
      });
      const supplierIds = Array.from(new Set(shortlisted.map(({ vendor }) => vendor.item_id)));

      const res = await servicesAPI.createRfq(assignmentId, items, supplierIds);
      // Tell the employee plainly if a supplier they chose could not be reached, rather than
      // silently sending to fewer suppliers than they picked.
      setUnreachable(res.unreachable ?? []);
      setContacted(res.contacted ?? []);
      setNotContacted(res.not_contacted ?? []);
      setSent(true);
      // AIQ-1436: one rfq_created per shortlisted vendor (mirrors the backend
      // canonical event name; the RFQ is a batch submit over the shortlist).
      shortlisted.forEach(({ service, vendor }) => {
        track('rfq_created', { supplier_id: vendor.item_id, service_category: service, case_id: assignmentId });
      });
    } catch (e) {
      setSendError((e as Error).message ?? 'Failed to send. Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (assignmentLoading) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center gap-3 text-sm text-[#475569]" role="status" aria-live="polite">
            <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
            <span>Loading your assignment…</span>
          </div>
        </Card>
      </AppShell>
    );
  }

  if (needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <EmployeeScopedAssignmentPicker
          title="Which assignment is this for?"
          subtitle="Pick the assignment your shortlist belongs to."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('servicesRfqNew')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">
            Sign in as an employee with an active assignment to use this step.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (shortlisted.length === 0) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Build a shortlist first: choose one provider per service on the recommendations page, then come back here.
          </p>
          <Button
            onClick={() =>
              navigate(caseStep('caseServicesRecommendations'))
            }
          >
            Back to recommendations
          </Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Request quotations (RFQ)" subtitle={RFQ_SUBTITLE}>
      <ServicesNavRibbon />

      <div className="mb-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#334155] leading-relaxed">
        <p>
          <abbr title="Request For Quotation" className="no-underline font-semibold text-[#0b2b43]">
            RFQ
          </abbr>{' '}
          <span className="text-[#64748b]">(Request For Quotation)</span> — you send your requirements to your
          shortlisted providers; they reply with <strong>proposed prices</strong>. You compare the offers and pick
          the one that suits you; your <strong>HR team validates it</strong>, because the company pays. Each request
          is tracked on your roadmap.
        </p>
      </div>

      <RfqWorkflowDiagram />

      <p className="text-sm font-medium text-[#0b2b43] mt-8 mb-3">Your shortlisted vendors</p>
      {/* [AIQ-1515] Used to read "These are the providers your requests will go to." — nothing
          was sent to a provider back then, so it was false.
          [AIQ-1521] It can now be true, but only when supplier dispatch is on, and this text
          renders BEFORE we send, when we don't yet know. So it promises nothing: the banner
          after sending is where we state who was actually reached. */}
      <p className="text-xs text-[#64748b] mb-4">
        Add an optional note for each, then send your request. We&apos;ll tell you exactly who it
        reached.
      </p>
      {shortlisted.map(({ service, vendor }) => (
        <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4 mb-3 bg-white">
          <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
          <div className="text-sm text-[#6b7280] mb-2">Service: {SERVICE_LABELS[service] || service}</div>
          <Input
            label="Optional note"
            value={notes[vendor.item_id] || ''}
            onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
            placeholder="e.g. Moving date, special requirements…"
            fullWidth
          />
        </div>
      ))}
      {/* [AIQ-1515] Was "Quotation requests sent", which implied the vendors had been contacted.
          They had not.
          [AIQ-1523] Kept as "sent to HR", because creating an RFQ still reached no supplier.
          [AIQ-1521] Now it depends on what actually happened, so we read it off the response
          instead of hardcoding either claim. `contacted` non-empty = those suppliers really do
          have the request in their inbox. Empty = nobody outside ReloPass has seen it, and we
          say exactly that. */}
      {sent && contacted.length > 0 ? (
        <div
          data-testid="rfq-sent"
          className="mt-4 flex items-start gap-2 rounded-lg border border-green-100 bg-green-50 p-3 text-sm text-green-700"
        >
          ✅{' '}
          <span>
            Sent to {contacted.length} {contacted.length === 1 ? 'provider' : 'providers'} —{' '}
            {contacted.join(', ')}. They&apos;ll reply with a price, and you&apos;ll see the offers
            here to compare. Your HR team validates the one you choose. We&apos;ve added this to
            your roadmap.
          </span>
        </div>
      ) : null}
      {sent && contacted.length === 0 ? (
        <div
          data-testid="rfq-sent"
          className="mt-4 flex items-start gap-2 rounded-lg border border-green-100 bg-green-50 p-3 text-sm text-green-700"
        >
          ✅{' '}
          <span>
            Request recorded — your HR team can see the providers you picked and will follow up.
            We&apos;ve added this to your roadmap.
          </span>
        </div>
      ) : null}
      {sent && (unreachable.length > 0 || notContacted.length > 0) ? (
        <div
          data-testid="rfq-unreachable"
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800"
        >
          <span className="font-semibold">We couldn’t reach every provider you picked.</span>
          <ul className="mt-1 list-disc pl-5">
            {unreachable.map((u) => (
              <li key={u}>{u}</li>
            ))}
            {notContacted.map((n) => (
              <li key={n.supplier}>
                {n.supplier} — {n.reason}
              </li>
            ))}
          </ul>
          <p className="mt-1">
            Your HR team can still reach them for you. Everyone else was included.
          </p>
        </div>
      ) : null}
      {!sent ? (
        <div className="mt-4 flex flex-col items-end gap-2">
          {sendError && <p className="text-xs text-red-500">{sendError}</p>}
          <Button type="button" onClick={handleSend} disabled={sending}>
            {sending ? 'Sending…' : 'Send quotation requests'}
          </Button>
        </div>
      ) : null}
    </AppShell>
  );
};
