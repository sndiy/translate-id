"""id-translate: deterministic document plumbing for AI translation into Indonesian.

The model only translates text segments; this package extracts segments, protects
placeholders, re-applies translations into the original format, and checks safety
invariants (never overwrite, SHA-256 verification, refuse encrypted inputs).
"""

__version__ = "0.1.0"
