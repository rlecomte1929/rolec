# Self-test fixtures

`clean/` is a well-formed (if short) harvest. `dirty/` deliberately contains one instance of
every defect the gates exist to catch:

| row | defect | gate that must fire |
|---|---|---|
| 2 | `source_url` is a Google Maps place | `sourcing_rule` |
| 2 | `verification_method = registry_lookup` | `enum_discipline`, `schema` |
| 3 | `914 450 133` under "Law Society of Ireland" | `no_org_number_as_accreditation` |
| 3 | `source_url` host == `website_url` host | `source_not_own_site` |
| 4 | `service_category = relocation` | `enum_discipline`, `schema` |
| 4 | `source_url` is a bare `find-a-solicitor/` form | `evidence_url_not_search_form` |
| — | file/thread record sets differ | `thread_diff` |

To run the self-test, copy a fixture over the declared output path in a scratch checkout and
run `otto_verify.py`. `clean/` should pass every gate (G's CSV now allows a header-only file, so a short harvest
is legitimate);
`dirty/` should fail every gate in the table above.

If a gate stops firing after an edit, the gate is broken — not the fixture.
