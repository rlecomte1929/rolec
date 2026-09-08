"""One rule for "what is this field's label in the form's own language?".

A `form_templates.fields` entry carries an English `label` plus, optionally, a label in the
authority's language under a per-language key. RP-NO-DATASHEET seeded `label_nb`, and three
call sites — the field-values API, the data-sheet PDF, and the form editor — each read that
key by name.

That was fine while Norway was the only localised corridor and wrong the moment a second one
arrived: a `label_de` on a German sheet would have been silently ignored by all three, so the
DE/FR sheets would have rendered English labels with no error to notice. Hence one function,
keyed off `form_templates.source_language`, rather than a fourth hardcoded key.

The language is a property of the TEMPLATE, not of the viewer. `source_language` says which
language the authority's own form is in; it is not a user preference and not a locale.
"""
from typing import Any, Dict, Optional

# Languages we have a label key convention for. Mirrors the examples named in
# 20261017000000_autofill_prefill_provenance_and_source_language.sql. Adding a language means
# adding it here and to FieldLang in frontend/src/features/platform-v2/form-editor/FieldRow.tsx.
SUPPORTED_LABEL_LANGUAGES = ("nb", "de", "fr")


def label_key_for(source_language: Optional[str]) -> Optional[str]:
    """The `fields[].label_*` key holding labels for this template's language.

    Returns None for English and for anything unrecognised — English needs no second label,
    and guessing `label_xx` for an unknown code would invent a convention rather than follow
    one.
    """
    lang = (source_language or "").strip().lower()
    if lang in SUPPORTED_LABEL_LANGUAGES:
        return f"label_{lang}"
    return None


def localised_label(
    field_def: Dict[str, Any],
    source_language: Optional[str],
) -> Optional[str]:
    """This field's label in the template's own language, or None if there isn't one.

    None is meaningful, not a failure: the caller renders the English `label` instead (the PDF)
    or falls through to the translation service (the editor). Returning the English label here
    would make "seeded translation" and "machine translation" indistinguishable downstream, and
    the editor deliberately shows those differently — a seeded label is authoritative and
    instant, a translated one is best-effort and can degrade to English on a 503.
    """
    key = label_key_for(source_language)
    if not key:
        return None
    value = field_def.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
