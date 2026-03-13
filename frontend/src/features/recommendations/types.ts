/** Recommendation Engine types (match backend) */
export type RecommendationTier = 'best_match' | 'good_fit' | 'ok' | 'weak';
export type AvailabilityLevel = 'high' | 'medium' | 'low' | 'scarce';

export interface RecommendationExplanation {
  match_reasons: string[];
  destination_fit: string;
  service_fit: string;
  budget_fit: string;
  family_fit: string;
  policy_fit: string;
  coverage_fit: string;
  warning_flags: string[];
  explanation_summary: string;
  score_dimensions: Record<string, number>;
}

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
    estimated_cost_usd?: number;
    estimated_cost_local?: number;
    currency?: string;
    cost_type?: 'monthly' | 'annual' | 'one_time';
    map_query?: string;
  };
  explanation?: RecommendationExplanation;
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
