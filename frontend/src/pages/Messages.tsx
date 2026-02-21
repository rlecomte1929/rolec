import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Card } from '../components/antigravity';
import { hrAPI, employeeAPI } from '../api/client';
import { getAuthItem } from '../utils/demo';

export const Messages: React.FC = () => {
  const role = getAuthItem('relopass_role');
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = role === 'HR' || role === 'ADMIN'
          ? await hrAPI.listMessages()
          : await employeeAPI.listMessages();
        setMessages(res.messages || []);
      } catch {
        setMessages([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [role]);

  return (
    <AppShell title="Messages" subtitle="Invitation and case communications">
      {loading ? (
        <div className="text-sm text-[#6b7280] py-6">Loading messages...</div>
      ) : (
        <Card padding="lg">
          {messages.length === 0 ? (
            <div className="text-sm text-[#6b7280]">No messages yet.</div>
          ) : (
            <div className="space-y-4">
              {messages.map((m) => (
                <div key={m.id} className="border-b border-[#e2e8f0] pb-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">{m.subject}</div>
                  <div className="text-xs text-[#6b7280]">
                    Assignment: {m.assignment_id || '—'} · Status: {m.status || 'draft'}
                  </div>
                  <pre className="mt-2 text-sm whitespace-pre-wrap text-[#4b5563]">{m.body}</pre>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </AppShell>
  );
};
