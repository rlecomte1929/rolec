import { apiGet } from './client';

/** Per-event counts + funnel rates over the selected window (GET /api/admin/product-metrics). */
export interface ProductMetrics {
  period_days: number;
  since: string;
  events: Record<string, number>;
  rates: {
    wizard_completion_pct: number;
    exception_request_pct: number;
    exception_decided_pct: number;
  };
  daily: Array<{ date: string } & Record<string, number>>;
}

export function getProductMetrics(days = 30): Promise<ProductMetrics> {
  return apiGet<ProductMetrics>(`/api/admin/product-metrics?days=${days}`);
}
