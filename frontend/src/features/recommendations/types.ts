/** Recommendation Engine types (match backend) */
export type RecommendationTier = 'best_match' | 'good_fit' | 'ok' | 'weak';
export type AvailabilityLevel = 'high' | 'medium' | 'low' | 'scarce';

export interface RecommendationItem {
  item_id: string;
  name: string;
  score: number;
  tier: RecommendationTier;
  summary: string;
  rationale: string;
  breakdown: Record<string, number>;
  pros: string[];
  cons: string[];
  metadata: {
    rating?: number;
    rating_count?: number;
    availability_level?: string;
    next_available_days?: number;
    waitlist_weeks?: number;
    confidence?: number;
  };
}

export interface RecommendationResponse {
  category: string;
  generated_at: string;
  criteria_echo: Record<string, unknown>;
  recommendations: RecommendationItem[];
}

export interface CategoryInfo {
  key: string;
  title: string;
  schema?: Record<string, unknown>;
}
