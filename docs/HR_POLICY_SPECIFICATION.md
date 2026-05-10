# HR Policy Specification — Global Mobility Platform

## 1. Data Model Structure

### 1.1 HRPolicy Schema (JSON-compatible)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "HRPolicy",
  "type": "object",
  "required": ["policyId", "effectiveDate", "companyEntity", "assignmentTypes", "employeeBands", "benefitCategories"],
  "properties": {
    "policyId": { "type": "string", "format": "uuid", "description": "Unique policy identifier" },
    "version": { "type": "integer", "minimum": 1, "description": "Policy version for audit" },
    "policyName": { "type": "string", "description": "Human-readable policy name" },
    "companyEntity": { "type": "string", "description": "Company or legal entity ID" },
    "effectiveDate": { "type": "string", "format": "date", "description": "YYYY-MM-DD" },
    "expiryDate": { "type": ["string", "null"], "format": "date" },
    "status": { "enum": ["draft", "published", "archived"], "default": "draft" },
    "employeeBands": {
      "type": "array",
      "items": { "type": "string" },
      "description": "e.g. Band1, Band2, Band3, Band4"
    },
    "assignmentTypes": {
      "type": "array",
      "items": { "enum": ["Permanent", "Long-Term", "Short-Term"] },
      "minItems": 1
    },
    "benefitCategories": {
      "type": "object",
      "additionalProperties": {
        "$ref": "#/definitions/BenefitDefinition"
      }
    },
    "bandAssignmentRules": {
      "type": "object",
      "description": "Per band + assignment type matrix. Keys: band_assignmentType",
      "additionalProperties": {
        "$ref": "#/definitions/BandAssignmentRule"
      }
    },
    "jurisdictionOverrides": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "countryCode": { "type": "string" },
          "overrideBenefitCategories": {
            "type": "object",
            "additionalProperties": { "$ref": "#/definitions/BenefitDefinition" }
          },
          "notes": { "type": "string" }
        }
      }
    },
    "documentationRequired": {
      "type": "object",
      "description": "Per benefit category or global",
      "additionalProperties": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "preApprovalRequired": {
      "type": "object",
      "additionalProperties": { "type": "boolean" }
    },
    "conditionalDependencies": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "benefit": { "type": "string" },
          "requires": { "type": "array", "items": { "type": "string" } },
          "condition": { "type": "string" }
        }
      }
    },
    "reimbursementRules": { "type": "string" },
    "repaymentClauses": { "type": "string" },
    "auditTrail": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": { "type": "string", "format": "date-time" },
          "userId": { "type": "string" },
          "action": { "enum": ["create", "update", "publish", "archive"] },
          "changes": { "type": "object" }
        }
      }
    }
  },
  "definitions": {
    "BenefitDefinition": {
      "type": "object",
      "required": ["allowed"],
      "properties": {
        "allowed": { "type": "boolean" },
        "maxAllowed": {
          "type": "object",
          "properties": {
            "min": { "type": "number", "minimum": 0 },
            "medium": { "type": "number", "minimum": 0 },
            "extensive": { "type": "number", "minimum": 0 },
            "premium": { "type": "number", "minimum": 0 }
          }
        },
        "unit": {
          "enum": ["currency", "days", "weeks", "months", "percentage"],
          "default": "currency"
        },
        "currency": {
          "enum": ["NOK", "USD", "GBP", "SGD", "EUR"],
          "default": "USD"
        },
        "documentationRequired": {
          "type": "array",
          "items": { "type": "string" }
        },
        "preApprovalRequired": { "type": "boolean", "default": false },
        "notes": { "type": "string" },
        "supportDocUrl": { "type": "string", "format": "uri" }
      }
    },
    "BandAssignmentRule": {
      "type": "object",
      "description": "Override of benefitCategories for a specific band+assignmentType",
      "properties": {
        "benefitOverrides": {
          "type": "object",
          "additionalProperties": { "$ref": "#/definitions/BenefitDefinition" }
        },
        "fallbackBand": { "type": "string", "description": "If no entry, use this band" }
      }
    }
  }
}
```

### 1.2 Benefit Category Keys (Standard Set)

```
preAssignmentVisit, travel, temporaryHousing, houseHunting, shipment, storage,
homeSalePurchase, rentalAssistance, settlingInAllowance, visaImmigration,
taxAssistance, spousalSupport, educationSupport, languageTraining, repatriation
```

---

## 2. HR Profile — Editable Policy Screen Logic

### 2.1 Section A — Policy Overview

| Field | Editable | Type | Validation |
|-------|----------|------|------------|
| Policy name | Yes | Text | Required, max 200 chars |
| Effective date | Yes | Date | Required, not in past when publishing |
| Expiry date | Yes | Date | Optional, must be > effectiveDate |
| Country entity | Yes | Select / Text | Required |
| Assignment types | Yes | Multi-select | Min 1 required |
| Employee bands | Yes | Multi-select / Tag input | Min 1 required |

### 2.2 Section B — Benefit Definition Matrix

For each benefit category row:

| Column | Editable | Type | Validation |
|--------|----------|------|------------|
| Allowed | Yes | Toggle | — |
| Min (max allowed) | Yes (if allowed) | Number | ≥ 0, ≤ medium |
| Medium | Yes (if allowed) | Number | ≥ min, ≤ extensive |
| Extensive | Yes (if allowed) | Number | ≥ medium, ≤ premium |
| Premium | Yes (if allowed) | Number | ≥ extensive |
| Unit | Yes | Select | currency, days, weeks, months, % |
| Currency | Yes (if unit=currency) | Select | NOK, USD, GBP, SGD, EUR |
| Documentation required | Yes | Multi-select / Tags | — |
| Pre-approval required | Yes | Checkbox | — |
| Notes | Yes | Textarea | Optional |
| Support doc link | Yes | URL | Optional |

**UI behavior:**
- When `allowed=false`, all tier fields and unit/currency are hidden or disabled.
- Tier fields must respect: `min ≤ medium ≤ extensive ≤ premium`.

### 2.3 Section C — Policy Rules

| Rule type | Editable | UI |
|-----------|----------|-----|
| Jurisdiction overrides | Yes | Add country → define overrides (same structure as benefit matrix) |
| Per-band exceptions | Yes | Table: Band × Assignment Type × Benefit overrides |
| Reimbursement rules | Yes | Rich text / markdown |
| Repayment clauses | Yes | Rich text / markdown |
| Conditional dependencies | Yes | Rule builder: "Benefit X only if [benefit Y accepted]" |

### 2.4 Section D — Save & Publish

| Action | Behavior |
|--------|----------|
| Save draft | Validate schema, persist, status=draft |
| Publish | Validate all rules, bump version, status=published |
| Validate schema | Run all validation rules, show errors |
| Notify entities | Optional: trigger notification to relevant employees |

### 2.5 Business Rules (HR View)

1. `maxAllowed.min` must be ≥ policy-defined minimum per assignment type.
2. If `allowed=false`, all tier fields for that benefit are hidden/disabled.
3. Policy must have at least one assignment type.
4. Tiers must be non-decreasing: `min ≤ medium ≤ extensive ≤ premium`.
5. Policy must have at least one benefit with `allowed=true`.

---

## 3. Employee Profile — Read-Only View & Service Eligibility

### 3.1 Section A — Applicable Policy Summary

| Display | Source |
|---------|--------|
| Employee band | `employee.band` |
| Assignment type | `assignment.type` |
| Country | `assignment.destination` or `policy.jurisdictionOverrides` |
| Policy effective date | `policy.effectiveDate` |
| Allowed benefits table | Filtered by band + assignment type + jurisdiction |

**Table columns:** Benefit name | Min | Medium | Extensive | Premium | Pre-approval | Documentation required

### 3.2 Section B — Allowed Choices UI

For each service category where `allowed=true`:

| Element | Behavior |
|---------|----------|
| Service options | Filter by tier ranges (min/med/ext/prem) |
| Explanatory text | From policy: "Maximum traveling allowance: $X" |
| Disabled services | Greyed out, tooltip: "Not available under your policy" |
| Contextual tips | From `policy.notes` or `supportDocUrl` |

**Example copy:**
- "Housing options must be submitted before arrival"
- "Dependent visas are covered under this policy"
- "Pre-approval required for shipment above $X"

### 3.3 Section C — Required Policy Rules to Accept

Checkboxes with clear text (enforced before submission):
- "I understand pre-approval is required for rental deposit reimbursement"
- "I accept that documentation must be provided within 30 days"

### 3.4 Employee Notifications

- Alert if user selects a service above allowed tier.
- Show currency conversion if employee locale differs from policy currency.

---

## 4. Service Recommendation Logic (DSL / JSON Logic)

### 4.1 Eligibility Rule

```json
{
  "and": [
    { "==": [{ "var": "benefit.allowed" }, true] },
    { "in": [{ "var": "employee.band" }, { "var": "policy.employeeBands" }] },
    { "in": [{ "var": "assignment.type" }, { "var": "policy.assignmentTypes" }] }
  ]
}
```

### 4.2 Present Benefit with Max Values

```
IF eligibility_rule THEN
  resolved_benefit = resolve_override(benefit, employee.band, assignment.type, assignment.destinationCountry)
  present_benefit:
    min: resolved_benefit.maxAllowed.min
    medium: resolved_benefit.maxAllowed.medium
    extensive: resolved_benefit.maxAllowed.extensive
    premium: resolved_benefit.maxAllowed.premium
    currency: resolved_benefit.currency
    documentationRequired: resolved_benefit.documentationRequired
    preApprovalRequired: resolved_benefit.preApprovalRequired
ELSE
  hide_benefit
```

### 4.3 Resolution Order (Overrides)

1. `jurisdictionOverrides[countryCode]` for assignment destination
2. `bandAssignmentRules[band_assignmentType]`
3. Fallback to `bandAssignmentRules[fallbackBand_assignmentType]` if defined
4. Base `benefitCategories[benefitKey]`

### 4.4 Conditional Dependencies

```
IF benefit = "spousalSupport" AND assignment.type IN ["Permanent","Long-Term"]
  THEN allow
ELSE hide
```

```json
{
  "conditionalDependencies": [
    {
      "benefit": "rentalAssistance",
      "requires": ["settlingInAllowance"],
      "condition": "rentalAssistance only if settlingInAllowance accepted"
    }
  ]
}
```

---

## 5. Input Validation & Errors

| Rule | Error message |
|------|---------------|
| Missing required max values | "Tier values (min, medium, extensive, premium) are required when benefit is allowed" |
| Wrong currency | "Currency must be one of NOK, USD, GBP, SGD, EUR" |
| Overlapping tiers (e.g. extensive < medium) | "Tier values must be non-decreasing: min ≤ medium ≤ extensive ≤ premium" |
| Policy has no benefits | "Policy must contain at least one allowed benefit" |
| No assignment type | "Policy must have at least one assignment type" |
| Max below policy minimum | "Maximum allowed cannot be lower than policy minimum for this assignment type" |
| Employee view edit attempt | "Employee view is read-only" |

---

## 6. Example Outputs

### 6.1 Example Filled HR Policy JSON

```json
{
  "policyId": "550e8400-e29b-41d4-a716-446655440000",
  "version": 2,
  "policyName": "Global Relocation Policy 2024",
  "companyEntity": "NOR-INV-001",
  "effectiveDate": "2024-01-01",
  "expiryDate": null,
  "status": "published",
  "employeeBands": ["Band1", "Band2", "Band3", "Band4"],
  "assignmentTypes": ["Permanent", "Long-Term", "Short-Term"],
  "benefitCategories": {
    "preAssignmentVisit": {
      "allowed": true,
      "maxAllowed": { "min": 1500, "medium": 3000, "extensive": 5000, "premium": 8000 },
      "unit": "currency",
      "currency": "USD",
      "documentationRequired": ["Travel receipts", "Approval email"],
      "preApprovalRequired": false,
      "notes": "Covers flights and accommodation for pre-assignment visit."
    },
    "travel": {
      "allowed": true,
      "maxAllowed": { "min": 3000, "medium": 6000, "extensive": 10000, "premium": 15000 },
      "unit": "currency",
      "currency": "USD",
      "documentationRequired": ["Flight receipts", "Boarding passes"],
      "preApprovalRequired": true
    },
    "temporaryHousing": {
      "allowed": true,
      "maxAllowed": { "min": 3000, "medium": 5000, "extensive": 7000, "premium": 10000 },
      "unit": "currency",
      "currency": "USD",
      "documentationRequired": ["Lease agreement", "Receipts"],
      "preApprovalRequired": true
    },
    "shipment": {
      "allowed": true,
      "maxAllowed": { "min": 5000, "medium": 10000, "extensive": 15000, "premium": 25000 },
      "unit": "currency",
      "currency": "USD",
      "documentationRequired": ["Vendor quote", "Inventory list"],
      "preApprovalRequired": true
    },
    "spousalSupport": {
      "allowed": true,
      "maxAllowed": { "min": 2000, "medium": 5000, "extensive": 8000, "premium": 12000 },
      "unit": "currency",
      "currency": "USD",
      "documentationRequired": ["Spouse CV", "Job search evidence"],
      "preApprovalRequired": true,
      "notes": "Only for Permanent and Long-Term assignments."
    }
  },
  "bandAssignmentRules": {
    "Band1_Permanent": {
      "benefitOverrides": {
        "shipment": {
          "allowed": true,
          "maxAllowed": { "min": 8000, "medium": 15000, "extensive": 20000, "premium": 30000 }
        }
      }
    }
  },
  "jurisdictionOverrides": {
    "SG": {
      "countryCode": "SG",
      "overrideBenefitCategories": {
        "temporaryHousing": {
          "allowed": true,
          "maxAllowed": { "min": 4000, "medium": 6000, "extensive": 9000, "premium": 12000 },
          "currency": "SGD"
        }
      },
      "notes": "Singapore cost-of-living adjustment"
    }
  },
  "conditionalDependencies": [
    {
      "benefit": "rentalAssistance",
      "requires": ["settlingInAllowance"],
      "condition": "Rental assistance only available if settling-in allowance is accepted"
    }
  ]
}
```

### 6.2 Example Employee View Rendered JSON

```json
{
  "employeeId": "emp-001",
  "band": "Band2",
  "assignment": {
    "type": "Long-Term",
    "destination": "Singapore",
    "countryCode": "SG"
  },
  "applicablePolicy": {
    "policyId": "550e8400-e29b-41d4-a716-446655440000",
    "effectiveDate": "2024-01-01"
  },
  "allowedBenefits": [
    {
      "key": "preAssignmentVisit",
      "label": "Pre-Assignment Visit",
      "allowed": true,
      "maxAllowed": { "min": 3000, "medium": 6000, "extensive": 5000, "premium": 8000 },
      "currency": "USD",
      "preApprovalRequired": false,
      "documentationRequired": ["Travel receipts", "Approval email"],
      "explanatoryText": "Maximum traveling allowance for pre-assignment visit: up to $8,000 USD (Premium tier)"
    },
    {
      "key": "temporaryHousing",
      "label": "Temporary Housing",
      "allowed": true,
      "maxAllowed": { "min": 4000, "medium": 6000, "extensive": 9000, "premium": 12000 },
      "currency": "SGD",
      "preApprovalRequired": true,
      "documentationRequired": ["Lease agreement", "Receipts"],
      "explanatoryText": "Singapore cost-of-living adjustment applies. Pre-approval required. Housing options must be submitted before arrival."
    }
  ],
  "acknowledgementsRequired": [
    {
      "id": "ack-1",
      "text": "I understand pre-approval is required for rental deposit reimbursement",
      "required": true
    },
    {
      "id": "ack-2",
      "text": "I accept that documentation must be provided within 30 days",
      "required": true
    }
  ]
}
```

---

## 7. Additional Considerations

### Scalability
- Design for multi-entity, multi-region policies
- Use `companyEntity` and `jurisdictionOverrides` for regional variations

### HR Manager Override
- Optional `overrideAccess` flag per HR role
- Override creates an exception record linked to the policy

### Version History & Comparison
- Store each published version with `version` and timestamp
- Comparison view: diff between two versions (benefit changes, tier changes)

### Audit Trail
- Log all changes in `auditTrail`
- Fields: timestamp, userId, action, changes (before/after)

### Help & Validation Hints
- Tooltips on tier labels (e.g. "Minimum = baseline package")
- Inline validation with clear error messages
- Link to support docs from `supportDocUrl`
