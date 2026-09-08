def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: Live integration tests that need external services (DB / Supabase); skip without env.",
    )
