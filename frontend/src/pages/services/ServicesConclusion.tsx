import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';

export const ServicesConclusion: React.FC = () => {
  return (
    <AppShell title="Final selection" subtitle="Confirm vendors and costs.">
      <Card padding="lg" className="space-y-4">
        <div className="text-sm text-[#6b7280]">
          Final vendor selection will appear here once quotes are received.
        </div>
        <Button variant="outline">Continue to contract (external)</Button>
      </Card>
    </AppShell>
  );
};
