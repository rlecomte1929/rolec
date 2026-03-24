import React from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../../../components/antigravity';
import type { AdminPoliciesByCompany, AdminPolicySummary, AdminPolicyTemplate } from '../../../types';
import { buildRoute } from '../../../navigation/routes';
import { PolicyWorkspaceStructuredHistoryDetails } from './PolicyWorkspaceStructuredHistoryDetails';

const VERSION_STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  review_required: 'Review required',
  reviewed: 'Reviewed',
  published: 'Published',
  archived: 'Archived',
  auto_generated: 'Auto-generated',
};

const VERSION_STATUS_VARIANTS: Record<string, 'neutral' | 'success' | 'warning'> = {
  draft: 'neutral',
  review_required: 'warning',
  reviewed: 'neutral',
  published: 'success',
  archived: 'neutral',
  auto_generated: 'neutral',
};

function formatDate(val: string | null | undefined): string {
  if (!val) return '-';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return String(val);
  }
}

type Props = {
  selectedCompanyId: string;
  companyName: string;
  data: AdminPoliciesByCompany | null;
  loading: boolean;
  error: string | null;
  sourceDocCount: number;
  latestSourceDocumentTitle: string | null | undefined;
  /** Structured baseline source mode (manual / extracted / hybrid). */
  sourceModeLabel: string;
  policyConfigHref: string;
  templates: AdminPolicyTemplate[];
  applyingTemplate: boolean;
  onApplyDefaultTemplate: () => void;
  onInspect: (policyId: string) => void;
  onEdit: (policyId: string) => void;
};

export const PolicySourceHistorySection: React.FC<Props> = ({
  selectedCompanyId,
  companyName,
  data,
  loading,
  error,
  sourceDocCount,
  latestSourceDocumentTitle,
  sourceModeLabel,
  policyConfigHref,
  templates,
  applyingTemplate,
  onApplyDefaultTemplate,
  onInspect,
  onEdit,
}) => {
  const policies: AdminPolicySummary[] = data?.policies ?? [];
  const hrHref = `${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(selectedCompanyId)}`;
  const latestTitle =
    (latestSourceDocumentTitle ?? '').trim() ||
    (sourceDocCount > 0 ? '—' : 'None uploaded');

  return (
    <section className="mt-6 space-y-3" aria-labelledby="policy-sources-heading">
      <div>
        <h2 id="policy-sources-heading" className="text-base font-semibold text-[#0b2b43]">
          Policy sources and version history
        </h2>
        <p className="text-xs text-[#64748b] mt-1 max-w-2xl leading-snug">
          Secondary traceability. The structured workspace above is the operational baseline.
        </p>
      </div>

      {selectedCompanyId ? (
        <Card padding="sm" className="border-[#e8ecf1] bg-[#fafbfc]">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs sm:text-sm text-[#475569]">
            <span>
              <span className="text-[#94a3b8]">Source documents</span>{' '}
              <span className="font-medium text-[#0b2b43]">{sourceDocCount}</span>
            </span>
            <span className="min-w-0 max-w-full sm:max-w-md">
              <span className="text-[#94a3b8]">Latest upload</span>{' '}
              <span className="font-medium text-[#0b2b43] truncate inline-block max-w-[16rem] align-bottom" title={latestTitle}>
                {latestTitle}
              </span>
            </span>
            <span>
              <span className="text-[#94a3b8]">Source mode</span>{' '}
              <span className="font-medium text-[#0b2b43]">{sourceModeLabel}</span>
            </span>
          </div>
        </Card>
      ) : null}

      <details className="rounded-lg border border-[#e2e8f0] bg-white">
        <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-[#0b2b43]">
          Default platform template
        </summary>
        <div className="px-3 pb-3 pt-0 border-t border-[#f1f5f9] text-sm text-[#64748b]">
          <p className="text-xs mb-2 pt-2">Apply when the company has no custom policy yet. Does not overwrite existing records.</p>
          {templates.length > 0 ? (
            <div className="space-y-2">
              <ul className="text-xs text-[#374151] list-disc list-inside">
                {templates.map((t) => (
                  <li key={t.id}>
                    <span className="font-medium">{t.template_name}</span> ({t.version})
                    {t.is_default_template ? (
                      <span className="ml-1">
                        <Badge variant="neutral" size="sm">
                          Default
                        </Badge>
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
              {selectedCompanyId ? (
                <Button size="sm" onClick={onApplyDefaultTemplate} disabled={applyingTemplate || loading}>
                  {applyingTemplate ? 'Applying…' : 'Apply to company'}
                </Button>
              ) : null}
            </div>
          ) : (
            <p className="text-xs">No templates configured.</p>
          )}
        </div>
      </details>

      {selectedCompanyId && error ? (
        <Card padding="sm" className="border-red-200 bg-red-50">
          <p className="text-red-700 text-sm">{error}</p>
        </Card>
      ) : null}

      {selectedCompanyId && !error && data ? (
        <Card padding="md" className="border-[#e2e8f0]">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <h3 className="text-sm font-semibold text-[#0b2b43]">{companyName}</h3>
            <Link to={hrHref}>
              <Button size="sm" variant="outline">
                HR policy workspace
              </Button>
            </Link>
          </div>

          <div className="text-xs text-[#64748b] mb-2">Policy records ({policies.length})</div>
          {policies.length === 0 ? (
            <div className="py-6 text-center text-[#64748b] text-sm">
              <p>No policy records.</p>
              <Link to={hrHref}>
                <Button variant="outline" size="sm" className="mt-2">
                  Upload documents
                </Button>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs sm:text-sm">
                <thead>
                  <tr className="border-b border-[#e2e8f0] text-left text-[#64748b]">
                    <th className="py-2 pr-2">Title</th>
                    <th className="py-2 pr-2">Source</th>
                    <th className="py-2 pr-2">Latest ver.</th>
                    <th className="py-2 pr-2">Published</th>
                    <th className="py-2 pr-2">Docs</th>
                    <th className="py-2 pr-2">#</th>
                    <th className="py-2 pr-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((p) => (
                    <tr key={p.policy_id} className="border-b border-[#f1f5f9] hover:bg-[#f8fafc]">
                      <td className="py-2 pr-2 font-medium text-[#0b2b43]">{p.title || '-'}</td>
                      <td className="py-2 pr-2">
                        {(p.template_source ?? 'company_uploaded') === 'default_platform_template' ? (
                          <Badge variant="neutral" size="sm">
                            Template
                          </Badge>
                        ) : (
                          <Badge variant="neutral" size="sm">
                            Upload
                          </Badge>
                        )}
                      </td>
                      <td className="py-2 pr-2">
                        <Badge variant={VERSION_STATUS_VARIANTS[p.latest_version_status ?? ''] || 'neutral'} size="sm">
                          {p.latest_version_number ?? '-'} ·{' '}
                          {VERSION_STATUS_LABELS[p.latest_version_status ?? ''] ?? p.latest_version_status ?? '-'}
                        </Badge>
                      </td>
                      <td className="py-2 pr-2">
                        {p.published_version_id ? (
                          <span className="text-green-700">Yes · {formatDate(p.published_at)}</span>
                        ) : (
                          <span className="text-[#64748b]">No</span>
                        )}
                      </td>
                      <td className="py-2 pr-2">{sourceDocCount}</td>
                      <td className="py-2 pr-2">{p.version_count}</td>
                      <td className="py-2 pr-2">
                        <div className="flex flex-wrap gap-1">
                          <Button size="sm" variant="outline" onClick={() => onInspect(p.policy_id)}>
                            Inspect
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => onEdit(p.policy_id)}>
                            Edit
                          </Button>
                          <Link to={hrHref}>
                            <Button size="sm" variant="outline">
                              Open
                            </Button>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-3">
            <PolicyWorkspaceStructuredHistoryDetails companyId={selectedCompanyId} policyConfigHref={policyConfigHref} />
          </div>
        </Card>
      ) : null}
    </section>
  );
};
