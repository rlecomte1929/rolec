"""Corridor Candidate Beam — multi-pass authoring pipeline (generation only).

Deliberately under `backend/imports/`, alongside the Otto loader, and NOT under any
serving root. Nothing in this package may be imported by `requirements_builder`,
`rules_engine`, `requirement_evaluation_service`, `immigration_requirement_service` or
`hr_policy_resolver` — the beam calls an LLM, and a serving path that can reach an LLM is
a serving path that can invent a compliance requirement at request time. Enforced by
`scripts/check_serving_llm_isolation.py`.
"""
