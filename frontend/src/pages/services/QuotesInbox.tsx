import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Card } from '../../components/antigravity';

export const QuotesInbox: React.FC = () => {
  return (
    <AppShell title="Quotes inbox" subtitle="Track vendor replies and quotation threads.">
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">
          RFQ conversations will appear here once vendors respond.
        </div>
      </Card>
    </AppShell>
  );
};
