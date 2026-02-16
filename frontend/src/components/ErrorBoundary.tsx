import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#f5f7fa] p-8">
          <div className="max-w-md w-full bg-white border border-[#e2e8f0] rounded-2xl p-8 text-center space-y-4">
            <div className="text-2xl font-semibold text-[#0b2b43]">Something went wrong</div>
            <p className="text-sm text-[#4b5563]">
              An unexpected error occurred. Please reload the page or go back to the dashboard.
            </p>
            {this.state.error && (
              <pre className="text-xs text-left bg-[#f8fafc] border border-[#e2e8f0] rounded-lg p-3 overflow-auto max-h-32 text-[#6b7280]">
                {this.state.error.message}
              </pre>
            )}
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-[#0b2b43] text-white text-sm rounded-lg hover:bg-[#0a2236]"
              >
                Reload page
              </button>
              <button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.href = '/';
                }}
                className="px-4 py-2 border border-[#e2e8f0] text-[#4b5563] text-sm rounded-lg hover:bg-[#f8fafc]"
              >
                Go to home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
