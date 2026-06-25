/**
 * [P2-3] classification_prompt.ts
 *
 * 14-category classification prompt for HR relocation policy chunks.
 * Calls the Anthropic API at temperature=0 to deterministically classify
 * a raw text chunk into one of 14 benefit categories.
 *
 * Categories (CAT-01 → CAT-14):
 *   CAT-01  Housing Allowance
 *   CAT-02  Relocation Lump Sum
 *   CAT-03  Transportation & Shipping
 *   CAT-04  Temporary Accommodation
 *   CAT-05  Travel & Airfare
 *   CAT-06  Language & Cultural Training
 *   CAT-07  Schooling & Education
 *   CAT-08  Spousal / Partner Support
 *   CAT-09  Tax Assistance
 *   CAT-10  Healthcare & Insurance
 *   CAT-11  Home Sale / Lease Break
 *   CAT-12  Cost-of-Living Adjustment (COLA)
 *   CAT-13  Settling-In Services
 *   CAT-14  Repatriation Benefits
 *
 * Output schema (JSON):
 * {
 *   category_code: string,           // "CAT-01" … "CAT-14" | "UNCLASSIFIED"
 *   category_name: string,           // Human-readable label
 *   applicable_tiers: string[],      // e.g. ["Manager", "Director"] or []
 *   extracted_values: Array<{
 *     value: string | number | null,
 *     unit: string | null,           // "EUR", "months", "trips", etc.
 *     currency: string | null,       // ISO-4217 or null
 *     condition: string | null,      // e.g. "subject to line manager approval"
 *   }>,
 *   confidence_score: number,        // 0.0 – 1.0
 *   confidence_rationale: string,    // ≤120 chars
 * }
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExtractedValue {
  value: string | number | null;
  unit: string | null;
  currency: string | null;
  condition: string | null;
}

export interface ClassificationOutput {
  category_code: string;
  category_name: string;
  applicable_tiers: string[];
  extracted_values: ExtractedValue[];
  confidence_score: number;
  confidence_rationale: string;
}

export interface ClassifyOptions {
  /** Anthropic API key — defaults to VITE_ANTHROPIC_API_KEY env var */
  apiKey?: string;
  /** Model name — defaults to claude-3-5-haiku-20241022 for speed */
  model?: string;
  /** Max tokens for the classification response (default 512) */
  maxTokens?: number;
}

// ---------------------------------------------------------------------------
// Category definitions (used in prompt and for validation)
// ---------------------------------------------------------------------------

export const CATEGORIES: Array<{ code: string; name: string; keywords: string[] }> = [
  {
    code: 'CAT-01',
    name: 'Housing Allowance',
    keywords: ['housing', 'rent', 'accommodation allowance', 'housing cap', 'monthly housing'],
  },
  {
    code: 'CAT-02',
    name: 'Relocation Lump Sum',
    keywords: ['lump sum', 'relocation bonus', 'one-time payment', 'cash allowance', 'flat-rate'],
  },
  {
    code: 'CAT-03',
    name: 'Transportation & Shipping',
    keywords: ['shipping', 'household goods', 'freight', 'moving costs', 'container', 'vehicle shipment'],
  },
  {
    code: 'CAT-04',
    name: 'Temporary Accommodation',
    keywords: ['temporary housing', 'serviced apartment', 'hotel', 'interim accommodation', 'short-term'],
  },
  {
    code: 'CAT-05',
    name: 'Travel & Airfare',
    keywords: ['airfare', 'flights', 'business class', 'economy', 'travel allowance', 'airline tickets'],
  },
  {
    code: 'CAT-06',
    name: 'Language & Cultural Training',
    keywords: ['language training', 'cultural training', 'language lessons', 'cross-cultural', 'language course'],
  },
  {
    code: 'CAT-07',
    name: 'Schooling & Education',
    keywords: ['school fees', 'tuition', 'education allowance', 'private school', 'international school'],
  },
  {
    code: 'CAT-08',
    name: 'Spousal / Partner Support',
    keywords: ['spouse', 'partner support', 'accompanying partner', 'spousal assistance', 'partner career', 'spousal career', 'spousal program'],
  },
  {
    code: 'CAT-09',
    name: 'Tax Assistance',
    keywords: ['tax equalization', 'tax assistance', 'tax gross-up', 'hypothetical tax', 'tax return'],
  },
  {
    code: 'CAT-10',
    name: 'Healthcare & Insurance',
    keywords: ['health insurance', 'medical', 'healthcare', 'international medical', 'BUPA', 'Cigna'],
  },
  {
    code: 'CAT-11',
    name: 'Home Sale / Lease Break',
    keywords: ['home sale', 'lease break', 'early termination', 'property sale', 'rental termination', 'lease termination', 'lease fees', 'estate agent'],
  },
  {
    code: 'CAT-12',
    name: 'Cost-of-Living Adjustment',
    keywords: ['COLA', 'cost of living', 'hardship allowance', 'location premium', 'index adjustment'],
  },
  {
    code: 'CAT-13',
    name: 'Settling-In Services',
    keywords: ['settling-in', 'orientation', 'destination services', 'area tour', 'utility setup', 'school search'],
  },
  {
    code: 'CAT-14',
    name: 'Repatriation Benefits',
    keywords: ['repatriation', 'return relocation', 'home country', 'end of assignment', 'repatriation flight', 'repatriation lump', 'repatriation allowance', 'repatriation services'],
  },
];

const CATEGORY_CODES = new Set(CATEGORIES.map((c) => c.code));

// ---------------------------------------------------------------------------
// System prompt with 42 few-shot examples (3 per category)
// ---------------------------------------------------------------------------

export const CLASSIFICATION_SYSTEM_PROMPT = `You are an expert HR relocation policy analyst. Given a raw text excerpt from a corporate relocation policy document, classify it into exactly one of the 14 benefit categories below and extract all numeric values with their units, currencies, and conditions.

CATEGORIES:
CAT-01 Housing Allowance — monthly housing rent subsidy or cap
CAT-02 Relocation Lump Sum — one-time cash payment for relocation
CAT-03 Transportation & Shipping — household goods, vehicle, freight
CAT-04 Temporary Accommodation — short-term hotel or serviced apartment
CAT-05 Travel & Airfare — flights and travel costs for employee and family
CAT-06 Language & Cultural Training — language lessons or cross-cultural coaching
CAT-07 Schooling & Education — school tuition and education fees for dependants
CAT-08 Spousal / Partner Support — career coaching, job search, or allowance for partner
CAT-09 Tax Assistance — tax equalization, gross-up, or advisory services
CAT-10 Healthcare & Insurance — international health insurance or medical plan
CAT-11 Home Sale / Lease Break — assistance with selling home or breaking lease
CAT-12 Cost-of-Living Adjustment — COLA index, hardship premium, or location allowance
CAT-13 Settling-In Services — destination services, area orientation, utility setup
CAT-14 Repatriation Benefits — end-of-assignment relocation back to home country

If the excerpt does not fit any category, output category_code "UNCLASSIFIED".

RULES:
1. Return ONLY a JSON object matching the schema. No prose, no markdown fences.
2. applicable_tiers: extract grade/tier labels mentioned (e.g. "Manager", "Director", "VP", "Band 5"). Return [] if none.
3. extracted_values: extract every numeric benefit value. Include value (number or string), unit (e.g. "EUR/month", "nights", "trips"), currency (ISO-4217 or null), condition (any qualifying phrase or null).
4. confidence_score: 0.9–1.0 if highly explicit; 0.7–0.89 if somewhat ambiguous; 0.5–0.69 if requires inference; <0.5 if very unclear.
5. confidence_rationale: ≤120 characters explaining your confidence.

OUTPUT SCHEMA:
{
  "category_code": "CAT-XX",
  "category_name": "...",
  "applicable_tiers": ["...", "..."],
  "extracted_values": [
    {"value": 3500, "unit": "EUR/month", "currency": "EUR", "condition": null}
  ],
  "confidence_score": 0.95,
  "confidence_rationale": "Explicit monthly cap stated with currency and grade"
}

FEW-SHOT EXAMPLES:

### CAT-01 Example 1
Chunk: "The housing allowance for Manager grade employees is capped at EUR 3,500 per month including utilities."
Output: {"category_code":"CAT-01","category_name":"Housing Allowance","applicable_tiers":["Manager"],"extracted_values":[{"value":3500,"unit":"EUR/month","currency":"EUR","condition":"including utilities"}],"confidence_score":0.97,"confidence_rationale":"Explicit cap stated with tier, currency and amount"}

### CAT-01 Example 2
Chunk: "Director-level assignees may receive a monthly housing subsidy of up to GBP 5,000 for London postings."
Output: {"category_code":"CAT-01","category_name":"Housing Allowance","applicable_tiers":["Director"],"extracted_values":[{"value":5000,"unit":"GBP/month","currency":"GBP","condition":"London postings"}],"confidence_score":0.88,"confidence_rationale":"Value hedged by 'up to' — approximate cap"}

### CAT-01 Example 3
Chunk: "Housing support is provided at competitive market rates determined by the destination city index."
Output: {"category_code":"CAT-01","category_name":"Housing Allowance","applicable_tiers":[],"extracted_values":[],"confidence_score":0.62,"confidence_rationale":"Category clear but no explicit value — market-rate reference only"}

### CAT-02 Example 1
Chunk: "A one-time relocation lump sum of USD 10,000 will be paid to the employee upon commencement of the assignment."
Output: {"category_code":"CAT-02","category_name":"Relocation Lump Sum","applicable_tiers":[],"extracted_values":[{"value":10000,"unit":"USD","currency":"USD","condition":"upon commencement of assignment"}],"confidence_score":0.98,"confidence_rationale":"Explicit one-time amount with trigger condition"}

### CAT-02 Example 2
Chunk: "Band 4 and Band 5 employees receive a flat-rate relocation cash allowance of EUR 6,000 gross."
Output: {"category_code":"CAT-02","category_name":"Relocation Lump Sum","applicable_tiers":["Band 4","Band 5"],"extracted_values":[{"value":6000,"unit":"EUR","currency":"EUR","condition":"gross"}],"confidence_score":0.96,"confidence_rationale":"Explicit amount, tiers and gross basis stated"}

### CAT-02 Example 3
Chunk: "The company may provide a miscellaneous relocation allowance at management's discretion."
Output: {"category_code":"CAT-02","category_name":"Relocation Lump Sum","applicable_tiers":[],"extracted_values":[],"confidence_score":0.55,"confidence_rationale":"Category fits but amount undefined and subject to discretion"}

### CAT-03 Example 1
Chunk: "The company will reimburse the cost of shipping household goods up to a maximum of EUR 8,000 for container shipments."
Output: {"category_code":"CAT-03","category_name":"Transportation & Shipping","applicable_tiers":[],"extracted_values":[{"value":8000,"unit":"EUR","currency":"EUR","condition":"container shipments only"}],"confidence_score":0.93,"confidence_rationale":"Clear shipping cap with explicit limit and scope"}

### CAT-03 Example 2
Chunk: "VP-grade assignees are entitled to full door-to-door household goods shipping with no cost cap."
Output: {"category_code":"CAT-03","category_name":"Transportation & Shipping","applicable_tiers":["VP"],"extracted_values":[{"value":null,"unit":null,"currency":null,"condition":"no cost cap — full reimbursement"}],"confidence_score":0.90,"confidence_rationale":"Full coverage confirmed; no numeric cap to extract"}

### CAT-03 Example 3
Chunk: "Vehicle transportation costs may be covered where deemed necessary by the mobility team."
Output: {"category_code":"CAT-03","category_name":"Transportation & Shipping","applicable_tiers":[],"extracted_values":[],"confidence_score":0.60,"confidence_rationale":"Category identifiable but coverage is conditional and discretionary"}

### CAT-04 Example 1
Chunk: "The company provides up to 90 nights of temporary accommodation in a serviced apartment upon arrival."
Output: {"category_code":"CAT-04","category_name":"Temporary Accommodation","applicable_tiers":[],"extracted_values":[{"value":90,"unit":"nights","currency":null,"condition":"serviced apartment upon arrival"}],"confidence_score":0.95,"confidence_rationale":"Duration explicit; type of accommodation specified"}

### CAT-04 Example 2
Chunk: "Senior Managers are entitled to hotel accommodation for up to 30 days while arranging permanent housing."
Output: {"category_code":"CAT-04","category_name":"Temporary Accommodation","applicable_tiers":["Senior Manager"],"extracted_values":[{"value":30,"unit":"days","currency":null,"condition":"while arranging permanent housing"}],"confidence_score":0.94,"confidence_rationale":"Duration and tier explicit with qualifying condition"}

### CAT-04 Example 3
Chunk: "Short-term housing may be arranged by the mobility team as required during the transition period."
Output: {"category_code":"CAT-04","category_name":"Temporary Accommodation","applicable_tiers":[],"extracted_values":[],"confidence_score":0.58,"confidence_rationale":"No duration or cost — entirely discretionary"}

### CAT-05 Example 1
Chunk: "The employee and up to 3 dependants will receive business class flights to the destination country."
Output: {"category_code":"CAT-05","category_name":"Travel & Airfare","applicable_tiers":[],"extracted_values":[{"value":4,"unit":"business class flights","currency":null,"condition":"employee + up to 3 dependants"}],"confidence_score":0.96,"confidence_rationale":"Class of travel and number of travellers stated explicitly"}

### CAT-05 Example 2
Chunk: "VP-level employees may take one home leave trip per year in business class; economy class for dependants."
Output: {"category_code":"CAT-05","category_name":"Travel & Airfare","applicable_tiers":["VP"],"extracted_values":[{"value":1,"unit":"trips/year","currency":null,"condition":"business class employee, economy dependants"}],"confidence_score":0.93,"confidence_rationale":"Frequency and class entitlement explicit with tier"}

### CAT-05 Example 3
Chunk: "Travel costs for the relocation journey will be reimbursed in line with the company travel policy."
Output: {"category_code":"CAT-05","category_name":"Travel & Airfare","applicable_tiers":[],"extracted_values":[],"confidence_score":0.65,"confidence_rationale":"Category clear but amount deferred to separate policy document"}

### CAT-06 Example 1
Chunk: "Employees are entitled to 60 hours of language training in the host country language, capped at EUR 2,500."
Output: {"category_code":"CAT-06","category_name":"Language & Cultural Training","applicable_tiers":[],"extracted_values":[{"value":60,"unit":"hours","currency":null,"condition":null},{"value":2500,"unit":"EUR","currency":"EUR","condition":"cap"}],"confidence_score":0.97,"confidence_rationale":"Hours and cost cap both stated explicitly"}

### CAT-06 Example 2
Chunk: "Director-grade assignees and their partner may attend cross-cultural coaching sessions (up to 8 sessions)."
Output: {"category_code":"CAT-06","category_name":"Language & Cultural Training","applicable_tiers":["Director"],"extracted_values":[{"value":8,"unit":"sessions","currency":null,"condition":"assignee and partner eligible"}],"confidence_score":0.90,"confidence_rationale":"Session count explicit; 'up to' introduces slight ambiguity"}

### CAT-06 Example 3
Chunk: "Cultural orientation support will be arranged as appropriate for the host location."
Output: {"category_code":"CAT-06","category_name":"Language & Cultural Training","applicable_tiers":[],"extracted_values":[],"confidence_score":0.57,"confidence_rationale":"No hours, sessions or cost — vague discretionary language"}

### CAT-07 Example 1
Chunk: "School tuition fees for dependent children will be reimbursed up to CHF 30,000 per child per academic year."
Output: {"category_code":"CAT-07","category_name":"Schooling & Education","applicable_tiers":[],"extracted_values":[{"value":30000,"unit":"CHF/child/year","currency":"CHF","condition":null}],"confidence_score":0.98,"confidence_rationale":"Per-child annual cap explicitly stated in Swiss francs"}

### CAT-07 Example 2
Chunk: "Manager and above may claim international school fees up to EUR 15,000 per annum per child."
Output: {"category_code":"CAT-07","category_name":"Schooling & Education","applicable_tiers":["Manager"],"extracted_values":[{"value":15000,"unit":"EUR/child/year","currency":"EUR","condition":"international school"}],"confidence_score":0.96,"confidence_rationale":"Cap, tier, frequency and school type all explicit"}

### CAT-07 Example 3
Chunk: "Education assistance for school-age dependants may be provided subject to HR approval."
Output: {"category_code":"CAT-07","category_name":"Schooling & Education","applicable_tiers":[],"extracted_values":[],"confidence_score":0.55,"confidence_rationale":"Category evident but amount is fully discretionary"}

### CAT-08 Example 1
Chunk: "An accompanying partner allowance of EUR 3,000 is provided to support job search and professional development."
Output: {"category_code":"CAT-08","category_name":"Spousal / Partner Support","applicable_tiers":[],"extracted_values":[{"value":3000,"unit":"EUR","currency":"EUR","condition":"job search and professional development"}],"confidence_score":0.96,"confidence_rationale":"Explicit allowance for accompanying partner with stated purpose"}

### CAT-08 Example 2
Chunk: "The company will fund spousal career coaching up to 6 sessions with an accredited career coach."
Output: {"category_code":"CAT-08","category_name":"Spousal / Partner Support","applicable_tiers":[],"extracted_values":[{"value":6,"unit":"sessions","currency":null,"condition":"accredited career coach"}],"confidence_score":0.94,"confidence_rationale":"Session count stated; 'up to' limits certainty slightly"}

### CAT-08 Example 3
Chunk: "Support for the accompanying partner's integration into the host country may be considered."
Output: {"category_code":"CAT-08","category_name":"Spousal / Partner Support","applicable_tiers":[],"extracted_values":[],"confidence_score":0.52,"confidence_rationale":"Category evident but entitlement is discretionary with no value"}

### CAT-09 Example 1
Chunk: "The company operates a tax equalization policy ensuring the employee pays no more than their hypothetical home-country tax."
Output: {"category_code":"CAT-09","category_name":"Tax Assistance","applicable_tiers":[],"extracted_values":[{"value":null,"unit":null,"currency":null,"condition":"hypothetical home-country tax applies"}],"confidence_score":0.97,"confidence_rationale":"Standard tax equalization policy clearly described"}

### CAT-09 Example 2
Chunk: "All Director-grade and above assignees will receive an annual tax return preparation service funded by the company."
Output: {"category_code":"CAT-09","category_name":"Tax Assistance","applicable_tiers":["Director"],"extracted_values":[{"value":1,"unit":"tax return/year","currency":null,"condition":"company funded"}],"confidence_score":0.92,"confidence_rationale":"Service and tier explicit; frequency annual"}

### CAT-09 Example 3
Chunk: "Tax implications will be discussed with the employee during the pre-assignment briefing."
Output: {"category_code":"CAT-09","category_name":"Tax Assistance","applicable_tiers":[],"extracted_values":[],"confidence_score":0.53,"confidence_rationale":"Mentions tax context but no benefit entitlement described"}

### CAT-10 Example 1
Chunk: "Internationally mobile employees and their family members are enrolled in the Cigna Global Health plan at company expense."
Output: {"category_code":"CAT-10","category_name":"Healthcare & Insurance","applicable_tiers":[],"extracted_values":[{"value":null,"unit":null,"currency":null,"condition":"company funded, includes family"}],"confidence_score":0.96,"confidence_rationale":"Named health plan with family coverage confirmed at company cost"}

### CAT-10 Example 2
Chunk: "Manager-grade assignees receive an international health insurance allowance of up to EUR 4,000 per year."
Output: {"category_code":"CAT-10","category_name":"Healthcare & Insurance","applicable_tiers":["Manager"],"extracted_values":[{"value":4000,"unit":"EUR/year","currency":"EUR","condition":"up to — annual cap"}],"confidence_score":0.89,"confidence_rationale":"Cap stated but 'up to' introduces slight ambiguity"}

### CAT-10 Example 3
Chunk: "Healthcare coverage during the assignment will align with local statutory requirements."
Output: {"category_code":"CAT-10","category_name":"Healthcare & Insurance","applicable_tiers":[],"extracted_values":[],"confidence_score":0.60,"confidence_rationale":"Category clear but entitlement deferred to local law"}

### CAT-11 Example 1
Chunk: "The company will reimburse documented lease break fees up to 3 months' rent to assist with home country lease termination."
Output: {"category_code":"CAT-11","category_name":"Home Sale / Lease Break","applicable_tiers":[],"extracted_values":[{"value":3,"unit":"months rent","currency":null,"condition":"documented fees, home country lease"}],"confidence_score":0.95,"confidence_rationale":"Cap in months of rent stated with documentation requirement"}

### CAT-11 Example 2
Chunk: "Directors may claim up to EUR 20,000 towards estate agent fees incurred on the sale of their primary residence."
Output: {"category_code":"CAT-11","category_name":"Home Sale / Lease Break","applicable_tiers":["Director"],"extracted_values":[{"value":20000,"unit":"EUR","currency":"EUR","condition":"primary residence estate agent fees"}],"confidence_score":0.94,"confidence_rationale":"Amount, tier and qualifying expense type all explicit"}

### CAT-11 Example 3
Chunk: "Assistance with home sale or lease termination may be available upon request and case-by-case review."
Output: {"category_code":"CAT-11","category_name":"Home Sale / Lease Break","applicable_tiers":[],"extracted_values":[],"confidence_score":0.51,"confidence_rationale":"Category identifiable but no benefit amount — entirely discretionary"}

### CAT-12 Example 1
Chunk: "Employees relocating to high-cost cities receive a COLA supplement of 15% of base salary, reviewed annually."
Output: {"category_code":"CAT-12","category_name":"Cost-of-Living Adjustment","applicable_tiers":[],"extracted_values":[{"value":15,"unit":"% of base salary","currency":null,"condition":"high-cost cities, reviewed annually"}],"confidence_score":0.96,"confidence_rationale":"Percentage COLA stated with review cadence"}

### CAT-12 Example 2
Chunk: "A hardship allowance of up to 20% of base pay is granted for Band 6 postings to hardship locations."
Output: {"category_code":"CAT-12","category_name":"Cost-of-Living Adjustment","applicable_tiers":["Band 6"],"extracted_values":[{"value":20,"unit":"% base pay","currency":null,"condition":"hardship locations"}],"confidence_score":0.90,"confidence_rationale":"Percentage and tier stated; 'up to' introduces slight variance"}

### CAT-12 Example 3
Chunk: "Location-based salary adjustments will be determined by the compensation benchmarking tool."
Output: {"category_code":"CAT-12","category_name":"Cost-of-Living Adjustment","applicable_tiers":[],"extracted_values":[],"confidence_score":0.58,"confidence_rationale":"Category fits but no explicit adjustment value or method stated"}

### CAT-13 Example 1
Chunk: "The company provides a 2-day destination orientation tour covering schools, neighbourhoods, and essential services."
Output: {"category_code":"CAT-13","category_name":"Settling-In Services","applicable_tiers":[],"extracted_values":[{"value":2,"unit":"days","currency":null,"condition":"school, neighbourhood and services orientation"}],"confidence_score":0.95,"confidence_rationale":"Duration and scope of settling-in service explicitly described"}

### CAT-13 Example 2
Chunk: "Director-level assignees receive a comprehensive settling-in services package worth up to EUR 5,000 from the DSP."
Output: {"category_code":"CAT-13","category_name":"Settling-In Services","applicable_tiers":["Director"],"extracted_values":[{"value":5000,"unit":"EUR","currency":"EUR","condition":"via DSP — destination service provider"}],"confidence_score":0.92,"confidence_rationale":"Cap stated with tier and delivery mechanism"}

### CAT-13 Example 3
Chunk: "Some administrative support may be offered to help employees settle into the new location."
Output: {"category_code":"CAT-13","category_name":"Settling-In Services","applicable_tiers":[],"extracted_values":[],"confidence_score":0.55,"confidence_rationale":"Category fits but entitlement is vague and discretionary"}

### CAT-14 Example 1
Chunk: "Upon completion of the assignment, the employee and family are entitled to economy class flights back to the home country."
Output: {"category_code":"CAT-14","category_name":"Repatriation Benefits","applicable_tiers":[],"extracted_values":[{"value":null,"unit":"economy class flights","currency":null,"condition":"end of assignment, includes family"}],"confidence_score":0.95,"confidence_rationale":"Repatriation flights confirmed with class and eligibility"}

### CAT-14 Example 2
Chunk: "A repatriation lump sum of EUR 5,000 is paid to all Band 4 and above employees returning to their home country."
Output: {"category_code":"CAT-14","category_name":"Repatriation Benefits","applicable_tiers":["Band 4"],"extracted_values":[{"value":5000,"unit":"EUR","currency":"EUR","condition":"return to home country"}],"confidence_score":0.97,"confidence_rationale":"Amount, tier and trigger event all explicitly stated"}

### CAT-14 Example 3
Chunk: "Repatriation support will be coordinated by the global mobility team at the end of the assignment period."
Output: {"category_code":"CAT-14","category_name":"Repatriation Benefits","applicable_tiers":[],"extracted_values":[],"confidence_score":0.60,"confidence_rationale":"Category clear but no benefit amount or entitlement specified"}

Now classify the following policy text chunk. Return ONLY the JSON object.`;

// ---------------------------------------------------------------------------
// Pure helpers (testable without API)
// ---------------------------------------------------------------------------

/**
 * Validate that a raw LLM response string is valid JSON and conforms to the
 * ClassificationOutput schema. Returns the parsed object or throws.
 */
export function parseClassificationOutput(raw: string): ClassificationOutput {
  // Strip accidental markdown fences if the model adds them
  const cleaned = raw
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();

  let parsed: unknown;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    throw new Error(`Classification response is not valid JSON: ${cleaned.slice(0, 200)}`);
  }

  const obj = parsed as Record<string, unknown>;

  if (typeof obj.category_code !== 'string') {
    throw new Error('Missing or invalid category_code in classification response');
  }
  if (typeof obj.category_name !== 'string') {
    throw new Error('Missing or invalid category_name in classification response');
  }
  if (!Array.isArray(obj.applicable_tiers)) {
    throw new Error('applicable_tiers must be an array');
  }
  if (!Array.isArray(obj.extracted_values)) {
    throw new Error('extracted_values must be an array');
  }
  if (typeof obj.confidence_score !== 'number') {
    throw new Error('confidence_score must be a number');
  }
  if (typeof obj.confidence_rationale !== 'string') {
    throw new Error('confidence_rationale must be a string');
  }

  return {
    category_code: obj.category_code,
    category_name: obj.category_name,
    applicable_tiers: obj.applicable_tiers as string[],
    extracted_values: obj.extracted_values as ExtractedValue[],
    confidence_score: Math.max(0, Math.min(1, obj.confidence_score as number)),
    confidence_rationale: (obj.confidence_rationale as string).slice(0, 120),
  };
}

/**
 * Build the user message for a given chunk text.
 */
export function buildUserMessage(chunkText: string): string {
  return `Chunk: "${chunkText.trim()}"`;
}

/**
 * Return the category name for a given code, or "Unknown" if not found.
 */
export function getCategoryName(code: string): string {
  return CATEGORIES.find((c) => c.code === code)?.name ?? 'Unknown';
}

/**
 * Return true if the code is a valid known category code (or UNCLASSIFIED).
 */
export function isValidCategoryCode(code: string): boolean {
  return code === 'UNCLASSIFIED' || CATEGORY_CODES.has(code);
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Classify a single policy chunk text into one of the 14 HR benefit categories.
 *
 * Calls the Anthropic Messages API at temperature=0 for determinism.
 * Returns a ClassificationOutput with structured extracted values.
 *
 * @param chunkText  Raw text excerpt from a policy document
 * @param options    Optional overrides for API key, model, maxTokens
 */
export async function classifyChunk(
  chunkText: string,
  options: ClassifyOptions = {},
): Promise<ClassificationOutput> {
  // Lazy import of Supabase-adjacent module pattern — keep top-level import-free
  // for testability; API key sourced from env or caller
  const apiKey =
    options.apiKey ??
    (typeof import.meta !== 'undefined' && (import.meta as unknown as Record<string, unknown>).env
      ? ((import.meta as unknown as Record<string, unknown>).env as Record<string, string>)
          .VITE_ANTHROPIC_API_KEY
      : undefined);

  if (!apiKey) {
    throw new Error(
      'Anthropic API key is required. Set VITE_ANTHROPIC_API_KEY or pass options.apiKey.',
    );
  }

  const model = options.model ?? 'claude-3-5-haiku-20241022';
  const maxTokens = options.maxTokens ?? 512;

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      temperature: 0,
      system: CLASSIFICATION_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: buildUserMessage(chunkText) }],
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Anthropic API error ${response.status}: ${body.slice(0, 300)}`);
  }

  const data = (await response.json()) as {
    content: Array<{ type: string; text: string }>;
  };

  const textBlock = data.content.find((b) => b.type === 'text');
  if (!textBlock) {
    throw new Error('No text block in Anthropic API response');
  }

  return parseClassificationOutput(textBlock.text);
}

// ---------------------------------------------------------------------------
// Batch classify
// ---------------------------------------------------------------------------

export interface BatchClassifyResult {
  index: number;
  chunkText: string;
  output: ClassificationOutput | null;
  error: string | null;
}

/**
 * Classify an array of chunks, returning results in the same order.
 * Errors on individual chunks are captured and do not abort the batch.
 *
 * @param chunks   Array of raw text strings to classify
 * @param options  Shared ClassifyOptions applied to every call
 */
export async function batchClassifyChunks(
  chunks: string[],
  options: ClassifyOptions = {},
): Promise<BatchClassifyResult[]> {
  const results: BatchClassifyResult[] = [];

  for (let i = 0; i < chunks.length; i++) {
    const chunkText = chunks[i] ?? '';
    try {
      const output = await classifyChunk(chunkText, options);
      results.push({ index: i, chunkText, output, error: null });
    } catch (err) {
      results.push({
        index: i,
        chunkText,
        output: null,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return results;
}
