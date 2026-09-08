import React from 'react';
import { AppShell } from '../components/AppShell';

interface PlaceholderPageProps {
  title: string;
  description: string;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ title, description }) => {
  return (
    <AppShell title={title} subtitle={description}>
      <div className="text-sm text-[#6b7280]">This section is included for demo navigation.</div>
    </AppShell>
  );
};
