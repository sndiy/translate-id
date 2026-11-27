from id_translate.protect import (
    MARKUP_OPTIONS,
    check_tokens,
    has_translatable_text,
    mask,
    restore,
)


def test_placeholders_urls_emails_paths_are_masked_and_restored():
    src = (
        "Hello {name}, you have %d new messages (%1$s, %(count)s, {{total}}, ${HOME}). "
        "Visit https://example.com/a?b=1. Mail me@example.org or open C:\\Temp\\x.txt and /usr/local/bin."
    )
    masked, prot = mask(src)
    for literal in ["{name}", "%d", "%1$s", "%(count)s", "{{total}}", "${HOME}", "https://example.com/a?b=1",
                    "me@example.org", "C:\\Temp\\x.txt", "/usr/local/bin"]:
        assert literal in prot.values(), literal
        assert literal not in masked
    assert masked.count("⟦P") == len(prot)
    assert restore(masked, prot) == src


def test_url_trailing_punctuation_not_swallowed():
    masked, prot = mask("See https://example.com/x).")
    assert prot["⟦P1⟧"] == "https://example.com/x"
    assert masked.endswith(").")


def test_percent_in_prose_is_not_a_placeholder():
    masked, prot = mask("Save 20% today and 50 % tomorrow.")
    assert prot == {}
    assert masked == "Save 20% today and 50 % tomorrow."


def test_icu_plural_structure_masked_messages_translatable():
    src = "{count, plural, =0{No files} one{# file} other{# files in {folder}}}"
    masked, prot = mask(src)
    assert "No files" in masked and "file" in masked and "files in" in masked
    assert "plural" not in masked
    assert restore(masked, prot) == src
    assert all(v != src for v in prot.values())  # structure split into pieces, not one blob


def test_literal_brackets_are_protected():
    masked, prot = mask("Use ⟦this⟧ literally")
    assert "⟦" in prot.values() and "⟧" in prot.values()
    assert restore(masked, prot) == "Use ⟦this⟧ literally"


def test_markup_option_masks_tags_and_adjacent_spans_merge():
    masked, prot = mask("Press <b><i>Save</i></b> now", MARKUP_OPTIONS)
    assert masked == "Press ⟦P1⟧Save⟦P2⟧ now"
    assert prot["⟦P1⟧"] == "<b><i>"


def test_check_tokens_detects_missing_duplicate_unknown_and_order():
    assert check_tokens("a ⟦P1⟧ b ⟦P2⟧", "x ⟦P2⟧ y ⟦P1⟧") == []  # reordering placeholders is fine
    assert check_tokens("a ⟦P1⟧", "x")[0].startswith("missing")
    assert "unexpected" in check_tokens("a ⟦P1⟧", "⟦P1⟧ ⟦P1⟧")[0]
    assert "unexpected" in check_tokens("a", "⟦P9⟧")[0]
    assert "before" in check_tokens("⟦S1⟧a⟦/S1⟧", "⟦/S1⟧a⟦S1⟧")[0]


def test_has_translatable_text():
    assert not has_translatable_text("⟦P1⟧ 12,5 ⟦P2⟧ -")
    assert has_translatable_text("⟦P1⟧ halo")
