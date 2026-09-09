/**
 * Characterisation of the small-admin API cluster before splitting client.ts (WS3 Task 3.8 slice 9).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import {
  adminCollaborationAPI as adminCollaborationAPIFromModule,
  adminFormTemplatesAPI as adminFormTemplatesAPIFromModule,
  adminFreshnessAPI as adminFreshnessAPIFromModule,
  adminLeadsAPI as adminLeadsAPIFromModule,
  adminMarketingAnalyticsAPI as adminMarketingAnalyticsAPIFromModule,
  adminNotificationsAPI as adminNotificationsAPIFromModule,
  adminOpsAnalyticsAPI as adminOpsAnalyticsAPIFromModule,
  adminProspectsAPI as adminProspectsAPIFromModule,
  adminRecommendationsAPI as adminRecommendationsAPIFromModule,
  adminResourcesAPI as adminResourcesAPIFromModule,
  adminReviewQueueAPI as adminReviewQueueAPIFromModule,
  adminStagingAPI as adminStagingAPIFromModule,
  leadCaptureAPI as leadCaptureAPIFromModule,
  sourceChangeReviewAPI as sourceChangeReviewAPIFromModule,
} from '../adminMiscApi';
import {
  adminCollaborationAPI,
  adminFormTemplatesAPI,
  adminFreshnessAPI,
  adminLeadsAPI,
  adminMarketingAnalyticsAPI,
  adminNotificationsAPI,
  adminOpsAnalyticsAPI,
  adminProspectsAPI,
  adminRecommendationsAPI,
  adminResourcesAPI,
  adminReviewQueueAPI,
  adminStagingAPI,
  leadCaptureAPI,
  sourceChangeReviewAPI,
} from '../client';

const ADMIN_PROSPECTS_API_METHODS = [
  'list',
  'get',
  'ingestBatch',
  'remove',
  'triage',
  'onboard',
  'reenrich',
  'reenrichFailed',
  'costEstimate',
  'exportCsvUrl',
] as const;

const ADMIN_LEADS_API_METHODS = ['list', 'get', 'patch', 'stats'] as const;

const LEAD_CAPTURE_API_METHODS = ['submit'] as const;

const ADMIN_RECOMMENDATIONS_API_METHODS = ['getDebug'] as const;

const ADMIN_RESOURCES_API_METHODS = [
  'getCounts',
  'listResources',
  'getResource',
  'createResource',
  'updateResource',
  'submitForReview',
  'approveResource',
  'publishResource',
  'unpublishResource',
  'archiveResource',
  'restoreResource',
  'deleteResource',
  'getResourceAudit',
  'getGlobalAuditLog',
  'listEvents',
  'getEvent',
  'createEvent',
  'updateEvent',
  'publishEvent',
  'archiveEvent',
  'submitEventForReview',
  'approveEvent',
  'unpublishEvent',
  'restoreEvent',
  'getEventAudit',
  'listCategories',
  'createCategory',
  'updateCategory',
  'deactivateCategory',
  'listTags',
  'createTag',
  'updateTag',
  'listSources',
  'createSource',
  'updateSource',
] as const;

const ADMIN_FORM_TEMPLATES_API_METHODS = ['list', 'get', 'create', 'update'] as const;

const ADMIN_STAGING_API_METHODS = [
  'getDashboard',
  'listResourceCandidates',
  'getResourceCandidate',
  'getResourceCandidateMatches',
  'approveResourceAsNew',
  'mergeResource',
  'rejectResource',
  'markResourceDuplicate',
  'ignoreResource',
  'restoreResourceToReview',
  'listEventCandidates',
  'getEventCandidate',
  'getEventCandidateMatches',
  'approveEventAsNew',
  'mergeEvent',
  'rejectEvent',
  'markEventDuplicate',
  'ignoreEvent',
  'restoreEventToReview',
] as const;

const ADMIN_FRESHNESS_API_METHODS = [
  'getOverview',
  'getCountries',
  'getCities',
  'getSources',
  'getSourcePages',
  'refreshFreshness',
  'listSchedules',
  'getDueSchedules',
  'getSchedule',
  'createSchedule',
  'updateSchedule',
  'pauseSchedule',
  'resumeSchedule',
  'triggerSchedule',
  'processDueSchedules',
  'triggerCrawl',
  'listJobRuns',
  'getJobRun',
  'listDocumentChanges',
  'getDocumentChange',
  'getStaleResources',
  'getStaleEvents',
] as const;

const SOURCE_CHANGE_REVIEW_API_METHODS = ['listPending', 'approve', 'reject'] as const;

const ADMIN_REVIEW_QUEUE_API_METHODS = [
  'list',
  'getStats',
  'getAssignees',
  'getItem',
  'getActivity',
  'assign',
  'claim',
  'unassign',
  'setStatus',
  'defer',
  'resolve',
  'reopen',
  'updateNotes',
  'bulkAssign',
  'bulkStatus',
  'backfill',
] as const;

const ADMIN_NOTIFICATIONS_API_METHODS = [
  'list',
  'getStats',
  'getFeed',
  'getOne',
  'getEvents',
  'acknowledge',
  'resolve',
  'suppress',
  'reopen',
  'recompute',
  'sync',
] as const;

const ADMIN_OPS_ANALYTICS_API_METHODS = [
  'getSlaOverview',
  'getWorkflowOverview',
  'getQueueBacklog',
  'getQueueBreaches',
  'getReviewerWorkload',
  'getDestinations',
  'getTopDestinationsByRequest',
  'getNotificationMetrics',
  'getBottlenecks',
  'getWorkflowFunnel',
  'getAssistantTopics',
] as const;

const ADMIN_MARKETING_ANALYTICS_API_METHODS = ['funnel'] as const;

const ADMIN_COLLABORATION_API_METHODS = [
  'getThread',
  'getOrCreateThread',
  'getSummary',
  'getSummariesBatch',
  'getThreadById',
  'getComments',
  'createComment',
  'editComment',
  'deleteComment',
  'resolveThread',
  'reopenThread',
  'closeThread',
  'markRead',
  'getUnreadCount',
] as const;

describe('admin-misc API cluster surface', () => {
  it('exposes the characterised adminProspectsAPI method names', () => {
    expect(Object.keys(adminProspectsAPI).sort()).toEqual([...ADMIN_PROSPECTS_API_METHODS].sort());
  });
  it('re-exports the same adminProspectsAPI object as adminMiscApi.ts', () => {
    expect(adminProspectsAPI).toBe(adminProspectsAPIFromModule);
  });

  it('exposes the characterised adminLeadsAPI method names', () => {
    expect(Object.keys(adminLeadsAPI).sort()).toEqual([...ADMIN_LEADS_API_METHODS].sort());
  });
  it('re-exports the same adminLeadsAPI object as adminMiscApi.ts', () => {
    expect(adminLeadsAPI).toBe(adminLeadsAPIFromModule);
  });

  it('exposes the characterised leadCaptureAPI method names', () => {
    expect(Object.keys(leadCaptureAPI).sort()).toEqual([...LEAD_CAPTURE_API_METHODS].sort());
  });
  it('re-exports the same leadCaptureAPI object as adminMiscApi.ts', () => {
    expect(leadCaptureAPI).toBe(leadCaptureAPIFromModule);
  });

  it('exposes the characterised adminRecommendationsAPI method names', () => {
    expect(Object.keys(adminRecommendationsAPI).sort()).toEqual([...ADMIN_RECOMMENDATIONS_API_METHODS].sort());
  });
  it('re-exports the same adminRecommendationsAPI object as adminMiscApi.ts', () => {
    expect(adminRecommendationsAPI).toBe(adminRecommendationsAPIFromModule);
  });

  it('exposes the characterised adminResourcesAPI method names', () => {
    expect(Object.keys(adminResourcesAPI).sort()).toEqual([...ADMIN_RESOURCES_API_METHODS].sort());
  });
  it('re-exports the same adminResourcesAPI object as adminMiscApi.ts', () => {
    expect(adminResourcesAPI).toBe(adminResourcesAPIFromModule);
  });

  it('exposes the characterised adminFormTemplatesAPI method names', () => {
    expect(Object.keys(adminFormTemplatesAPI).sort()).toEqual([...ADMIN_FORM_TEMPLATES_API_METHODS].sort());
  });
  it('re-exports the same adminFormTemplatesAPI object as adminMiscApi.ts', () => {
    expect(adminFormTemplatesAPI).toBe(adminFormTemplatesAPIFromModule);
  });

  it('exposes the characterised adminStagingAPI method names', () => {
    expect(Object.keys(adminStagingAPI).sort()).toEqual([...ADMIN_STAGING_API_METHODS].sort());
  });
  it('re-exports the same adminStagingAPI object as adminMiscApi.ts', () => {
    expect(adminStagingAPI).toBe(adminStagingAPIFromModule);
  });

  it('exposes the characterised adminFreshnessAPI method names', () => {
    expect(Object.keys(adminFreshnessAPI).sort()).toEqual([...ADMIN_FRESHNESS_API_METHODS].sort());
  });
  it('re-exports the same adminFreshnessAPI object as adminMiscApi.ts', () => {
    expect(adminFreshnessAPI).toBe(adminFreshnessAPIFromModule);
  });

  it('exposes the characterised sourceChangeReviewAPI method names', () => {
    expect(Object.keys(sourceChangeReviewAPI).sort()).toEqual([...SOURCE_CHANGE_REVIEW_API_METHODS].sort());
  });
  it('re-exports the same sourceChangeReviewAPI object as adminMiscApi.ts', () => {
    expect(sourceChangeReviewAPI).toBe(sourceChangeReviewAPIFromModule);
  });

  it('exposes the characterised adminReviewQueueAPI method names', () => {
    expect(Object.keys(adminReviewQueueAPI).sort()).toEqual([...ADMIN_REVIEW_QUEUE_API_METHODS].sort());
  });
  it('re-exports the same adminReviewQueueAPI object as adminMiscApi.ts', () => {
    expect(adminReviewQueueAPI).toBe(adminReviewQueueAPIFromModule);
  });

  it('exposes the characterised adminNotificationsAPI method names', () => {
    expect(Object.keys(adminNotificationsAPI).sort()).toEqual([...ADMIN_NOTIFICATIONS_API_METHODS].sort());
  });
  it('re-exports the same adminNotificationsAPI object as adminMiscApi.ts', () => {
    expect(adminNotificationsAPI).toBe(adminNotificationsAPIFromModule);
  });

  it('exposes the characterised adminOpsAnalyticsAPI method names', () => {
    expect(Object.keys(adminOpsAnalyticsAPI).sort()).toEqual([...ADMIN_OPS_ANALYTICS_API_METHODS].sort());
  });
  it('re-exports the same adminOpsAnalyticsAPI object as adminMiscApi.ts', () => {
    expect(adminOpsAnalyticsAPI).toBe(adminOpsAnalyticsAPIFromModule);
  });

  it('exposes the characterised adminMarketingAnalyticsAPI method names', () => {
    expect(Object.keys(adminMarketingAnalyticsAPI).sort()).toEqual([...ADMIN_MARKETING_ANALYTICS_API_METHODS].sort());
  });
  it('re-exports the same adminMarketingAnalyticsAPI object as adminMiscApi.ts', () => {
    expect(adminMarketingAnalyticsAPI).toBe(adminMarketingAnalyticsAPIFromModule);
  });

  it('exposes the characterised adminCollaborationAPI method names', () => {
    expect(Object.keys(adminCollaborationAPI).sort()).toEqual([...ADMIN_COLLABORATION_API_METHODS].sort());
  });
  it('re-exports the same adminCollaborationAPI object as adminMiscApi.ts', () => {
    expect(adminCollaborationAPI).toBe(adminCollaborationAPIFromModule);
  });
});
