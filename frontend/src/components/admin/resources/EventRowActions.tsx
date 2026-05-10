import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../antigravity';
import { buildRoute } from '../../../navigation/routes';

type EventRowActionsProps = {
  eventId: string;
  status?: string;
  onAction: (action: string, notes?: string) => Promise<void>;
  disabled?: boolean;
};

const VALID_TRANSITIONS: Record<string, string[]> = {
  draft: ['submit'],
  in_review: ['approve'],
  approved: ['publish'],
  published: ['unpublish', 'archive'],
  archived: ['restore'],
};

export const EventRowActions: React.FC<EventRowActionsProps> = ({
  eventId,
  status = 'draft',
  onAction,
  disabled,
}) => {
  const [working, setWorking] = useState(false);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approveNotes, setApproveNotes] = useState('');
  const actions = VALID_TRANSITIONS[status] || [];

  const handle = async (action: string, notes?: string) => {
    if (action === 'approve') {
      setShowApproveModal(true);
      return;
    }
    setWorking(true);
    try {
      await onAction(action, notes);
    } finally {
      setWorking(false);
      setShowApproveModal(false);
      setApproveNotes('');
    }
  };

  return (
    <div className="flex items-center gap-1 flex-wrap">
      <Link to={buildRoute('adminEventsEdit', { id: eventId })} className="text-[#0b2b43] text-xs hover:underline">
        Edit
      </Link>
      {actions.includes('submit') && (
        <button type="button" onClick={() => handle('submit')} disabled={disabled || working} className="text-xs text-amber-700 hover:underline">
          Submit
        </button>
      )}
      {actions.includes('approve') && (
        <button type="button" onClick={() => setShowApproveModal(true)} disabled={disabled || working} className="text-xs text-blue-700 hover:underline">
          Approve
        </button>
      )}
      {actions.includes('publish') && (
        <button type="button" onClick={() => handle('publish')} disabled={disabled || working} className="text-xs text-green-700 hover:underline">
          Publish
        </button>
      )}
      {actions.includes('unpublish') && (
        <button type="button" onClick={() => handle('unpublish')} disabled={disabled || working} className="text-xs text-slate-600 hover:underline">
          Unpublish
        </button>
      )}
      {actions.includes('archive') && (
        <button type="button" onClick={() => handle('archive')} disabled={disabled || working} className="text-xs text-slate-600 hover:underline">
          Archive
        </button>
      )}
      {actions.includes('restore') && (
        <button type="button" onClick={() => handle('restore')} disabled={disabled || working} className="text-xs text-blue-700 hover:underline">
          Restore
        </button>
      )}

      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowApproveModal(false)}>
          <div className="bg-white rounded-lg shadow-lg p-4 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h4 className="font-semibold mb-2">Approve event</h4>
            <label className="block text-sm text-slate-600 mb-2">Review notes (optional)</label>
            <textarea value={approveNotes} onChange={(e) => setApproveNotes(e.target.value)} rows={2} className="w-full border border-slate-200 rounded px-2 py-1 text-sm mb-4" />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handle('approve', approveNotes || undefined)} disabled={working}>
                {working ? 'Approving…' : 'Approve'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowApproveModal(false)}>Cancel</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
