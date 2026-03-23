/**
 * HR-facing policy lifecycle labels from normalized policy + version rows (no raw backend codes in UI).
 */
import type { HrPolicyWorkspaceResolved } from './hrPolicyWorkspaceState';

export type HrPolicyLifecycleContext = {
  /** Shown near top — employees vs drafts */
  employeeVisibilityLines: string[];
  /** What drives employee-facing resolution today */
  activeSource: {
    title: string;
    subtitle: string;
    badge: string;
  };
  /** When a newer draft exists while something is still published */
  draftReplacement: null | {
    title: string;
    body: string;
    versionLabel: string | null;
  };
  /** Shown when published template — encourage upload without blocking */
  templateUploadHint: string | null;
  /** Generic note when multiple versions may exist */
  versionHistoryHint: string;
};

function norm(s: unknown): string {
  return String(s ?? '')
    .trim()
    .toLowerCase();
}

export function isTemplatePolicy(policy: Record<string, unknown> | null | undefined): boolean {
  if (!policy) return false;
  if (policy.template_source === 'default_platform_template') return true;
  const tn = String(policy.template_name || '');
  return tn.startsWith('starter_');
}

function templateTierLabel(policy: Record<string, unknown> | null | undefined): string | null {
  const tn = String(policy?.template_name || '');
  const m = tn.match(/^starter_(conservative|standard|premium)$/);
  if (!m) return null;
  return m[1].charAt(0).toUpperCase() + m[1].slice(1);
}

function versionHasUploadSource(ver: Record<string, unknown> | null | undefined): boolean {
  return Boolean(ver && ver.source_policy_document_id);
}

function isPublishedVersion(ver: Record<string, unknown> | null | undefined): boolean {
  return norm(ver?.status) === 'published';
}

export function deriveHrPolicyLifecycleContext(
  normalized: Record<string, unknown> | null | undefined,
  resolved: HrPolicyWorkspaceResolved
): HrPolicyLifecycleContext {
  const policy = (normalized?.policy || null) as Record<string, unknown> | null;
  const published = (normalized?.published_version || null) as Record<string, unknown> | null;
  const latest = (normalized?.version || null) as Record<string, unknown> | null;

  const employeeVisibilityLines = [
    'Employees only see benefit limits and caps from a version you have published. Drafts and new uploads stay in HR view until you publish.',
    'When you publish a new version, it replaces what employees see on their assignments (within eligibility rules). Until then, the current live version stays in effect.',
  ];

  const versionHistoryHint =
    'Older versions may be archived when you publish a replacement. The live policy for employees is always the latest published version; drafts and older published rows stay in the background until you act.';

  let activeSource: HrPolicyLifecycleContext['activeSource'];
  if (resolved.phase === 'no_policy') {
    activeSource = {
      title: 'No active policy yet',
      subtitle:
        'Start from a standard baseline or upload your company policy. Employees have nothing to view until you publish a version.',
      badge: 'Setup required',
    };
  } else {
    activeSource = {
      title: 'Active source',
      subtitle: 'No published version is selected for employees yet.',
      badge: 'No live version',
    };
  }

  const hasPublishedRow = published && isPublishedVersion(published);
  const policyTemplate = isTemplatePolicy(policy);

  if (resolved.phase !== 'no_policy' && hasPublishedRow) {
    const pubUploaded = versionHasUploadSource(published);
    const tier = templateTierLabel(policy);
    if (pubUploaded) {
      activeSource = {
        title: 'Active for employees',
        subtitle: `Published company policy from an uploaded document${
          resolved.publishedVersionNumber != null ? ` · version ${resolved.publishedVersionNumber}` : ''
        }.`,
        badge: 'Published · uploaded policy',
      };
    } else if (policyTemplate) {
      activeSource = {
        title: 'Active for employees',
        subtitle: `Published ReloPass standard baseline${tier ? ` (${tier})` : ''}${
          resolved.publishedVersionNumber != null ? ` · version ${resolved.publishedVersionNumber}` : ''
        }. You can upload a formal company policy anytime; it becomes a draft until you publish.`,
        badge: 'Published · standard template',
      };
    } else {
      activeSource = {
        title: 'Active for employees',
        subtitle: `Published policy${
          resolved.publishedVersionNumber != null ? ` · version ${resolved.publishedVersionNumber}` : ''
        }.`,
        badge: 'Published',
      };
    }
  } else if (
    resolved.phase !== 'no_policy' &&
    (resolved.phase === 'draft_not_publishable' || resolved.phase === 'ready_to_publish')
  ) {
    const latestUploaded = versionHasUploadSource(latest);
    if (latestUploaded) {
      activeSource = {
        title: 'Not live for employees yet',
        subtitle: `Uploaded company policy saved as a draft${
          resolved.draftVersionNumber != null ? ` · working version ${resolved.draftVersionNumber}` : ''
        }. Publish when checks pass to make it active.`,
        badge: 'Draft · uploaded policy',
      };
    } else if (policyTemplate || (latest && !versionHasUploadSource(latest))) {
      activeSource = {
        title: 'Not live for employees yet',
        subtitle: `Standard baseline or draft without a linked file${
          resolved.draftVersionNumber != null ? ` · working version ${resolved.draftVersionNumber}` : ''
        }. Publish when ready, or upload a company document to replace this path.`,
        badge: policyTemplate ? 'Draft · standard template' : 'Draft',
      };
    }
  }

  let draftReplacement: HrPolicyLifecycleContext['draftReplacement'] = null;
  if (resolved.hasUnpublishedDraftAhead && latest && !isPublishedVersion(latest)) {
    const latestUploaded = versionHasUploadSource(latest);
    const v = resolved.draftVersionNumber != null ? `Version ${resolved.draftVersionNumber}` : 'New draft';
    draftReplacement = {
      title: latestUploaded ? 'New uploaded policy — draft only' : 'New draft — not yet live',
      body: latestUploaded
        ? 'Your current published policy remains active until you publish a reviewed replacement. This file is saved as a draft only; employees still see the published version.'
        : 'Your current published policy remains active until you publish a reviewed replacement. Employees still see the published version until you publish this draft.',
      versionLabel: v,
    };
  }

  const templateUploadHint =
    resolved.phase === 'published' && policyTemplate
      ? 'You can upload your formal company policy while this baseline stays live. ReloPass saves the upload as a separate draft; employees keep seeing the published baseline until you publish the new version.'
      : null;

  return {
    employeeVisibilityLines,
    activeSource,
    draftReplacement,
    templateUploadHint,
    versionHistoryHint,
  };
}
