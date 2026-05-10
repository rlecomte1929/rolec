import React, { useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Card, Button } from '../../components/antigravity';
import { adminAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';

type Candidate = {
  id: string;
  destination_country: string;
  url: string;
  title?: string;
  snippet?: string;
  publisher_domain?: string;
  status: string;
  created_at?: string;
};

type KnowledgeDoc = {
  id: string;
  title: string;
  publisher?: string;
  source_url: string;
  fetch_status?: string;
  last_verified_at?: string;
  fetched_at?: string;
  content_length?: number;
  excerpt_preview?: string;
  content_excerpt?: string;
};

type RequirementEntity = {
  id: string;
  destination_country: string;
  domain_area: string;
  topic_key: string;
  title: string;
  status: string;
};

type RequirementFact = {
  id: string;
  fact_type: string;
  fact_text: string;
  evidence_quote?: string | null;
  source_url: string;
  status: string;
};

const CORE_URL_SETS: Record<string, Array<{ url: string; domain_area: string }>> = {
  US: [
    { url: 'https://www.uscis.gov/working-in-the-united-states', domain_area: 'immigration' },
    { url: 'https://travel.state.gov/content/travel/en/us-visas.html', domain_area: 'immigration' },
    { url: 'https://www.cbp.gov/travel/international-visitors/i-94', domain_area: 'registration' },
    { url: 'https://www.ssa.gov/ssnumber/', domain_area: 'registration' },
  ],
  SG: [
    { url: 'https://www.mom.gov.sg/passes-and-permits', domain_area: 'immigration' },
    { url: 'https://www.ica.gov.sg/enter-transit-depart', domain_area: 'registration' },
  ],
};

export const AdminResearch: React.FC = () => {
  const role = getAuthItem('relopass_role');
  const [destination, setDestination] = useState('US');
  const [domainArea, setDomainArea] = useState('immigration');
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [manualUrl, setManualUrl] = useState('');
  const [batchUrls, setBatchUrls] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [health, setHealth] = useState<any>(null);
  const [ingestResults, setIngestResults] = useState<any>(null);
  const [activeDoc, setActiveDoc] = useState<KnowledgeDoc | null>(null);
  const [entities, setEntities] = useState<RequirementEntity[]>([]);
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);
  const [facts, setFacts] = useState<RequirementFact[]>([]);
  const [criteriaFacts, setCriteriaFacts] = useState<RequirementFact[]>([]);

  const refresh = async () => {
    if (role !== 'ADMIN') return;
    const [candRes, docRes] = await Promise.all([
      adminAPI.listResearchCandidates({ destination_country: destination, status: 'pending' }),
      adminAPI.listKnowledgeDocs({ destination_country: destination }),
    ]);
    setCandidates(candRes.candidates || []);
    setDocs(docRes.docs || []);
    if (docRes.fallback) {
      setMessage('No destination-specific docs found. Showing all knowledge docs.');
    }
    const entRes = await adminAPI.listRequirementEntities({ destination, status: 'pending' });
    setEntities(entRes.entities || []);
    const critRes = await adminAPI.listRequirementCriteria({ destination, status: 'pending' });
    setCriteriaFacts(critRes.facts || []);
    const healthRes = await adminAPI.researchHealth({ destination });
    setHealth(healthRes);
  };
  useEffect(() => {
    if (!activeEntityId) {
      setFacts([]);
      return;
    }
    adminAPI.listRequirementFacts(activeEntityId, { status: 'pending' })
      .then((res) => setFacts(res.facts || []))
      .catch(() => setFacts([]));
  }, [activeEntityId]);

  useEffect(() => {
    refresh().catch(() => undefined);
  }, [destination]);

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Official Source Ingest" subtitle="Restricted">
        <Card padding="lg">You do not have access to the Admin Console.</Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Official Source Ingest" subtitle="Approve official sources for guidance packs">
      <Card padding="lg">
        <div className="flex items-center gap-3">
          <label className="text-sm text-[#6b7280]">Destination</label>
          <select
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            className="border border-[#e2e8f0] rounded-md px-2 py-1 text-sm"
          >
            <option value="US">US</option>
            <option value="SG">SG</option>
          </select>
          <Button
            variant="outline"
            onClick={() => refresh()}
          >
            Refresh
          </Button>
        </div>
        {message && <div className="mt-2 text-sm text-[#0b2b43]">{message}</div>}
        {health && (
          <div className="mt-3 text-xs text-[#6b7280] flex flex-wrap gap-3">
            <span>DB: {health.db_provider}</span>
            <span>Knowledge docs: {health.knowledge_docs}</span>
            <span>Knowledge rules: {health.knowledge_rules}</span>
            <span>Knowledge packs: {health.knowledge_packs}</span>
            <span>Ingest jobs (24h): {health.ingest_jobs_24h}</span>
            {health.last_job && (
              <span>Last job: {health.last_job.status}{health.last_job.error ? ` (${health.last_job.error})` : ''}</span>
            )}
          </div>
        )}
      </Card>

      <Card padding="lg" className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Pending official sources</div>
        {candidates.length === 0 && (
          <div className="text-sm text-[#6b7280]">No pending candidates.</div>
        )}
        <div className="space-y-3">
          {candidates.map((c) => (
            <div key={c.id} className="border border-[#e2e8f0] rounded-lg p-3">
              <div className="font-semibold text-[#0b2b43]">{c.title || c.url}</div>
              <div className="text-xs text-[#6b7280]">{c.publisher_domain}</div>
              {c.snippet && <div className="text-xs text-[#6b7280] mt-1">{c.snippet}</div>}
              <div className="flex items-center gap-2 mt-2">
                <select
                  value={domainArea}
                  onChange={(e) => setDomainArea(e.target.value)}
                  className="border border-[#e2e8f0] rounded-md px-2 py-1 text-xs"
                >
                  <option value="immigration">Immigration</option>
                  <option value="registration">Registration</option>
                  <option value="tax">Tax</option>
                  <option value="other">Other</option>
                </select>
                <Button
                  onClick={async () => {
                    setLoading(true);
                    setMessage('');
                    try {
                      const res = await adminAPI.approveResearchCandidate(c.id, { domain_area: domainArea });
                      setMessage(`Approved and ingested: ${res.fetch_status}`);
                      await refresh();
                    } finally {
                      setLoading(false);
                    }
                  }}
                  disabled={loading}
                >
                  Approve & ingest
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card padding="lg" className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Manual ingest</div>
        <div className="text-xs text-[#6b7280] mb-2">Ingest batch: ingest the URLs you paste below (one per line).</div>
        <div className="text-xs text-[#6b7280] mb-2">Ingest core set: ingest a predefined official starter set for the selected destination.</div>
        <div className="flex items-center gap-2">
          <input
            className="flex-1 border border-[#e2e8f0] rounded-md px-3 py-2 text-sm"
            placeholder="https://www.uscis.gov/..."
            value={manualUrl}
            onChange={(e) => setManualUrl(e.target.value)}
          />
          <select
            value={domainArea}
            onChange={(e) => setDomainArea(e.target.value)}
            className="border border-[#e2e8f0] rounded-md px-2 py-1 text-xs"
          >
            <option value="immigration">Immigration</option>
            <option value="registration">Registration</option>
            <option value="tax">Tax</option>
            <option value="other">Other</option>
          </select>
          <Button
            onClick={async () => {
              if (!manualUrl) return;
              setLoading(true);
              setMessage('');
              setIngestResults(null);
              try {
                const res = await adminAPI.ingestUrl({ url: manualUrl, destination_country: destination, domain_area: domainArea });
                setMessage(`Ingested ${res.succeeded}/${res.attempted} URL(s).`);
                setIngestResults(res);
                setManualUrl('');
                await refresh();
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
          >
            Ingest URL
          </Button>
        </div>
        <div className="mt-4">
          <div className="text-xs text-[#6b7280] mb-2">Batch URLs (one per line)</div>
          <textarea
            className="w-full border border-[#e2e8f0] rounded-md px-3 py-2 text-sm h-28"
            placeholder="https://travel.state.gov/...
https://www.uscis.gov/..."
            value={batchUrls}
            onChange={(e) => setBatchUrls(e.target.value)}
          />
          <div className="flex items-center gap-2 mt-2">
            <Button
              onClick={async () => {
                const urls = batchUrls.split('\n').map((u) => u.trim()).filter(Boolean);
                if (!urls.length) return;
                setLoading(true);
                setMessage('');
                setIngestResults(null);
                try {
                  const res = await adminAPI.ingestBatch({ urls, destination_country: destination, domain_area: domainArea });
                  setMessage(`Batch ingested ${res.succeeded}/${res.attempted} URL(s).`);
                  setIngestResults(res);
                  setBatchUrls('');
                  await refresh();
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
            >
              Ingest batch
            </Button>
          </div>
        </div>
        <div className="mt-3">
          <Button
            variant="outline"
            onClick={async () => {
              setLoading(true);
              setMessage('');
              setIngestResults(null);
              try {
                const items = CORE_URL_SETS[destination] || [];
                const res = await adminAPI.ingestBatch({
                  urls: items,
                  destination_country: destination,
                });
                setMessage(`Core set ingested for ${destination}: ${res.succeeded}/${res.attempted}.`);
                setIngestResults(res);
                await refresh();
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
          >
            Ingest core set
          </Button>
          {ingestResults?.results?.some((r: any) => r.status !== 'fetched') && (
            <Button
              variant="outline"
              onClick={async () => {
                const failed = ingestResults.results.filter((r: any) => r.status !== 'fetched').map((r: any) => r.url);
                if (!failed.length) return;
                setLoading(true);
                setMessage('');
                try {
                  const res = await adminAPI.ingestBatch({
                    urls: failed,
                    destination_country: destination,
                    domain_area: domainArea,
                  });
                  setMessage(`Retry completed: ${res.succeeded}/${res.attempted}.`);
                  setIngestResults(res);
                  await refresh();
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
            >
              Retry failed
            </Button>
          )}
        </div>
        {ingestResults?.results?.length ? (
          <div className="mt-3 text-xs text-[#6b7280]">
            {ingestResults.results.map((r: any, idx: number) => (
              <div key={`${r.url}-${idx}`}>
                {r.status === 'fetched' ? '✅' : '⚠️'} {r.url}
                {typeof r.facts_created === 'number' ? ` · facts: ${r.facts_created}` : ''}
                {r.error ? ` · ${r.error}` : ''}
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      <Card padding="lg" className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Knowledge docs (curated)</div>
        {docs.length === 0 && (
          <div className="text-sm text-[#6b7280]">No knowledge docs for this destination.</div>
        )}
        <div className="space-y-3">
          {docs.map((d) => (
            <div key={d.id} className="border border-[#e2e8f0] rounded-lg p-3">
              <div className="font-semibold text-[#0b2b43]">{d.title}</div>
              <div className="text-xs text-[#6b7280]">{d.publisher}</div>
              <div className="text-xs text-[#6b7280] mt-1">{d.fetch_status}</div>
              {d.excerpt_preview && (
                <div className="text-xs text-[#6b7280] mt-2">{d.excerpt_preview}...</div>
              )}
              <a className="text-xs text-[#1d4ed8] underline mt-2 inline-block" href={d.source_url} target="_blank" rel="noreferrer">
                {d.source_url}
              </a>
              <div className="mt-2">
                <Button variant="outline" onClick={() => setActiveDoc(d)}>View full excerpt</Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card padding="lg" className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Pending extracted requirements</div>
        {entities.length === 0 && (
          <div className="text-sm text-[#6b7280]">No pending requirement entities.</div>
        )}
        <div className="flex gap-4">
          <div className="w-1/3 space-y-2">
            {entities.map((e) => (
              <button
                key={e.id}
                className={`w-full text-left border rounded-lg p-2 ${activeEntityId === e.id ? 'border-[#0b2b43] bg-[#eef4f8]' : 'border-[#e2e8f0]'}`}
                onClick={() => setActiveEntityId(e.id)}
              >
                <div className="text-sm font-semibold text-[#0b2b43]">{e.title}</div>
                <div className="text-xs text-[#6b7280]">{e.domain_area} · {e.topic_key}</div>
              </button>
            ))}
          </div>
          <div className="flex-1">
            {facts.length === 0 && (
              <div className="text-sm text-[#6b7280]">Select an entity to review pending facts.</div>
            )}
            {facts.map((f) => (
              <div key={f.id} className="border border-[#e2e8f0] rounded-lg p-3 mb-2">
                <div className="text-sm font-semibold text-[#0b2b43]">{f.fact_type}</div>
                <div className="text-xs text-[#6b7280]">{f.fact_text}</div>
                {f.evidence_quote && <div className="text-xs text-[#6b7280] mt-1">“{f.evidence_quote}”</div>}
                <a className="text-xs text-[#1d4ed8] underline mt-2 inline-block" href={f.source_url} target="_blank" rel="noreferrer">
                  {f.source_url}
                </a>
                <div className="mt-2 flex gap-2">
                  <Button
                    variant="outline"
                    onClick={async () => {
                      await adminAPI.approveRequirementFacts({ fact_ids: [f.id] });
                      setFacts(facts.filter((x) => x.id !== f.id));
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    variant="outline"
                    onClick={async () => {
                      await adminAPI.rejectRequirementFacts({ fact_ids: [f.id] });
                      setFacts(facts.filter((x) => x.id !== f.id));
                    }}
                  >
                    Reject
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card padding="lg" className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Extracted criteria (pending)</div>
        {criteriaFacts.length === 0 && (
          <div className="text-sm text-[#6b7280]">No extracted criteria yet.</div>
        )}
        <div className="space-y-2">
          {criteriaFacts.map((f) => (
            <div key={f.id} className="border border-[#e2e8f0] rounded-lg p-3">
              <div className="text-sm text-[#0b2b43]">{f.fact_text}</div>
              <a className="text-xs text-[#1d4ed8] underline mt-1 inline-block" href={f.source_url} target="_blank" rel="noreferrer">
                {f.source_url}
              </a>
              <div className="mt-2 flex gap-2">
                <Button
                  variant="outline"
                  onClick={async () => {
                    await adminAPI.approveRequirementFacts({ fact_ids: [f.id] });
                    setCriteriaFacts(criteriaFacts.filter((x) => x.id !== f.id));
                  }}
                >
                  Approve
                </Button>
                <Button
                  variant="outline"
                  onClick={async () => {
                    await adminAPI.rejectRequirementFacts({ fact_ids: [f.id] });
                    setCriteriaFacts(criteriaFacts.filter((x) => x.id !== f.id));
                  }}
                >
                  Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
      {activeDoc && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-4 w-[720px] max-w-[95%]">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">{activeDoc.title}</div>
            <div className="text-xs text-[#6b7280] mb-2">{activeDoc.source_url}</div>
            <div className="text-xs text-[#6b7280] mb-2">Status: {activeDoc.fetch_status} · Fetched: {activeDoc.fetched_at || '-'}</div>
            <pre className="text-xs whitespace-pre-wrap border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc] max-h-[320px] overflow-auto">
              {activeDoc.content_excerpt || 'No excerpt available.'}
            </pre>
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={() => navigator.clipboard?.writeText(activeDoc.content_excerpt || '')}>Copy excerpt</Button>
              <Button onClick={() => setActiveDoc(null)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};
