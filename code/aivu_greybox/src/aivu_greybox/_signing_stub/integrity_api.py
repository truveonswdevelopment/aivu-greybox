"""Stub implementations of the three §12 signing surfaces.

Function signatures match the §12 spec exactly. Implementations are stubs:
they produce synthetic signatures and an in-memory log. They are NOT
cryptographically meaningful and MUST be replaced by the real
`aivu_integrity` implementation before any pilot data leaves the HPM.

The stub is sufficient to exercise the call pattern, the record schema,
and §10 coverage tests; it is NOT sufficient for actual cryptographic
integrity.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class KeyRole(Enum):
    """HPM key roles. v0.1 uses a single role; the parameter is named so
    v0.2 multi-role expansion does not require a function-signature change."""

    TELEMETRY = "telemetry"


class AttestationMoment(Enum):
    """The three Birth Certificate half-signing moments per §12.2.3."""

    HVAC_HALF = "hvac_half"
    ENVELOPE_HALF_INITIAL = "envelope_half_initial"
    ENVELOPE_HALF_FINAL = "envelope_half_final"
    # Post-commissioning event-driven significance event per §7.3.3
    POST_COMMISSIONING_SIGNIFICANCE_EVENT = "post_commissioning_significance_event"


# ---------------------------------------------------------------------------
# Type aliases — the signed-record protocol
# ---------------------------------------------------------------------------

# Any record produced by aivu_greybox that needs signing. The schema is
# defined by the producer (records.py); the signing stub treats it as opaque
# bytes-with-metadata.
SignableRecord = dict[str, Any]


@dataclass(frozen=True)
class TimestampMonotonic:
    """HPM monotonic clock value at signing.

    Per §12 INV-SIGN12-7, monotonic timestamps MUST be strictly increasing
    within a single HPM's log.
    """

    nanoseconds: int

    @classmethod
    def now(cls) -> "TimestampMonotonic":
        """Capture the current monotonic clock value."""
        return cls(nanoseconds=time.monotonic_ns())


@dataclass(frozen=True)
class SignedRecord:
    """A record after passing through sign_record().

    Per §12.2.1: carries the original record bytes, the Ed25519 signature
    (synthetic in the stub), the public-key fingerprint (synthetic),
    monotonic timestamp, and a content-addressed hash that downstream
    calls reference.
    """

    record: SignableRecord
    signature: bytes
    public_key_fingerprint: str
    monotonic_timestamp: TimestampMonotonic
    record_hash: str  # SHA-256 hex digest of the record's canonical serialization
    key_role: KeyRole
    is_stub_signature: bool = True  # honesty per the stub discipline


@dataclass(frozen=True)
class LogInclusionProof:
    """Returned by commit_to_log().

    Per §12.2.2: sufficient for an on-HPM verifier to confirm the record's
    position in the log; composes with the post-pilot MMR commitment to
    produce externally-verifiable inclusion.
    """

    record_hash: str
    log_index: int
    log_head_hash_at_append: str
    previous_record_hash: str | None  # None only for the genesis entry
    is_stub_proof: bool = True


@dataclass(frozen=True)
class ThresholdAttestation:
    """Returned by threshold_attest().

    Per §12.2.3: v0.1 pilot ships with stub-attestation. The payload MUST
    carry the "stub-attestation, post-pilot replacement required" flag
    visible to any consumer (INV-SIGN12-4).
    """

    artifact_hash: str
    moment: AttestationMoment
    monotonic_timestamp: TimestampMonotonic
    stub_signatures: tuple[bytes, ...]  # one per stub party (HPM, BDT, Clearinghouse)
    post_pilot_replacement_required: bool = True  # INV-SIGN12-4


# ---------------------------------------------------------------------------
# The in-memory append-only log
# ---------------------------------------------------------------------------


@dataclass
class _InMemoryLog:
    """Stub implementation of the local append-only signed log.

    Replace with the real `aivu_integrity` log when post-pilot work lands.
    The append-only contract is enforced at the API level: there is no
    `remove` or `modify` operation surfaced.
    """

    entries: list[SignedRecord] = field(default_factory=list)
    head_hash: str = "GENESIS"

    def append(self, signed: SignedRecord) -> LogInclusionProof:
        # Enforce strict-monotonic timestamps per INV-SIGN12-7
        if self.entries:
            last_ts = self.entries[-1].monotonic_timestamp.nanoseconds
            if signed.monotonic_timestamp.nanoseconds <= last_ts:
                raise ValueError(
                    f"Monotonic timestamp violation per INV-SIGN12-7: new record "
                    f"timestamp {signed.monotonic_timestamp.nanoseconds} ns is "
                    f"not strictly greater than previous {last_ts} ns."
                )

        prev_hash = self.entries[-1].record_hash if self.entries else None
        index = len(self.entries)
        self.entries.append(signed)
        # Update head as hash of (previous_head + new_record_hash)
        self.head_hash = hashlib.sha256(
            f"{self.head_hash}|{signed.record_hash}".encode("utf-8")
        ).hexdigest()
        return LogInclusionProof(
            record_hash=signed.record_hash,
            log_index=index,
            log_head_hash_at_append=self.head_hash,
            previous_record_hash=prev_hash,
            is_stub_proof=True,
        )

    def retrieve_by_hash(self, record_hash: str) -> SignedRecord | None:
        """INV-SIGN12-6: inclusion proofs MUST be retrievable post-hoc."""
        for entry in self.entries:
            if entry.record_hash == record_hash:
                return entry
        return None


_log = _InMemoryLog()


# ---------------------------------------------------------------------------
# The three §12 surfaces
# ---------------------------------------------------------------------------


def _canonical_serialize(record: SignableRecord) -> bytes:
    """Deterministic serialization for hashing.

    Real implementation will be canonical JSON or a structured wire format
    agreed with `aivu_integrity`. Stub uses Python's `repr` with sorted
    keys at the top level — enough for in-process consistency, NOT enough
    for cross-platform bit-identity per §3.3 reproducibility commitment.
    """
    items = sorted(record.items()) if isinstance(record, dict) else [("_", record)]
    return repr(items).encode("utf-8")


def sign_record(
    record: SignableRecord,
    key_role: KeyRole = KeyRole.TELEMETRY,
    timestamp: TimestampMonotonic | None = None,
) -> SignedRecord:
    """§12.2.1 — per-packet Ed25519 signature of a single record.

    Stub: returns a synthetic signature derived from the record's hash.
    """
    if timestamp is None:
        timestamp = TimestampMonotonic.now()

    serialized = _canonical_serialize(record)
    record_hash = hashlib.sha256(serialized).hexdigest()

    # Synthetic "signature": HMAC-like construction over (record_hash + role)
    stub_sig = hashlib.sha256(
        f"STUB_SIG|{record_hash}|{key_role.value}".encode("utf-8")
    ).digest()
    stub_fingerprint = hashlib.sha256(b"STUB_PUBLIC_KEY").hexdigest()[:16]

    return SignedRecord(
        record=record,
        signature=stub_sig,
        public_key_fingerprint=stub_fingerprint,
        monotonic_timestamp=timestamp,
        record_hash=record_hash,
        key_role=key_role,
        is_stub_signature=True,
    )


def commit_to_log(signed_record: SignedRecord) -> LogInclusionProof:
    """§12.2.2 — append the signed record to the local append-only log.

    Stub: in-memory log only. No MMR commitment; the real implementation
    composes the inclusion proof with a public anchor.
    """
    return _log.append(signed_record)


def threshold_attest(
    artifact: SignableRecord,
    moment: AttestationMoment,
) -> ThresholdAttestation:
    """§12.2.3 — invoke 2-of-3 threshold attestation for a Birth Certificate
    half-signing moment (or post-commissioning significance event).

    Stub: produces three synthetic per-party signatures plus the explicit
    post-pilot-replacement-required flag per INV-SIGN12-4. The artifact
    is NOT cryptographically attested by an actual DKG-distributed threshold
    in v0.1; the stub exists to exercise the call pattern.
    """
    serialized = _canonical_serialize(artifact)
    artifact_hash = hashlib.sha256(serialized).hexdigest()

    # Three synthetic per-party signatures: HPM, BDT, Clearinghouse
    parties = ("HPM", "BDT", "CLEARINGHOUSE")
    stub_sigs = tuple(
        hashlib.sha256(
            f"STUB_THRESHOLD|{party}|{artifact_hash}|{moment.value}".encode("utf-8")
        ).digest()
        for party in parties
    )

    return ThresholdAttestation(
        artifact_hash=artifact_hash,
        moment=moment,
        monotonic_timestamp=TimestampMonotonic.now(),
        stub_signatures=stub_sigs,
        post_pilot_replacement_required=True,  # INV-SIGN12-4
    )


# ---------------------------------------------------------------------------
# Test/debug helpers — not part of the §12 API surface
# ---------------------------------------------------------------------------


def _reset_log_for_testing() -> None:
    """Clear the in-memory log. Test-suite only."""
    global _log
    _log = _InMemoryLog()


def _retrieve_by_hash_for_testing(record_hash: str) -> SignedRecord | None:
    """Look up a record by hash. Test-suite only (INV-SIGN12-6 verification)."""
    return _log.retrieve_by_hash(record_hash)
