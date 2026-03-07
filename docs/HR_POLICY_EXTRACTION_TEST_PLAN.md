# HR Policy Extraction MVP — Test Plan

## Setup

1. **Create sample policy document:**
   ```bash
   pip install python-docx  # or use project venv
   python scripts/create_sample_hr_policy.py
   ```
   This creates `backend/tests/fixtures/HR_policy_2026.docx`.

2. **Run extraction locally:**
   ```python
   from backend.services.policy_extractor import extract_policy_from_bytes
   with open("backend/tests/fixtures/HR_policy_2026.docx", "rb") as f:
       data = extract_policy_from_bytes(f.read(), "docx")
   print(data["policy_meta"])
   print(len(data["benefits"]), "benefits extracted")
   ```

## Expected Extracted Benefits (from sample template)

At minimum, the extractor should populate these categories if present in the document:

| Category | Benefit key | Expected content |
|----------|-------------|------------------|
| Housing | temporary_housing | Days, monthly caps (OSLO_NOK, NY_USD, etc.) |
| Movers | shipment | Container/weight limits |
| Schools | education_support | Tuition percent, bands |
| Immigration | visa_support | Work permit, residence |
| Travel | travel_host | Flights, assignment types |
| Travel | scouting_trip | Days, USD cap |
| Settling-in | settling_in_allowance | Months, family size |
| Tax | tax_assistance | Assignment types |
| Spouse | spousal_support | USD cap |
| Integration | language_training | Hours |
| Repatriation | repatriation | Return shipment/travel |

## Manual E2E Test

1. Log in as HR.
2. Go to `/hr/policy`.
3. Upload `backend/tests/fixtures/HR_policy_2026.docx` (or any .docx/.pdf).
4. Click "Extract benefits".
5. Verify benefits table shows grouped categories with icons.
6. Edit a row (eligibility/limits/notes), click "Save changes".
7. Log in as Employee, go to HR Policy tab.
8. Verify read-only display with company name, version, effective date, download link, benefits table.
