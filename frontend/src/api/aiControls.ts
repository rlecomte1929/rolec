import { apiGet, apiPost } from './client';

export type AiControlSource = 'env' | 'db' | 'default';

export interface AiControl {
  key: string;
  value: string;
  source: AiControlSource;
}

export interface AiControlsResponse {
  controls: AiControl[];
}

export interface SetAiControlRequest {
  key: string;
  value: string;
  reason: string;
}

export const getAiControls = (): Promise<AiControlsResponse> =>
  apiGet<AiControlsResponse>('/api/admin/ai-controls');

export const setAiControl = (req: SetAiControlRequest): Promise<AiControl> =>
  apiPost<AiControl>('/api/admin/ai-controls', req);

export const killAiFeature = (feature: string): Promise<AiControl> =>
  apiPost<AiControl>(`/api/admin/ai-controls/kill/${encodeURIComponent(feature)}`);
