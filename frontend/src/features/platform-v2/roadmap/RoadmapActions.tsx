/**
 * I-4 — roadmap delivery actions: email the plan + download deadlines as .ics.
 * Rendered in the roadmap header when a caseId is available.
 */
import { useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { Alert } from '../../../components/antigravity/Alert';
import { ConfirmDialog } from '../shared';
import { emailRoadmapPlan, downloadCaseCalendar } from '../../../api/roadmapIntegrations';

export interface RoadmapActionsProps {
  caseId: string;
}

export function RoadmapActions({ caseId }: RoadmapActionsProps) {
  const [confirmEmail, setConfirmEmail] = useState(false);
  const [busy, setBusy] = useState<null | 'email' | 'calendar'>(null);
  const [notice, setNotice] = useState<{ variant: 'success' | 'error'; msg: string } | null>(null);

  const sendEmail = async () => {
    setConfirmEmail(false);
    setBusy('email');
    setNotice(null);
    try {
      const r = await emailRoadmapPlan(caseId);
      setNotice({ variant: 'success', msg: `Plan emailed to ${r.emailed_to}.` });
    } catch {
      setNotice({ variant: 'error', msg: "Couldn't send the email. Please try again." });
    } finally {
      setBusy(null);
    }
  };

  const downloadCalendar = async () => {
    setBusy('calendar');
    setNotice(null);
    try {
      await downloadCaseCalendar(caseId);
      setNotice({ variant: 'success', msg: 'Calendar file downloaded — open it to add your deadlines.' });
    } catch {
      setNotice({ variant: 'error', msg: "Couldn't generate the calendar file. Please try again." });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div style={{ marginTop: '12px' }}>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <Button variant="secondary" size="sm" onClick={() => setConfirmEmail(true)} disabled={busy !== null}>
          {busy === 'email' ? 'Sending…' : '✉ Email this plan'}
        </Button>
        <Button variant="secondary" size="sm" onClick={downloadCalendar} disabled={busy !== null}>
          {busy === 'calendar' ? 'Preparing…' : '📅 Add deadlines to calendar'}
        </Button>
      </div>
      {notice && (
        <div style={{ marginTop: '10px' }}>
          <Alert variant={notice.variant}>{notice.msg}</Alert>
        </div>
      )}
      <ConfirmDialog
        open={confirmEmail}
        title="Email this plan?"
        description="We'll email your relocation plan and key dates to your account email."
        confirmLabel="Send email"
        onConfirm={sendEmail}
        onCancel={() => setConfirmEmail(false)}
      />
    </div>
  );
}

export default RoadmapActions;
