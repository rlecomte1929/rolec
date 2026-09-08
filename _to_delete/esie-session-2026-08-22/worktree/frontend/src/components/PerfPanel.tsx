import React, { useEffect, useState } from 'react';
import { getRecentInteractions, subscribePerf } from '../perf/perf';

const isPerfEnabled = import.meta.env.VITE_PERF_DEBUG === '1';

export const PerfPanel: React.FC = () => {
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!isPerfEnabled) return;
    const unsub = subscribePerf(() => {
      setVersion((v) => v + 1);
    });
    return () => {
      unsub();
    };
  }, []);

  if (!isPerfEnabled) return null;

  const interactions = getRecentInteractions(10);

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 8,
        right: 8,
        maxWidth: 320,
        zIndex: 9999,
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        fontSize: 11,
        background: 'rgba(15,23,42,0.92)',
        color: '#e5e7eb',
        borderRadius: 8,
        padding: '8px 10px',
        boxShadow: '0 10px 25px rgba(15,23,42,0.55)',
        pointerEvents: 'none',
      }}
      aria-label="Performance debug panel"
      data-version={version}
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Perf Interactions</div>
      {interactions.length === 0 ? (
        <div style={{ opacity: 0.7 }}>No interactions recorded yet.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {interactions.map((it) => (
            <div
              key={it.id}
              style={{
                borderRadius: 4,
                background: 'rgba(31,41,55,0.9)',
                padding: '4px 6px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ fontWeight: 500 }}>{it.name}</span>
                <span>{it.clickToRenderMs.toFixed(1)} ms</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', opacity: 0.75 }}>
                <span>id={it.id.slice(0, 8)}</span>
                <span>requests={it.requestCount}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

