import React, { useEffect, useMemo, useState } from 'react';
import { Button, Card } from '../antigravity';
import { guidanceAPI } from '../../api/client';
import { useAdminContext } from '../../features/admin/useAdminContext';

const GUIDANCE_ENABLED =
  import.meta.env.NEXT_PUBLIC_FEATURE_GUIDANCE_PACK === 'true' ||
  import.meta.env.VITE_FEATURE_GUIDANCE_PACK === 'true';

type GuidancePack = {
  guidance_mode?: 'demo' | 'strict';
  pack_hash?: string;
  rule_set?: Array<{
    rule_id: string;
    rule_key: string;
    version: number;
    pack_id: string;
    pack_version: number;
    is_baseline: boolean;
    injected_for_minimum: boolean;
  }>;
  plan: {
    items: Array<{
      phase: string;
      category: string;
      title: string;
      description_md: string;
      citations: string[];
      rule?: {
        rule_id: string;
        rule_key: string;
        version: number;
        pack_id: string;
        pack_version: number;
        is_baseline: boolean;
        injected_for_minimum: boolean;
      };
    }>;
  };
  checklist: {
    items: Array<{
      phase: string;
      title: string;
      description: string;
      due_date?: string | null;
      relative_to_move?: string | null;
      citations: string[];
      rule?: {
        rule_id: string;
        rule_key: string;
        version: number;
        pack_id: string;
        pack_version: number;
        is_baseline: boolean;
        injected_for_minimum: boolean;
      };
    }>;
  };
  markdown: string;
  sources: Array<{ doc_id: string; title?: string; url: string; publisher?: string }>;
  not_covered: string[];
  coverage?: {
    score?: number;
    domains_covered?: string[];
    missing_info?: string[];
    not_covered?: string[];
    guidance_mode?: 'demo' | 'strict';
    baseline_injected_count?: number;
    matched_rules_count?: number;
  };
};

export const GuidancePackPanel: React.FC<{ caseId: string; isStep5Complete: boolean }> = ({ caseId, isStep5Complete }) => {
  const [loading, setLoading] = useState(false);
  const [pack, setPack] = useState<GuidancePack | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'plan' | 'checklist' | 'sources' | 'guide' | 'explain'>('plan');
  const [mode, setMode] = useState<'demo' | 'strict'>('demo');
  const [explain, setExplain] = useState<{ trace_id?: string | null; rejected_count?: number; logs: any[] } | null>(null);
  const { context: adminContext } = useAdminContext();

  useEffect(() => {
    if (!GUIDANCE_ENABLED || !caseId) return;
    guidanceAPI.getLatest(caseId)
      .then((res) => setPack(res))
      .catch(() => undefined);
  }, [caseId]);

  useEffect(() => {
    if (!GUIDANCE_ENABLED || !caseId || tab !== 'explain') return;
    guidanceAPI.explain(caseId)
      .then((res) => setExplain(res))
      .catch(() => undefined);
  }, [caseId, tab]);

  if (!GUIDANCE_ENABLED) return null;

  const missingInfoLabels: Record<string, string> = {
    origin_country: 'Origin country',
    destination_country: 'Destination country',
    'origin_country or destination_country': 'Origin and destination countries',
    move_date: 'Target move date',
    employment_type: 'Employment type',
    visa_type: 'Visa or pass type',
  };

  const formatMissingInfo = (items?: string[]) => {
    if (!items || items.length === 0) return '';
    return items
      .map((item) => missingInfoLabels[item] || item.replace(/_/g, ' '))
      .join(', ');
  };

  const generate = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await guidanceAPI.generate(caseId, adminContext?.isAdmin ? mode : undefined);
      setPack(res);
      setGeneratedAt(new Date().toLocaleString());
      setTab('plan');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Unable to generate guidance pack.');
    } finally {
      setLoading(false);
    }
  };

  const sourceMap = useMemo(() => {
    const map = new Map<string, { title?: string; url: string; publisher?: string }>();
    (pack?.sources || []).forEach((s) => map.set(s.doc_id, s));
    return map;
  }, [pack?.sources]);

  return (
    <Card padding="lg">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-[#0b2b43]">Guidance Pack</div>
          <div className="text-sm text-[#6b7280]">Curated plan, checklist and guide with official sources.</div>
        </div>
        <div className="flex items-center gap-2">
          {adminContext?.isAdmin && (
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'demo' | 'strict')}
              className="text-xs border border-[#e2e8f0] rounded-md px-2 py-1 text-[#0b2b43] bg-white"
              disabled={loading}
            >
              <option value="demo">Demo mode</option>
              <option value="strict">Strict mode</option>
            </select>
          )}
          {pack && (
            <Button
              variant="outline"
              onClick={() => {
                if (window.confirm('Regenerate the guidance pack? This will overwrite the latest guidance.')) {
                  generate();
                }
              }}
              disabled={!isStep5Complete || loading}
            >
              Regenerate
            </Button>
          )}
          <Button onClick={generate} disabled={!isStep5Complete || loading}>
            {loading ? 'Generating...' : 'Generate Guidance Pack'}
          </Button>
        </div>
      </div>
      {!isStep5Complete && (
        <div className="mt-2 text-xs text-[#6b7280]">Complete Step 5 to enable guidance pack generation.</div>
      )}
      {error && <div className="mt-3 text-sm text-[#7a2a2a]">{error}</div>}

      {pack && (
        <div className="mt-4">
          <div className="flex items-center gap-3 text-xs text-[#6b7280] mb-3">
            {generatedAt && <span>Generated at: {generatedAt}</span>}
            {pack.guidance_mode && <span>Mode: {pack.guidance_mode}</span>}
            {pack.pack_hash && (
              <span>
                Pack hash: {pack.pack_hash.slice(0, 8)}...
                <button
                  className="text-[#1d4ed8] underline ml-1"
                  onClick={() => navigator.clipboard?.writeText(pack.pack_hash || '')}
                >
                  Copy
                </button>
              </span>
            )}
            {typeof pack.coverage?.score === 'number' && (
              <span className={`px-2 py-0.5 rounded-full border ${pack.coverage.score >= 70 ? 'border-[#10b981] text-[#10b981]' : pack.coverage.score >= 40 ? 'border-[#f59e0b] text-[#f59e0b]' : 'border-[#ef4444] text-[#ef4444]'}`}>
                Coverage {pack.coverage.score}/100
              </span>
            )}
            {pack.coverage?.domains_covered?.length ? (
              <span>Domains: {pack.coverage.domains_covered.join(', ')}</span>
            ) : null}
            {pack.coverage?.baseline_injected_count ? (
              <span className="px-2 py-0.5 rounded-full border border-[#f59e0b] text-[#b45309]">Baseline injected</span>
            ) : null}
          </div>

          {pack.coverage?.missing_info?.length ? (
            <div className="mb-3 text-xs text-[#7a2a2a] border border-[#fecaca] bg-[#fff5f5] rounded-lg p-2">
              Missing information to personalize your guidance: {formatMissingInfo(pack.coverage.missing_info)}
            </div>
          ) : null}

          {pack.coverage?.not_covered?.length ? (
            <div className="mb-3 text-xs text-[#7a5e2a] border border-[#fde68a] bg-[#fffbeb] rounded-lg p-2">
              We could not generate some items because: {pack.coverage.not_covered.join(' · ')}
            </div>
          ) : null}

          <div className="flex items-center gap-2 text-sm mb-3">
            {(['plan', 'checklist', 'sources', 'guide', 'explain'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1 rounded-full border ${tab === t ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]' : 'border-transparent text-[#6b7280]'}`}
              >
                {t === 'plan' ? 'Plan' : t === 'checklist' ? 'Checklist' : t === 'sources' ? 'Sources' : t === 'guide' ? 'Full Guide' : 'Explain'}
              </button>
            ))}
          </div>

          {tab === 'plan' && (
            <div className="space-y-3">
              {pack.plan.items.length === 0 && (
                <div className="text-sm text-[#6b7280]">
                  Add the missing information above, then try again.
                </div>
              )}
              {pack.plan.items.map((item, idx) => (
                <div key={`${item.title}-${idx}`} className="rounded-lg border border-[#e2e8f0] p-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                  <div className="text-xs text-[#6b7280]">{item.phase} · {item.category}</div>
                  <div className="text-sm text-[#4b5563] mt-2">{item.description_md}</div>
                  <div className="text-xs text-[#6b7280] mt-1">Citations: {item.citations?.length || 0}</div>
                  {item.rule && (
                    <details className="mt-2">
                      <summary className="text-xs text-[#1d4ed8] cursor-pointer">Why this action?</summary>
                      <div className="mt-2 text-xs text-[#4b5563] space-y-1">
                        <div>Rule: {item.rule.rule_key} (v{item.rule.version})</div>
                        <div>Pack version: {item.rule.pack_version}</div>
                        <div>Baseline: {item.rule.is_baseline ? 'Yes' : 'No'}</div>
                        <div>Injected for minimum: {item.rule.injected_for_minimum ? 'Yes' : 'No'}</div>
                        {item.citations?.length ? (
                          <div>
                            Sources:{' '}
                            {item.citations
                              .map((c) => sourceMap.get(c))
                              .filter(Boolean)
                              .map((s, i) => (
                                <a key={`${s?.url}-${i}`} className="text-[#1d4ed8] underline mr-2" href={s?.url} target="_blank" rel="noreferrer">
                                  {s?.title || s?.url}
                                </a>
                              ))}
                          </div>
                        ) : null}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'checklist' && (
            <div className="space-y-3">
              {pack.checklist.items.length === 0 && (
                <div className="text-sm text-[#6b7280]">No checklist items available.</div>
              )}
              {pack.checklist.items.map((item, idx) => (
                <div key={`${item.title}-${idx}`} className="rounded-lg border border-[#e2e8f0] p-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                  <div className="text-xs text-[#6b7280]">{item.phase} · {item.due_date || item.relative_to_move}</div>
                  <div className="text-sm text-[#4b5563] mt-2">{item.description}</div>
                  <div className="text-xs text-[#6b7280] mt-1">Citations: {item.citations?.length || 0}</div>
                  {item.rule && (
                    <details className="mt-2">
                      <summary className="text-xs text-[#1d4ed8] cursor-pointer">Why this action?</summary>
                      <div className="mt-2 text-xs text-[#4b5563] space-y-1">
                        <div>Rule: {item.rule.rule_key} (v{item.rule.version})</div>
                        <div>Pack version: {item.rule.pack_version}</div>
                        <div>Baseline: {item.rule.is_baseline ? 'Yes' : 'No'}</div>
                        <div>Injected for minimum: {item.rule.injected_for_minimum ? 'Yes' : 'No'}</div>
                        {item.citations?.length ? (
                          <div>
                            Sources:{' '}
                            {item.citations
                              .map((c) => sourceMap.get(c))
                              .filter(Boolean)
                              .map((s, i) => (
                                <a key={`${s?.url}-${i}`} className="text-[#1d4ed8] underline mr-2" href={s?.url} target="_blank" rel="noreferrer">
                                  {s?.title || s?.url}
                                </a>
                              ))}
                          </div>
                        ) : null}
                      </div>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}

          {tab === 'sources' && (
            <div className="space-y-2">
              {pack.sources.length === 0 && (
                <div className="text-sm text-[#6b7280]">No sources available.</div>
              )}
              {pack.sources.map((s) => (
                <div key={s.doc_id} className="text-sm">
                  <a className="text-[#1d4ed8] underline" href={s.url} target="_blank" rel="noreferrer">
                    {s.title || s.url}
                  </a>
                  {s.publisher && <span className="text-xs text-[#6b7280]"> · {s.publisher}</span>}
                </div>
              ))}
            </div>
          )}

          {tab === 'guide' && (
            <pre className="whitespace-pre-wrap text-sm text-[#4b5563] border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
              {pack.markdown}
            </pre>
          )}

          {tab === 'explain' && (
            <div className="space-y-2 text-sm text-[#4b5563]">
              {typeof explain?.rejected_count === 'number' && (
                <div className="text-xs text-[#6b7280]">Rejected rules: {explain.rejected_count}</div>
              )}
              {!explain?.logs?.length && (
                <div className="text-sm text-[#6b7280]">No explainability data available.</div>
              )}
              {explain?.logs?.map((log, idx) => (
                <div key={`${log.rule_key}-${idx}`} className="rounded-lg border border-[#e2e8f0] p-3">
                  <div className="font-semibold text-[#0b2b43]">{log.rule_key} (v{log.version})</div>
                  <div className="text-xs text-[#6b7280]">
                    Match: {log.evaluation_result ? 'Yes' : 'No'} · Baseline: {log.was_baseline ? 'Yes' : 'No'} · Injected: {log.injected_for_minimum ? 'Yes' : 'No'}
                  </div>
                  {log.snapshot_subset && Object.keys(log.snapshot_subset).length > 0 && (
                    <div className="text-xs text-[#6b7280] mt-1">
                      Snapshot fields: {Object.entries(log.snapshot_subset).map(([k, v]) => `${k}: ${v ?? 'unknown'}`).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
