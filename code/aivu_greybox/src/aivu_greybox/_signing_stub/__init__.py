"""Stub interfaces for `aivu_integrity` signing surfaces, per §12.

This module exists because `aivu_greybox` v0.1 ships before `aivu_integrity`'s
implementation lands. The stub:

  - Provides interfaces that exactly match the §12 function signatures
    (sign_record, commit_to_log, threshold_attest), so greybox code compiled
    against the stub does not require modification when the real
    `aivu_integrity` lands — per §12 INV-SIGN12-5 (signing interface
    invariance across v0.1 → post-pilot transition).
  - Returns synthetic ("stub") signatures and attestation payloads, with
    the stub-attestation flag set per INV-SIGN12-4 (stub-attestation
    honesty).

When the real `aivu_integrity` arrives, swap the imports in
`aivu_greybox._signing_stub.integrity_api` → `aivu_integrity.api` and no
other code changes.
"""

from .integrity_api import (
    AttestationMoment,
    KeyRole,
    LogInclusionProof,
    SignableRecord,
    SignedRecord,
    ThresholdAttestation,
    TimestampMonotonic,
    _reset_log_for_testing,
    _retrieve_by_hash_for_testing,
    commit_to_log,
    sign_record,
    threshold_attest,
)

__all__ = [
    "AttestationMoment",
    "KeyRole",
    "LogInclusionProof",
    "SignableRecord",
    "SignedRecord",
    "ThresholdAttestation",
    "TimestampMonotonic",
    "commit_to_log",
    "sign_record",
    "threshold_attest",
    # Test helpers — not part of the §12 API surface
    "_reset_log_for_testing",
    "_retrieve_by_hash_for_testing",
]
