"""Exception hierarchy and process exit codes.

Exit codes (stable contract, documented in docs/cli.md):
    0  OK
    1  check failed (qa found errors, verify detected a changed file)
    2  usage error (bad arguments)
    3  input error (missing file, unsupported or malformed format)
    4  safety refusal (would overwrite, source changed, encrypted/DRM input)
    5  optional dependency missing
    6  validation error (missing translations, broken protect tokens)
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    FAILED = 1
    USAGE = 2
    INPUT = 3
    SAFETY = 4
    DEPENDENCY = 5
    VALIDATION = 6


class IdTranslateError(Exception):
    exit_code: ExitCode = ExitCode.FAILED


class UsageError(IdTranslateError):
    exit_code = ExitCode.USAGE


class InputError(IdTranslateError):
    exit_code = ExitCode.INPUT


class UnsupportedFormatError(InputError):
    pass


class SafetyError(IdTranslateError):
    exit_code = ExitCode.SAFETY


class OverwriteRefusedError(SafetyError):
    pass


class EncryptedInputError(SafetyError):
    pass


class DependencyMissingError(IdTranslateError):
    exit_code = ExitCode.DEPENDENCY


class ValidationError(IdTranslateError):
    exit_code = ExitCode.VALIDATION
