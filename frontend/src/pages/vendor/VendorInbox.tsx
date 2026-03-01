import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Card } from '../../components/antigravity';

export const VendorInbox: React.FC = () => {
  return (
    <AppShell title="Vendor inbox" subtitle="RFQs assigned to your vendor account.">
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">
          Vendor RFQs will appear here once the RFQ workflow is active.
        </div>
      </Card>
    </AppShell>
  );
};
