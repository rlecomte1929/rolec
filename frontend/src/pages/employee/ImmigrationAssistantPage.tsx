import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import { ImmigrationAnswerPanel } from '../../features/immigration/ImmigrationAnswerPanel';

/**
 * Route: /employee/immigration-assistant
 * Unified relocation assistant (Slice 5): grounded Q&A spanning immigration
 * ("what does my move need") and company policy ("what does my company cover").
 */
export const ImmigrationAssistantPage: React.FC = () => (
  <AppShell title="Relocation Assistant" subtitle="Grounded answers about your move and your company's benefits">
    <Container maxWidth="xl" className="py-8">
      <ImmigrationAnswerPanel />
    </Container>
  </AppShell>
);
