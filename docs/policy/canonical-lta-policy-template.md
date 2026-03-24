# Canonical long-term assignment (LTA) policy template

## Purpose

ReloPass uses a **fixed canonical template** for long-term assignment policies so that:

- Uploaded PDFs/DOCX are **mapped into known slots**, not used to invent a new ontology each time.
- HR sees **consistent sections** and can **fill gaps** where extraction missed a field.
- **Comparison** (e.g. company vs benchmark) can target fields marked `drives_comparison`.

The template is defined in code: `backend/services/policy_canonical_lta_template.py`.

## The “~90%” idea

Real policies differ in wording, order, and legal packaging. This template is **opinionated** and aims to cover **most** international LTA programs:

- **Eligibility, move, allowances, family, tax, leave, repatriation, governance** appear in almost every serious program.
- The remaining **10%** is company-specific (e.g. club memberships, club cars, equity, special host countries). Those map to **narrative** rows, **HR notes**, or future template versions—not ad-hoc keys per upload.

## Top-level domains

1. Eligibility and scope  
2. Pre-departure support  
3. Move logistics  
4. Compensation and payroll  
5. Assignment allowances and premiums  
6. Family support  
7. Leave and travel during assignment  
8. Repatriation  
9. Governance, approvals, and external dependencies  

## Field metadata (per row)

| Attribute | Meaning |
|-----------|---------|
| `key` | Stable snake_case id for APIs and mapper targets |
| `domain_id` | One of the nine domains above |
| `value_type` | `amount` \| `duration` \| `quantity` \| `percentage` \| `narrative` \| `external_reference` — primary UI/comparison hint |
| `applicability` | Typical axes: employee, spouse/partner, children, family, assignment type |
| `drives_comparison` | Include in automated policy comparison when populated |
| `employee_visible_label` | Copy-safe label for employee-facing summaries |
| `maps_to_benefit_taxonomy_key` | Optional link to `policy_taxonomy.BENEFIT_TAXONOMY` for the current normalization engine |

## Using the template

- **Mapper**: resolve extracted clauses → `maps_to_benefit_taxonomy_key` where set; otherwise attach to `key` for HR queue.  
- **APIs / UI**: `canonical_lta_template_as_jsonable()` exposes the full structure for review screens and gap lists.  
- **Evolution**: add fields with new keys; avoid renaming keys once customers depend on them (migrate if needed).
