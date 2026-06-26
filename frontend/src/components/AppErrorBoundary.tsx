import React from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { reportError } from '../lib/errorTracking';
import { Button } from './antigravity/Button';

interface Props {
  children: React.ReactNode;
  componentName?: string;
  fallback?: React.ReactNode;
}

function DefaultFallback() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-4">
      <p className="text-marketing-body font-semibold text-marketing-primary mb-2">
        Something went wrong.
      </p>
      <p className="text-sm text-marketing-text-subtle mb-6">
        Reload the page to try again.
      </p>
      <Button unstyled
        onClick={() => window.location.reload()}
        className="text-sm font-medium text-marketing-accent underline"
      >
        Reload
      </Button>
    </div>
  );
}

export const AppErrorBoundary: React.FC<Props> = ({
  children,
  componentName,
  fallback,
}) => {
  return (
    <ErrorBoundary
      fallback={fallback ?? <DefaultFallback />}
      onError={(error: unknown) => {
        const err = error instanceof Error ? error : new Error(String(error));
        reportError({
          message:       err.message,
          stack:         err.stack ?? null,
          componentName: componentName ?? null,
        });
      }}
    >
      {children}
    </ErrorBoundary>
  );
};
