import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import { ImmigrationAnswerPanel } from '../../features/immigration/ImmigrationAnswerPanel';

/**
 * Route: /employee/immigration-assistant
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict capture).
 */
export const ImmigrationAssistantPage: React.FC = () => (
  <AppShell title="Immigration Q&A" subtitle="Grounded, cited answers for your corridor">
    <Container maxWidth="xl" className="py-8">
      <ImmigrationAnswerPanel />
    </Container>
  </AppShell>
);
