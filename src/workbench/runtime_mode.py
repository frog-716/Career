"""Fail-closed runtime mode for local Career instances."""

from __future__ import annotations

import os
from dataclasses import dataclass


LOCAL_ONLY = "LOCAL_ONLY"
AI_ENABLED = "AI_ENABLED"
_ENV_NAME = "CAREER_AI_MODE"
_UNSET = object()


class RuntimeModeError(ValueError):
    """The launcher was not given an explicit, supported AI mode."""


@dataclass(frozen=True)
class RuntimeMode:
    value: str
    explicit: bool
    valid: bool
    raw: str | None

    @property
    def local_only(self) -> bool:
        return self.value == LOCAL_ONLY

    @property
    def ai_enabled(self) -> bool:
        return self.value == AI_ENABLED and self.valid


def resolve_runtime_mode(raw=_UNSET) -> RuntimeMode:
    if raw is _UNSET:
        raw = os.environ.get(_ENV_NAME)
    if not isinstance(raw, str) or not raw.strip():
        return RuntimeMode(LOCAL_ONLY, explicit=False, valid=False, raw=raw)
    normalized = raw.strip().upper()
    if normalized in {LOCAL_ONLY, AI_ENABLED}:
        return RuntimeMode(normalized, explicit=True, valid=True, raw=raw)
    return RuntimeMode(LOCAL_ONLY, explicit=False, valid=False, raw=raw)


def startup_mode(raw=_UNSET) -> RuntimeMode:
    mode = resolve_runtime_mode(raw)
    if not mode.explicit or not mode.valid:
        raise RuntimeModeError(
            f"{_ENV_NAME} 必须显式设置为 {LOCAL_ONLY} 或 {AI_ENABLED}；未知值不会回退到真实 AI"
        )
    return mode


def require_ai_enabled(mode: RuntimeMode | None = None) -> RuntimeMode:
    current = mode or resolve_runtime_mode()
    if not current.ai_enabled:
        # Imported lazily so the provider module can use this module without a
        # circular import during process startup.
        from .providers import LocalOnlyDisabled

        raise LocalOnlyDisabled()
    return current


def require_secret_maintenance(mode: RuntimeMode | None = None) -> RuntimeMode:
    """Allow explicit secret maintenance without enabling any AI outbound."""

    current = mode or resolve_runtime_mode()
    if not current.valid:
        from .providers import LocalOnlyDisabled

        raise LocalOnlyDisabled()
    return current
