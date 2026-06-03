import { apiPost } from './client';

export type TranslationDomain = 'policy' | 'comm' | 'supplier' | 'ui';
export type QualityTier = 'fast' | 'premium';

export interface TranslateRequest {
  text: string;
  src: string;
  tgt: string;
  domain?: TranslationDomain;
  quality_tier?: QualityTier;
}

export interface Translation {
  text: string;
  provider: string;
  model_version: string;
  cost_usd: number;
  cache_hit: boolean;
}

/** Translate document content via the Parker-I neural translation layer (POST /api/translate). */
export async function translateText(req: TranslateRequest): Promise<Translation> {
  return apiPost<Translation>('/api/translate', {
    domain: 'comm',
    quality_tier: 'fast',
    ...req,
  });
}
