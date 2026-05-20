/**
 * ProviderStatusCell
 *
 * A single cell in the Provider × Case Status Grid.
 * Shows a colour-coded badge representing the status of one provider type
 * for a specific case.
 *
 * Clickable — navigates to the HR command-center case detail page where
 * the ProviderCoordinationPanel lives.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridCellStatus } from '../../api/client';
import { buildRoute } from '../../navigation/routes';

interface ProviderStatusCellProps {
  status: GridCellStatus;
  caseId: string;
  /** Provider type label shown in tooltip */
  providerType: string;
}

const STATUS_CONFIG: Record<
  GridCellStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  'on-track': {
    label: 'On track',
    bg: '#d1fae5',
    text: '#065f46',
    dot: '#10b981',
  },
  'at-risk': {
    label: 'At risk',
    bg: '#fef3c7',
    text: '#92400e',
    dot: '#f59e0b',
  },
  blocked: {
    label: 'Blocked',
    bg: '#fee2e2',
    text: '#991b1b',
    dot: '#ef4444',
  },
  complete: {
    label: 'Complete',
    bg: '#dbeafe',
    text: '#1e40af',
    dot: '#3b82f6',
  },
  'not-assigned': {
    label: 'No provider',
    bg: '#f3f4f6',
    text: '#6b7280',
    dot: '#d1d5db',
  },
};

export const ProviderStatusCell: React.FC<ProviderStatusCellProps> = ({
  status,
  caseId,
  providerType,
}) => {
  const navigate = useNavigate();
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG['not-assigned'];

  const handleClick = () => {
    navigate(buildRoute('hrCommandCenterCase', { id: caseId }));
  };

  return (
    <button
      onClick={handleClick}
      title={`${providerType}: ${cfg.label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 9999,
        border: 'none',
        cursor: 'pointer',
        backgroundColor: cfg.bg,
        color: cfg.text,
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1,
        whiteSpace: 'nowrap',
        transition: 'opacity 0.15s',
      }}
      onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '0.8')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = '1')}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          backgroundColor: cfg.dot,
          flexShrink: 0,
        }}
      />
      {cfg.label}
    </button>
  );
};
