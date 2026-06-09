"""backend.db — domain-split extraction of the monolithic backend/database.py.

[AUDIT-C1.2+] Each module here holds one domain's DB methods as a mixin that the
`Database` class inherits, so existing callers keep working unchanged via MRO.
See audit/database_inventory.md for the domain map and extraction order.
"""
