import React from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Card, Button } from '../../components/antigravity';

export const VendorRfq: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  return (
    <AppShell title="RFQ detail" subtitle={`RFQ ${id || ''}`}>
      <Card padding="lg" className="space-y-4">
        <div className="text-sm text-[#6b7280]">
          Respond to the RFQ with a structured quote. Attachments coming soon.
        </div>
        <Button>Send reply</Button>
      </Card>
    </AppShell>
  );
};
