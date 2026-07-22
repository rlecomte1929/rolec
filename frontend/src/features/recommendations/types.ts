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
  /** Estimated monthly cost as a % of the company housing cap (FX-normalized). */
  budget_pct_of_cap?: number | null;
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
    company_preferred?: boolean;
    /** Neighborhood coordinates for the housing map (living_areas). */
    lat?: number;
    lng?: number;
    /** Curated schools reachable from this neighborhood (Phase 3, school-age cases). */
    nearby_schools?: Array<{
      item_id: string;
      name: string;
      type?: string;
      curriculum?: string;
      lat: number;
      lng: number;
      commute_min: number;
    }>;
    /** Multimodal commute to the office (living_areas): per-mode time + cost + carbon. */
    commute_modes?: Array<{
      mode: string;
      minutes: number;
      distance_km: number;
      cost: number;
      carbon_g: number;
    }>;
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
