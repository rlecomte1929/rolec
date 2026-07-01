import React, { useEffect, useState } from "react";
import { Button } from "../../components/antigravity/Button";
import { Input } from "../../components/antigravity/Input";
import { Card } from "../../components/antigravity/Card";
import apiClient from "../../api/client";

interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action_type: string;
  new_value: Record<string, unknown> | null;
  actor_id: string | null;
  created_at: string;
}

interface AuditLogResponse {
  items: AuditLogEntry[];
  limit: number;
  offset: number;
}

export default function AdminAuditLogPage() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [since, setSince] = useState("");
  const [actor, setActor] = useState("");
  const [event, setEvent] = useState("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  const fetchLogs = async (params: {
    since?: string;
    actor?: string;
    event?: string;
    offset?: number;
  } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (params.since) query.set("since", params.since);
      if (params.actor) query.set("actor", params.actor);
      if (params.event) query.set("event", params.event);
      query.set("limit", String(LIMIT));
      query.set("offset", String(params.offset ?? 0));
      const res = await apiClient.get<AuditLogResponse>(`/api/admin/audit-log?${query}`);
      setItems(res.data.items);
    } catch {
      setError("Failed to load audit log");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchLogs();
  }, []);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    void fetchLogs({ since, actor, event, offset: 0 });
  };

  const handleClear = () => {
    setSince("");
    setActor("");
    setEvent("");
    setOffset(0);
    void fetchLogs({ offset: 0 });
  };

  const handlePrev = () => {
    const next = Math.max(0, offset - LIMIT);
    setOffset(next);
    void fetchLogs({ since, actor, event, offset: next });
  };

  const handleNext = () => {
    const next = offset + LIMIT;
    setOffset(next);
    void fetchLogs({ since, actor, event, offset: next });
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-navy-900 mb-6">Platform Audit Log</h1>

      <Card className="mb-6" padding="sm">
        <form onSubmit={handleFilter} className="flex flex-wrap gap-3 items-end">
          <div>
            <Input
              type="text"
              label="Since (ISO date)"
              value={since}
              onChange={(val) => setSince(val)}
              placeholder="2026-06-01T00:00:00"
            />
          </div>
          <div>
            <Input
              type="text"
              label="Actor"
              value={actor}
              onChange={(val) => setActor(val)}
              placeholder="actor-id"
            />
          </div>
          <div>
            <Input
              type="text"
              label="Event"
              value={event}
              onChange={(val) => setEvent(val)}
              placeholder="admin_added"
            />
          </div>
          <Button type="submit">Filter</Button>
          <Button type="button" variant="outline" onClick={handleClear}>
            Clear
          </Button>
        </form>
      </Card>

      {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

      {loading ? (
        <p className="text-navy-500">Loading…</p>
      ) : (
        <>
          <Card padding="none" className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-navy-100 text-left text-navy-600">
                  <th className="py-2 px-3">Time</th>
                  <th className="py-2 px-3">Event</th>
                  <th className="py-2 px-3">Entity</th>
                  <th className="py-2 px-3">Actor</th>
                  <th className="py-2 px-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-navy-400 text-center">
                      No audit log entries.
                    </td>
                  </tr>
                )}
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-navy-50 last:border-0">
                    <td className="py-1.5 px-3 text-navy-500 whitespace-nowrap">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                    </td>
                    <td className="py-1.5 px-3 font-mono text-teal-700">
                      {(item.new_value?.event as string) ?? item.action_type}
                    </td>
                    <td className="py-1.5 px-3 text-navy-600">{item.entity_type}</td>
                    <td className="py-1.5 px-3 text-navy-600 font-mono">
                      {item.actor_id ?? "—"}
                    </td>
                    <td className="py-1.5 px-3 text-navy-500 max-w-xs truncate">
                      {item.new_value
                        ? JSON.stringify(item.new_value)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex gap-3 mt-4">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={handlePrev}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={items.length < LIMIT}
              onClick={handleNext}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
