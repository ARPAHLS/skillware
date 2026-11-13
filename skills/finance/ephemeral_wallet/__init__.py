# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

try:
    from .skill import EphemeralWalletSkill
except (ImportError, ValueError):
    from skill import EphemeralWalletSkill  # type: ignore

__all__ = ["EphemeralWalletSkill"]
