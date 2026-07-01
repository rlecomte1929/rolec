import React, { useEffect, useState } from "react";
import { Button } from "../../components/antigravity/Button";
import { Input } from "../../components/antigravity/Input";
import { Card } from "../../components/antigravity/Card";
import apiClient from "../../api/client";

interface AdminEntry {
  email: string;
  enabled: boolean;
  added_by_user_id: string | null;
  created_at: string;
}

export default function AdminAdminsPage() {
  const [admins, setAdmins] = useState<AdminEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchAdmins = async () => {
    try {
      const res = await apiClient.get<{ items: AdminEntry[] }>("/api/admin/admins");
      setAdmins(res.data.items);
    } catch {
      setError("Failed to load admins");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchAdmins();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;
    setAdding(true);
    try {
      await apiClient.post("/api/admin/admins", { email: newEmail.trim() });
      setNewEmail("");
      await fetchAdmins();
    } catch {
      setError("Failed to add admin");
    } finally {
      setAdding(false);
    }
  };

  const handleToggle = async (email: string, currentEnabled: boolean) => {
    try {
      await apiClient.patch(`/api/admin/admins/${encodeURIComponent(email)}`, {
        enabled: !currentEnabled,
      });
      await fetchAdmins();
    } catch {
      setError("Failed to update admin");
    }
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-navy-900 mb-6">Admin Accounts</h1>

      <Card className="mb-6" padding="sm">
        <form onSubmit={(e) => { void handleAdd(e); }} className="flex gap-3 items-end">
          <div className="flex-1">
            <Input
              type="email"
              label="Add admin by email"
              value={newEmail}
              onChange={(val) => setNewEmail(val)}
              placeholder="admin@company.com"
              required
            />
          </div>
          <Button type="submit" disabled={adding}>
            {adding ? "Adding…" : "Add Admin"}
          </Button>
        </form>
      </Card>

      {error && (
        <p className="text-red-600 text-sm mb-4">{error}</p>
      )}

      {loading ? (
        <p className="text-navy-500">Loading…</p>
      ) : (
        <Card padding="none">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-navy-100 text-left text-navy-600">
                <th className="py-2 px-4">Email</th>
                <th className="py-2 px-4">Status</th>
                <th className="py-2 px-4">Added</th>
                <th className="py-2 px-4">Action</th>
              </tr>
            </thead>
            <tbody>
              {admins.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-navy-400 text-center">
                    No admins yet.
                  </td>
                </tr>
              )}
              {admins.map((a) => (
                <tr key={a.email} className="border-b border-navy-50 last:border-0">
                  <td className="py-2 px-4 font-mono text-navy-800">{a.email}</td>
                  <td className="py-2 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        a.enabled
                          ? "bg-teal-50 text-teal-700"
                          : "bg-navy-50 text-navy-500"
                      }`}
                    >
                      {a.enabled ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="py-2 px-4 text-navy-500">
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="py-2 px-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => { void handleToggle(a.email, a.enabled); }}
                    >
                      {a.enabled ? "Disable" : "Enable"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
