# backend/app/config/vendor_discovery.py
# Single source of truth for the vendor discovery system.
# Edit this file to add corridors, categories, or adjust quality thresholds.
# Pure config — no imports, no logic, importable with zero env vars set.

PRIORITY_CORRIDORS = [
    {"origin": "US", "destination_country": "FR", "destination_city": "Paris", "corridor_code": "US-FR"},
    {"origin": "US", "destination_country": "DE", "destination_city": "Berlin", "corridor_code": "US-DE"},
    {"origin": "US", "destination_country": "GB", "destination_city": "London", "corridor_code": "US-GB"},
    {"origin": "GB", "destination_country": "FR", "destination_city": "Paris", "corridor_code": "GB-FR"},
    {"origin": "GB", "destination_country": "DE", "destination_city": "Berlin", "corridor_code": "GB-DE"},
    {"origin": "FR", "destination_country": "DE", "destination_city": "Berlin", "corridor_code": "FR-DE"},
    {"origin": "DE", "destination_country": "FR", "destination_city": "Paris", "corridor_code": "DE-FR"},
    {"origin": "US", "destination_country": "NL", "destination_city": "Amsterdam", "corridor_code": "US-NL"},
    {"origin": "GB", "destination_country": "NL", "destination_city": "Amsterdam", "corridor_code": "GB-NL"},
    {"origin": "US", "destination_country": "ES", "destination_city": "Barcelona", "corridor_code": "US-ES"},
]

# Maps each ReloPass service category to ordered Google Places Text Search query templates.
# {city} is replaced at runtime. First template is used by default; others are tried on empty results (future).
SERVICE_CATEGORY_SEARCH_TERMS = {
    "movers": ["international removals {city}", "international movers {city}", "relocation moving company {city}"],
    "housing": ["relocation housing agency {city}", "furnished apartments {city} expat", "real estate expat {city}"],
    "schools": ["international school {city}", "bilingual school {city}"],
    "banks": ["expat bank account {city}", "international banking services {city}"],
    "insurance": ["expat health insurance broker {city}", "international health insurance {city}"],
    "language_integration": ["language school adults {city}", "expat language courses {city}"],
    "legal_admin": ["immigration lawyer {city}", "visa consultant {city}", "relocation legal services {city}"],
    "tax_finance": ["expat tax advisor {city}", "international tax consultant {city}"],
    "medical": ["English speaking doctor {city}", "international GP {city}"],
    "childcare": ["English speaking nursery {city}", "international childcare {city}"],
    "telecom": ["mobile phone plan expats {city}", "SIM card for foreigners {city}"],
    "storage": ["self storage {city}", "international storage {city}"],
}

# Minimum quality bars that a vendor must pass to be included in the catalog.
VENDOR_QUALITY_THRESHOLDS = {
    "min_rating": 3.8,           # Google rating (0–5 scale)
    "min_review_count": 10,      # Minimum number of Google reviews
    "required_business_status": "OPERATIONAL",
    "top_n_vendors": 5,          # Maximum vendors stored per (category, city)
    "max_candidates_to_fetch": 20,  # Max results requested from Places API per query
    "freshness_days": 90,        # Days before a scraped vendor is considered stale
}

# Maps service categories to their industry accreditation bodies.
# Vendors whose domain matches a known accredited member get an accreditation_tags boost.
ACCREDITATION_BY_CATEGORY = {
    "movers": ["FIDI", "IAM", "BAR"],       # FIDI = intl movers federation, IAM = intl assoc of movers, BAR = UK
    "housing": ["ARLA", "RICS", "FNAIM", "IVD"],  # UK, UK, FR, DE property associations
}
