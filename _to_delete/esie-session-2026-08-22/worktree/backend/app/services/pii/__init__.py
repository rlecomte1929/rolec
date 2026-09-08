"""PII detection & redaction package.

Currently houses:
  - ``presidio_recognizers`` — custom Microsoft Presidio recognizers for the
    GDPR entities stock Presidio misses (IBAN, EU passports, national IDs,
    multilingual names). Built incrementally under epic AI-I.3.

The existing regex masker lives at ``backend/app/services/pii_masker.py``;
AI-I.3f wires this registry into it.
"""
