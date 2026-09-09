import React from 'react';
import { StatCard } from '../antigravity/StatCard';

interface KPICardProps {
  title: string;
  value: number | string;
  subtitle?: string;
}

export const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle }) => (
  <StatCard label={title} value={value} sub={subtitle} />
);
