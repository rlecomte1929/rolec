import type { ReactNode } from 'react';
import { useV2Flag } from './useV2Flag';
import type { V2FlagKey } from './flags';

interface V2GateProps {
  /** Which platform-v2 sub-flag controls this gate. */
  flag: V2FlagKey;
  /** Rendered when the flag is ON — the new (V2) implementation. */
  children: ReactNode;
  /** Rendered when the flag is OFF — the legacy implementation. */
  fallback: ReactNode;
}

/**
 * Renders the V2 implementation when the named flag is on, otherwise the
 * legacy fallback. Keep both implementations mounted nowhere — only one
 * subtree ever renders at a time.
 *
 * Usage:
 *   <V2Gate flag="companies" fallback={<AdminCompaniesLegacy />}>
 *     <AdminCompaniesV2 />
 *   </V2Gate>
 *
 * Strictly visual. No effects, no side effects, no router awareness.
 */
export function V2Gate({ flag, children, fallback }: V2GateProps) {
  const { on } = useV2Flag(flag);
  return <>{on ? children : fallback}</>;
}
