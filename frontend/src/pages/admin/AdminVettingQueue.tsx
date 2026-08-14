import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Alert, Badge } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { AdminLayout } from './AdminLayout';

type PendingCapability = {
  supplier_id: string;
  supplier_name: string;
  capability_id: string;
  service_category: string;
  country_code?: string | null;
  city_name?: string | null;
  source?: string | null;
  source_url?: string | null;
  /** [AIQ-1788] Present for registry-harvested suppliers; absent for manually-added ones. */
  accreditation?: {
    body: string;
    number?: string | null;
    valid_until?: string | null;
    status: string;
    evidence_url?: string | null;
  } | null;
  created_at?: string | null;
};

function errMessage(err: unknown, fallback: string): string {
  const msg =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : (err as Error)?.message;
  return String(msg || fallback);
}

export const AdminVettingQueue: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<PendingCapability[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rejectingCapId, setRejectingCapId] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await suppliersAPI.listPendingCapabilities();
      setItems((data.capabilities || []) as PendingCapability[]);
    } catch (err: unknown) {
      setError(errMessage(err, 'Failed to load pending capabilities'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const approve = useCallback(
    async (row: PendingCapability) => {
      setSaving(true);
      setError(null);
      try {
        await suppliersAPI.approveCapability(row.supplier_id, row.capability_id);
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to approve capability'));
      } finally {
        setSaving(false);
      }
    },
    [load]
  );

  const reject = useCallback(
    async (row: PendingCapability, notes: string) => {
      if (!notes.trim()) return;
      setSaving(true);
      setError(null);
      try {
        await suppliersAPI.rejectCapability(row.supplier_id, row.capability_id, notes.trim());
        setRejectingCapId(null);
        setRejectNotes('');
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to reject capability'));
      } finally {
        setSaving(false);
      }
    },
    [load]
  );

  return (
    <AdminLayout
      title="Vetting queue"
      subtitle="Supplier capabilities awaiting a platform review decision"
    >
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <Card padding="lg">
        {loading ? (
          <p className="text-sm text-[#6b7280]">Loading pending capabilities…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[#6b7280]">
            No pending capabilities — catalog is fully reviewed.
          </p>
        ) : (
          <ul className="divide-y divide-[#e5e7eb]">
            {items.map((row) => (
              <li key={row.capability_id} className="py-4 flex justify-between items-start gap-4">
                <button
                  type="button"
                  className="text-left"
                  onClick={() => navigate(buildRoute('adminSuppliersDetail', { id: row.supplier_id }))}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[#0b2b43]">{row.supplier_name}</span>
                    {row.source && <Badge variant="neutral" size="sm">{row.source}</Badge>}
                  </div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    {row.service_category}
                    {row.country_code && ` • ${row.country_code}`}
                    {row.city_name && ` • ${row.city_name}`}
                  </div>
                  {row.created_at && (
                    <div className="text-xs text-[#9ca3af] mt-1">
                      Discovered {new Date(row.created_at).toLocaleDateString()}
                    </div>
                  )}
                </button>

                {/* [AIQ-1788] Registry-harvested suppliers arrive with accreditation evidence.
                    Approving one without being able to see WHICH register vouched for it is a
                    rubber stamp, and the evidence is the only thing separating a harvested
                    candidate from a scrape. Absent for manually-added suppliers, so both the
                    block and the link render only when there is something to show. */}
                {(row.accreditation || row.source_url) && (
                  <div className="text-xs text-[#6b7280] mt-1 min-w-0 flex-1">
                    {row.accreditation && (
                      <div>
                        <span className="text-[#0b2b43]">{row.accreditation.body}</span>
                        {row.accreditation.number && ` · ${row.accreditation.number}`}
                        {row.accreditation.valid_until &&
                          ` · expires ${row.accreditation.valid_until}`}
                        {row.accreditation.status === 'claimed' && (
                          <span className="text-[#9ca3af]"> · unverified</span>
                        )}
                      </div>
                    )}
                    {row.source_url && (
                      <a
                        href={
                          row.source_url.startsWith('http')
                            ? row.source_url
                            : `https://${row.source_url}`
                        }
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-accent-700 underline break-all"
                      >
                        Check the register ↗
                      </a>
                    )}
                  </div>
                )}

                <div className="flex flex-col items-end gap-2 shrink-0">
                  <Button variant="secondary" size="sm" onClick={() => approve(row)} disabled={saving}>
                    Approve
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setRejectingCapId((prev) => (prev === row.capability_id ? null : row.capability_id))
                    }
                    disabled={saving}
                  >
                    Reject
                  </Button>
                  {rejectingCapId === row.capability_id && (
                    <div className="w-56">
                      <textarea
                        value={rejectNotes}
                        onChange={(e) => setRejectNotes(e.target.value)}
                        rows={2}
                        placeholder="Reason for rejection (required)"
                        className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                      />
                      <div className="flex justify-end gap-2 mt-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setRejectingCapId(null);
                            setRejectNotes('');
                          }}
                          disabled={saving}
                        >
                          Cancel
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => reject(row, rejectNotes)}
                          disabled={saving || !rejectNotes.trim()}
                        >
                          Confirm reject
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </AdminLayout>
  );
};
