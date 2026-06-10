"""Integrations adapters (I-4).

Thin, server-side adapters that turn a case's roadmap/deadlines into delivered
artifacts — an emailed plan (via the existing Resend transactional sender) and
an importable .ics calendar feed of the case's milestones. Provider keys stay
server-side; nothing here depends on agent-session MCP tooling (the product
backend cannot reach those at runtime).
"""
