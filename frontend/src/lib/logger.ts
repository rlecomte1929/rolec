/**
 * logger — AUDIT-A8 (AIQ-360)
 *
 * Thin wrapper around console that silences all output in production.
 * Import this module instead of calling console.* directly so that
 * debug/info/warn output is automatically stripped from prod builds
 * without requiring manual removal.
 *
 * Usage:
 *   import { logger } from '../lib/logger';
 *   logger.debug('Value:', x);
 *   logger.info('Done');
 *   logger.warn('Something odd');
 *   logger.error('Unexpected error', err);
 */

const isProd = typeof import.meta !== 'undefined' && (import.meta as { env?: { MODE?: string } }).env?.MODE === 'production';

/* eslint-disable no-console */
export const logger = {
  debug: isProd ? () => undefined : (...args: unknown[]) => console.debug(...args),
  info:  isProd ? () => undefined : (...args: unknown[]) => console.info(...args),
  warn:  isProd ? () => undefined : (...args: unknown[]) => console.warn(...args),
  error: isProd ? () => undefined : (...args: unknown[]) => console.error(...args),
  log:   isProd ? () => undefined : (...args: unknown[]) => console.log(...args),
} as const;
/* eslint-enable no-console */
