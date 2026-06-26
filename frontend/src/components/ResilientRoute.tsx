import React, { Suspense } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { logger } from '../lib/logger';
import { reportError } from '../lib/errorTracking';
import { Button } from './antigravity/Button';

/**
 * AIQ-655 — resilient wrapper for top-level routes.
 *
 * Wraps a route's element in:
 *   - a **Suspense** boundary (skeleton while the lazy chunk / data loads), and
 *   - an **ErrorBoundary** that recovers a *render* failure on that route
 *     without a full-page reload: a Retry resets the boundary, and the boundary
 *     auto-resets when the route changes (keyed by pathname), so navigating
 *     away from a crashed page always recovers.
 *
 * Data-fetch failures (500 / offline) are handled at the page level by
 * `useResilientQuery`, which renders the error / offline state. Together they
 * guarantee a route shows exactly one of: skeleton, content, error, or offline.
 *
 * React Router renders one matched route at a time, so a single boundary keyed
 * by `pathname` is functionally per-route — no per-route wiring needed.
 */

function RouteSkeleton() {
  return (
    <div
      className="min-h-screen flex items-center justify-center bg-[#f5f7fa] px-6"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="rounded-2xl border border-[#e2e8f0] bg-white px-6 py-4 text-sm text-[#4b5563] shadow-sm">
        Loading…
      </div>
    </div>
  );
}

function RouteErrorState({
  error,
  onRetry,
  onGoHome,
}: {
  error: Error | null;
  onRetry: () => void;
  onGoHome: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f7fa] p-8">
      <div
        className="max-w-md w-full bg-white border border-[#e2e8f0] rounded-2xl p-8 text-center space-y-4"
        role="alert"
      >
        <div className="text-2xl font-semibold text-[#0b2b43]">This page hit a snag</div>
        <p className="text-sm text-[#4b5563]">
          Something went wrong loading this page. Retry, or head back to your dashboard — your data is safe.
        </p>
        {error?.message && (
          <pre className="text-xs text-left bg-[#f8fafc] border border-[#e2e8f0] rounded-lg p-3 overflow-auto max-h-32 text-[#6b7280]">
            {error.message}
          </pre>
        )}
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button variant="primary" onClick={onRetry}>
            Retry
          </Button>
          <Button variant="outline" onClick={onGoHome}>
            Go to home
          </Button>
        </div>
      </div>
    </div>
  );
}

interface BoundaryProps {
  /** When this changes, a previously-caught error is cleared (route changed). */
  resetKey: string;
  onGoHome: () => void;
  children: React.ReactNode;
}
interface BoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ResilientErrorBoundary extends React.Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { hasError: true, error };
  }

  componentDidUpdate(prev: BoundaryProps) {
    // Recover automatically when the user navigates to a different route.
    if (prev.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: null });
    }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    logger.error('[ResilientRoute]', error, info.componentStack);
    // EH-1: report render crashes to the capture-error service (was console-only).
    reportError({ message: error.message, stack: error.stack ?? null, componentName: 'ResilientRoute' });
  }

  private reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (this.state.hasError) {
      return (
        <RouteErrorState
          error={this.state.error}
          onRetry={this.reset}
          onGoHome={this.props.onGoHome}
        />
      );
    }
    return this.props.children;
  }
}

export const ResilientRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <ResilientErrorBoundary resetKey={location.pathname} onGoHome={() => navigate('/')}>
      <Suspense fallback={<RouteSkeleton />}>{children}</Suspense>
    </ResilientErrorBoundary>
  );
};
