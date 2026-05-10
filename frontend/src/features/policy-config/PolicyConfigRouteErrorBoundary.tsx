import React from 'react';
import { Card, Button } from '../../components/antigravity';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Isolates Compensation & Allowance route from the app root ErrorBoundary so
 * secondary API failures or render bugs in this subtree do not blank the whole admin shell.
 */
export class PolicyConfigRouteErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[PolicyConfigRouteErrorBoundary]', error.message, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card padding="lg" className="border-amber-200 bg-amber-50/80">
          <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">This section could not be displayed</h2>
          <p className="text-xs text-[#64748b] mb-3">
            The structured policy editor hit an unexpected error. You can try again or return to the dashboard.
          </p>
          {this.state.error?.message ? (
            <pre className="text-[11px] text-[#7a2a2a] bg-white/80 border border-amber-100 rounded p-2 mb-3 overflow-auto max-h-24">
              {this.state.error.message}
            </pre>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => this.setState({ hasError: false, error: null })}>
              Try again
            </Button>
            <Button size="sm" variant="ghost" onClick={() => (window.location.href = '/')}>
              Go to home
            </Button>
          </div>
        </Card>
      );
    }
    return this.props.children;
  }
}
