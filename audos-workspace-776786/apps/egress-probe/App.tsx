import { useState, useEffect, useCallback, useRef } from 'react';

const TARGET_URL = 'https://api.relopass.com/api/probe';
const PROBE_TIMEOUT_MS = 10_000;
const MARKER = 'audos-egress-probe-v1';

type FailureBucket =
  | 'TIMEOUT'
  | 'CSP_CONNECT_SRC_BLOCK'
  | 'CORS_BLOCK'
  | 'DNS_OR_NETWORK'
  | 'UNKNOWN';

interface CspViolationCapture {
  violatedDirective: string;
  blockedURI: string;
  effectiveDirective: string;
  originalPolicy: string;
  timestamp: number;
}

interface ProbeSuccess {
  kind: 'success';
  httpStatus: number;
  statusText: string;
  responseOk: boolean;
  rawBody: string;
  markerPass: boolean;
  durationMs: number;
}

interface ProbeFailure {
  kind: 'failure';
  bucket: FailureBucket;
  errorName: string;
  errorMessage: string;
  cspViolation: CspViolationCapture | null;
  errorDump: string;
  durationMs: number;
}

type ProbeResult = ProbeSuccess | ProbeFailure;

const AMBIGUITY_NOTE =
  'Browser fetch cannot fully disambiguate CORS rejection from DNS/network failure; check whether a securitypolicyviolation event fired (shown above) — if it did, the real cause is CSP connect-src, which is the architecture-level block.';

function serializeError(err: unknown): string {
  if (err instanceof Error) {
    const extra: Record<string, unknown> = {};
    for (const key of Object.getOwnPropertyNames(err)) {
      if (key !== 'name' && key !== 'message' && key !== 'stack') {
        extra[key] = (err as unknown as Record<string, unknown>)[key];
      }
    }
    return JSON.stringify(
      {
        name: err.name,
        message: err.message,
        stack: err.stack,
        ...extra,
      },
      null,
      2,
    );
  }
  try {
    return JSON.stringify(err, null, 2);
  } catch {
    return String(err);
  }
}

function isConnectSrcViolation(v: CspViolationCapture): boolean {
  const directive = (v.violatedDirective || v.effectiveDirective || '').toLowerCase();
  return directive.includes('connect-src') || directive.includes('connect');
}

function classifyFailure(
  err: unknown,
  cspViolations: CspViolationCapture[],
  targetUrl: string,
): Omit<ProbeFailure, 'kind' | 'durationMs'> {
  const errorName = err instanceof Error ? err.name : 'UnknownError';
  const errorMessage = err instanceof Error ? err.message : String(err);
  const msgLower = errorMessage.toLowerCase();

  if (err instanceof DOMException && err.name === 'AbortError') {
    return {
      bucket: 'TIMEOUT',
      errorName,
      errorMessage: 'TIMEOUT after 10s',
      cspViolation: null,
      errorDump: serializeError(err),
    };
  }

  if (errorName === 'AbortError' || msgLower.includes('aborted')) {
    return {
      bucket: 'TIMEOUT',
      errorName,
      errorMessage: 'TIMEOUT after 10s',
      cspViolation: null,
      errorDump: serializeError(err),
    };
  }

  const relevantViolation =
    cspViolations.find((v) => {
      if (!isConnectSrcViolation(v)) return false;
      const blocked = v.blockedURI || '';
      if (!blocked || blocked === 'unknown') return true;
      try {
        const blockedOrigin = new URL(blocked).origin;
        const targetOrigin = new URL(targetUrl).origin;
        return blocked === targetUrl || blockedOrigin === targetOrigin || targetUrl.startsWith(blocked);
      } catch {
        return blocked.includes('relopass') || blocked.includes('api.relopass');
      }
    }) ||
    cspViolations.find(isConnectSrcViolation) ||
    cspViolations[0] ||
    null;

  const cspInMessage =
    msgLower.includes('content security policy') ||
    msgLower.includes('csp') ||
    msgLower.includes('connect-src');

  if (relevantViolation || cspInMessage) {
    return {
      bucket: 'CSP_CONNECT_SRC_BLOCK',
      errorName,
      errorMessage,
      cspViolation: relevantViolation,
      errorDump: serializeError(err),
    };
  }

  if (errorName === 'TypeError' && msgLower.includes('failed to fetch')) {
    return {
      bucket: 'CORS_BLOCK',
      errorName,
      errorMessage,
      cspViolation: null,
      errorDump: serializeError(err),
    };
  }

  if (
    msgLower.includes('network') ||
    msgLower.includes('dns') ||
    msgLower.includes('net::') ||
    msgLower.includes('enotfound') ||
    msgLower.includes('could not resolve')
  ) {
    return {
      bucket: 'DNS_OR_NETWORK',
      errorName,
      errorMessage,
      cspViolation: null,
      errorDump: serializeError(err),
    };
  }

  return {
    bucket: 'UNKNOWN',
    errorName,
    errorMessage,
    cspViolation: relevantViolation,
    errorDump: serializeError(err),
  };
}

export default function EgressProbe() {
  const [result, setResult] = useState<ProbeResult | null>(null);
  const [running, setRunning] = useState(false);
  const [runCount, setRunCount] = useState(0);
  const cspViolationsRef = useRef<CspViolationCapture[]>([]);
  const probeActiveRef = useRef(false);

  const pageOrigin = typeof window !== 'undefined' ? window.location.origin : '(unknown)';

  const runProbe = useCallback(async () => {
    setRunning(true);
    setRunCount((c) => c + 1);
    cspViolationsRef.current = [];
    probeActiveRef.current = true;

    const started = performance.now();
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

    console.log('[EgressProbe] Starting probe', {
      origin: pageOrigin,
      target: TARGET_URL,
      timeoutMs: PROBE_TIMEOUT_MS,
    });

    try {
      const response = await fetch(TARGET_URL, {
        method: 'GET',
        signal: controller.signal,
        mode: 'cors',
        credentials: 'omit',
        cache: 'no-store',
      });

      window.clearTimeout(timeoutId);
      const rawBody = await response.text();
      const durationMs = Math.round(performance.now() - started);

      console.log('[EgressProbe] Probe succeeded', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        bodyLength: rawBody.length,
        durationMs,
      });

      setResult({
        kind: 'success',
        httpStatus: response.status,
        statusText: response.statusText,
        responseOk: response.ok,
        rawBody,
        markerPass: rawBody.includes(MARKER),
        durationMs,
      });
    } catch (err) {
      window.clearTimeout(timeoutId);
      // securitypolicyviolation may fire slightly after fetch rejection
      await new Promise((resolve) => setTimeout(resolve, 100));
      const durationMs = Math.round(performance.now() - started);
      const classified = classifyFailure(err, cspViolationsRef.current, TARGET_URL);

      console.error('[EgressProbe] Probe failed', {
        bucket: classified.bucket,
        errorName: classified.errorName,
        errorMessage: classified.errorMessage,
        cspViolations: cspViolationsRef.current,
        durationMs,
        err,
      });

      setResult({ kind: 'failure', ...classified, durationMs });
    } finally {
      probeActiveRef.current = false;
      setRunning(false);
    }
  }, [pageOrigin]);

  useEffect(() => {
    const onCspViolation = (event: SecurityPolicyViolationEvent) => {
      const capture: CspViolationCapture = {
        violatedDirective: event.violatedDirective,
        blockedURI: event.blockedURI,
        effectiveDirective: event.effectiveDirective,
        originalPolicy: event.originalPolicy,
        timestamp: Date.now(),
      };

      cspViolationsRef.current.push(capture);
      console.warn('[EgressProbe] securitypolicyviolation', capture);
    };

    document.addEventListener('securitypolicyviolation', onCspViolation);
    return () => document.removeEventListener('securitypolicyviolation', onCspViolation);
  }, []);

  useEffect(() => {
    runProbe();
  }, [runProbe]);

  return (
    <div
      style={{
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace',
        fontSize: '13px',
        lineHeight: 1.5,
        padding: '20px',
        color: '#0f172a',
        background: '#f8fafc',
        minHeight: '100%',
      }}
    >
      <h1 style={{ fontSize: '18px', fontWeight: 700, margin: '0 0 4px', fontFamily: 'system-ui, sans-serif' }}>
        Egress Probe
      </h1>
      <p style={{ margin: '0 0 16px', fontFamily: 'system-ui, sans-serif', color: '#475569', fontSize: '12px' }}>
        Sandbox egress diagnostic — browser fetch to api.relopass.com from Audos sandbox
      </p>

      <section style={{ marginBottom: '16px', padding: '12px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
        <div><strong>Page origin:</strong> {pageOrigin}</div>
        <div><strong>Target URL:</strong> {TARGET_URL}</div>
        <div><strong>Cross-origin:</strong> {pageOrigin !== new URL(TARGET_URL).origin ? 'yes' : 'no'}</div>
      </section>

      <button
        type="button"
        onClick={runProbe}
        disabled={running}
        style={{
          fontFamily: 'system-ui, sans-serif',
          fontSize: '13px',
          fontWeight: 600,
          padding: '8px 16px',
          marginBottom: '16px',
          cursor: running ? 'wait' : 'pointer',
          background: running ? '#94a3b8' : '#0ea5e9',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
        }}
      >
        {running ? 'Running probe…' : 'Run probe again'}
      </button>

      <section style={{ marginBottom: '12px', color: '#64748b', fontSize: '12px' }}>
        Run #{runCount} · Timeout: {PROBE_TIMEOUT_MS / 1000}s · Marker: {MARKER}
      </section>

      {running && !result && (
        <section style={{ padding: '12px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
          Fetch in progress…
        </section>
      )}

      {result?.kind === 'success' && (
        <section style={{ padding: '12px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
          <div style={{ fontWeight: 700, color: result.markerPass ? '#15803d' : '#b45309', marginBottom: '12px', fontSize: '15px' }}>
            {result.markerPass ? 'PASS' : 'FAIL'} — marker {result.markerPass ? 'found' : 'NOT found'} in response body
          </div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{`HTTP status: ${result.httpStatus} ${result.statusText}
response.ok: ${String(result.responseOk)}
Duration: ${result.durationMs}ms

--- raw response body ---
${result.rawBody}`}</pre>
        </section>
      )}

      {result?.kind === 'failure' && (
        <section style={{ padding: '12px', background: '#fff', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
          <div style={{ fontWeight: 700, color: '#dc2626', marginBottom: '12px', fontSize: '15px' }}>
            FAILURE — {result.bucket}
          </div>

          <pre style={{ margin: '0 0 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{`error.name: ${result.errorName}
error.message: ${result.errorMessage}
Duration: ${result.durationMs}ms`}</pre>

          {result.cspViolation ? (
            <pre style={{ margin: '0 0 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-all', background: '#fef2f2', padding: '8px', borderRadius: '4px' }}>{`--- securitypolicyviolation ---
violatedDirective: ${result.cspViolation.violatedDirective}
effectiveDirective: ${result.cspViolation.effectiveDirective}
blockedURI: ${result.cspViolation.blockedURI}`}</pre>
          ) : (
            <pre style={{ margin: '0 0 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-all', background: '#f1f5f9', padding: '8px', borderRadius: '4px' }}>{`--- securitypolicyviolation ---
(none captured for this probe)`}</pre>
          )}

          {(result.bucket === 'CORS_BLOCK' || result.bucket === 'DNS_OR_NETWORK') && (
            <p style={{ fontFamily: 'system-ui, sans-serif', fontSize: '12px', color: '#475569', margin: '0 0 12px', padding: '8px', background: '#fffbeb', borderRadius: '4px', border: '1px solid #fde68a' }}>
              {result.bucket === 'CORS_BLOCK' && (
                <>
                  Note: Founder has confirmed open CORS server-side; a CORS_BLOCK here is likely a false negative / preflight misconfig, NOT an architecture-level egress block.
                  <br />
                  <br />
                </>
              )}
              {AMBIGUITY_NOTE}
            </p>
          )}

          {result.bucket === 'CSP_CONNECT_SRC_BLOCK' && (
            <p style={{ fontFamily: 'system-ui, sans-serif', fontSize: '12px', color: '#475569', margin: '0 0 12px', padding: '8px', background: '#fef2f2', borderRadius: '4px', border: '1px solid #fecaca' }}>
              CSP connect-src block is the TRUE sandbox egress block signal for a hosted Audos app.
            </p>
          )}

          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{`--- full error dump ---
${result.errorDump}`}</pre>
        </section>
      )}
    </div>
  );
}
