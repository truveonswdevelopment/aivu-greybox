# `aivu_greybox` v0.1 — Section 12: Signing chain

**Status:** v1 draft, 2026-05-13. Anchored against §§1-11 (with §7 pending). §12 specifies the integration surface between `aivu_greybox` and `aivu_integrity`: the three function signatures `aivu_greybox` calls and the invariants on what gets signed at each call. Per the Phoenix-pivot scope-narrowing, only **per-packet HPM signing** and **local append-only signed log** are pilot-floor; the **MMR commitment primitive** and **2-of-3 threshold attestation** surfaces are spec'd in v0.1 but their implementation lives in `aivu_integrity` post-pilot work. The §12 interface contract is invariant across that deferral.

---

## 12.1 Position of §12 in the greybox spec

§1.3 names cryptographic infrastructure as out-of-scope for `aivu_greybox`: signing keys, MMR commitment primitives, OpenTimestamps anchoring, threshold attestation protocols, and external-verifier APIs are all `aivu_integrity`'s. What `aivu_greybox` owns is the call site: which records get signed, with which signing surface, at which protocol moment.

§12's job is to make that call site canonical. Three signing surfaces are consumed by `aivu_greybox`:

- **`sign_record(...)`** — Ed25519 per-packet signing of a single record (a telemetry packet, a Fan-Heat record, a posterior). Pilot-floor implementation.
- **`commit_to_log(...)`** — append the signed record to the HPM's local append-only signed log, return an inclusion proof against the log's current head. Pilot-floor implementation. MMR commitment to a publicly-anchored root is post-pilot per Workstream E.
- **`threshold_attest(...)`** — invoke the 2-of-3 threshold attestation protocol for a load-bearing artifact (a Digital Birth Certificate half-signing moment). Spec'd-but-deferred for v0.1; pilot ships without this surface live, returning a stub-attestation that the post-pilot `aivu_integrity` implementation replaces in place.

§§4, 5, 6, and 8 all call into one or more of these surfaces. §12 names the call pattern at each call site so a code reviewer sees the full signing chain in one place.

---

## 12.2 The three function signatures

These are interface contracts, not implementations. The implementations live in `aivu_integrity`; `aivu_greybox` consumes them through the API surface defined here. Specific type signatures will land in v0.1 implementation code; the shape below is the architectural contract.

### 12.2.1 `sign_record`

```
sign_record(
    record: SignableRecord,
    key_role: KeyRole,
    timestamp: TimestampMonotonic,
) -> SignedRecord
```

Per-packet signature of a single record using the HPM's Ed25519 key for the named role. `SignableRecord` is the union type covering every record `aivu_greybox` emits: telemetry packets, Fan-Heat records (Pass and Fail), Day-2 / Day-5 posterior records, §8 identifiability reports (co-signed with their parent posterior, not separately), and any structurally similar future record.

`KeyRole` distinguishes the HPM's per-packet telemetry key from any other key roles `aivu_integrity` exposes (e.g., a future Clearinghouse-facing transport key). For v0.1, the pilot home's HPM has one telemetry signing key role; the parameter is named explicitly so v0.2's multi-role expansion does not require a function signature change.

`TimestampMonotonic` is the HPM's monotonic clock value at signing. Wall-clock is recorded separately in the record's payload; the monotonic value is what `aivu_integrity` uses for log-ordering and replay-protection.

The returned `SignedRecord` carries the original record bytes, the Ed25519 signature, the public-key fingerprint, the monotonic timestamp, and a content-addressed hash of the record. The hash is what downstream calls reference.

### 12.2.2 `commit_to_log`

```
commit_to_log(
    signed_record: SignedRecord,
) -> LogInclusionProof
```

Appends the signed record to the HPM's local append-only signed log, returns an inclusion proof against the log's current head. Pilot-floor implementation: structurally append-only (each entry references the previous entry's hash; log integrity is locally verifiable by re-walking the chain), with no MMR commitment to a publicly-anchored root in v0.1.

The `LogInclusionProof` is sufficient for an on-HPM verifier to confirm the record's position in the log; for an off-HPM external verifier, the proof composes with the post-pilot MMR commitment to produce an externally-verifiable inclusion. The interface returns the proof in both cases; the v0.1 pilot consumes the local-only half.

Append-only is enforced at the API level: there is no corresponding `remove_from_log` or `modify_record` surface. The log grows monotonically over the HPM's deployed lifetime; storage management is `aivu_integrity`'s concern, not `aivu_greybox`'s.

### 12.2.3 `threshold_attest`

```
threshold_attest(
    artifact: BirthCertificateHalf,
    moment: AttestationMoment,
) -> ThresholdAttestation
```

Invokes the 2-of-3 threshold attestation protocol for a Digital Birth Certificate half-signing moment. `BirthCertificateHalf` is one of: the Day-3 (Capacity, EER) signed map (HVAC half), the Day-2 posterior (envelope half, initial signing), or the Day-5 posterior (envelope half, final signing, superseding Day-2). `AttestationMoment` identifies which of the three signing moments is being attested.

In v0.1, the implementation lives in `aivu_integrity` v0.1's spec but is *deferred* in execution per the Phoenix-pivot. The pilot ships with `threshold_attest` returning a stub-attestation: the artifact is signed with the HPM key only (rather than co-signed by HPM + BDT + Clearinghouse against a DKG-distributed threshold), and the returned `ThresholdAttestation` carries an explicit "stub-attestation, post-pilot replacement required" flag in its payload.

This is the central architectural commitment of §12 for v0.1: **the function signature is invariant across the pilot / post-pilot transition.** Code emitting Digital Birth Certificate halves calls `threshold_attest` today; the implementation behind that call swaps from stub to live without any caller-side code change when the post-pilot `aivu_integrity` implementation lands.

---

## 12.3 Call sites in §§4, 5, 6, 8

Every place `aivu_greybox` produces a record that must be signed.

### §4 — Fan-Heat Consistency Check

- **`FanHeatPass` record:** `sign_record` → `commit_to_log`. No threshold attestation; Fan-Heat is a pre-condition record, not a Birth Certificate half.
- **`FanHeatFail` record:** `sign_record` → `commit_to_log`. Same pattern. The fail-mode flag is part of the signed payload; failure preservation is INV-FH-3.

### §5 — Day-1-2 passive batch fit

- **`Day2Posterior` record (including the co-signed §8 identifiability report per INV-ID8-1):** `sign_record` → `commit_to_log` → `threshold_attest(artifact, "envelope_half_initial")`. Three calls in sequence. The threshold attestation is the Digital Birth Certificate envelope-half-initial signing moment per §2.3.

### §6 — Day-4-5 active-perturbation batch fit

- **`Day5Posterior` record (including co-signed §8 identifiability report):** `sign_record` → `commit_to_log` → `threshold_attest(artifact, "envelope_half_final")`. Same three-call pattern, different attestation moment. Day-5 supersedes Day-2 as the home's commissioned envelope baseline per §2.3 and §6's closing note.

- **Day-3 (Capacity, EER) operating-point map (signed by Phase 2, consumed by §6):** §6 does not call `sign_record` on the Day-3 map; `aivu_physics` Phase 2 does that. But §6 verifies the Day-3 map's inclusion proof and threshold attestation before consuming it as `u_meas` per INV-FIT45-2. The verification path uses `aivu_integrity`'s read-side API, not §12's signing surface.

### §8 — Identifiability collapse detection

§8 does not emit its own signed records. The identifiability report co-travels with the §5 or §6 posterior as part of the same `SignableRecord` payload, so the §5 / §6 `sign_record` call covers both. §8 INV-ID8-4 makes the co-signing explicit: a flagged posterior is still signed; the flag is signed with it.

### Continuous

- **1 Hz telemetry packets:** `sign_record` → `commit_to_log`, every packet, throughout the 5-Day window and continuously thereafter in Phase 2 ongoing-Cx. The cadence is the HPM heartbeat per §3.2; the per-packet signing-plus-MMR-append budget is included in the 100 ms per-cycle ceiling.

---

## 12.4 Invariants

**INV-SIGN12-1 — Every record `aivu_greybox` emits MUST be signed before it leaves the package boundary.** No record is emitted unsigned. The records covered are: telemetry packets (continuous), Fan-Heat Pass/Fail records (§4), Day-2 posterior records (§5), Day-5 posterior records (§6), and the §8 identifiability reports co-signed with their parent posterior. Implementations that emit any of these records without invoking `sign_record` are non-compliant.

**INV-SIGN12-2 — Every signed record MUST be appended to the local signed log before being consumed by a downstream call site.** `sign_record` and `commit_to_log` are paired; signing without appending leaves the record unverifiable to any later consumer. The sequence is `sign_record` → `commit_to_log`, not reversed and not separated.

**INV-SIGN12-3 — Birth Certificate half-signing moments MUST invoke `threshold_attest` with the correct `AttestationMoment` identifier.** Three moments exist: Day-3 HVAC half, Day-2 envelope-initial, Day-5 envelope-final. Each is identified by its enum value; the value is part of the threshold-attestation payload. Wrong-moment attestation (signing the Day-2 posterior with the `envelope_half_final` moment label) is non-compliant.

**INV-SIGN12-4 — The stub-attestation flag MUST be honest.** v0.1 pilot ships with `threshold_attest` returning stub-attestation. The returned `ThresholdAttestation` payload MUST carry the "stub-attestation, post-pilot replacement required" flag visible to any consumer parsing the record. A v0.1 implementation that emits a stub-attestation without the flag is non-compliant. The flag does NOT block use of the artifact during the pilot; it ensures that any consumer downstream can distinguish stub from live attestation.

**INV-SIGN12-5 — The signing interface is invariant across the v0.1 → post-pilot transition.** `aivu_greybox` code that calls `sign_record`, `commit_to_log`, or `threshold_attest` MUST NOT need modification when `aivu_integrity`'s post-pilot implementation lands. The function signatures pin this. Implementation swaps happen inside `aivu_integrity`; greybox code is unaware.

**INV-SIGN12-6 — Inclusion proofs MUST be retrievable post-hoc.** Any signed record committed to the local log MUST remain retrievable (by content-addressed hash) for the deployed lifetime of the HPM. Storage-management policy (rotation, archival, post-pilot anchoring) lives in `aivu_integrity`; the retrieval contract from `aivu_greybox`'s perspective is "indefinitely available."

**INV-SIGN12-7 — Monotonic timestamps MUST be strictly increasing within a single HPM's log.** Two records with the same monotonic timestamp (or with non-increasing timestamps) constitute a log corruption. The HPM's monotonic clock guarantees strict ordering; the invariant makes this part of the API contract so `aivu_integrity` can rely on it for replay-protection without separate clock-validation logic in `aivu_greybox`.

---

## 12.5 What §12 does not do

- **Does not specify the cryptographic primitives.** Ed25519, the MMR hash function, the threshold-attestation scheme — all live in `aivu_integrity`'s spec. §12 specifies the call surface, not the math.
- **Does not specify key management.** Key generation, DKG ceremony, rotation policy, revocation, and recovery from key compromise are all `aivu_integrity` concerns. §12 names `KeyRole` as a parameter; what a role means and how its key is produced are out of scope here.
- **Does not specify post-pilot anchoring.** OpenTimestamps anchoring to Bitcoin, MMR root publication cadence, and external-verifier transport are all post-pilot work in `aivu_integrity`.
- **Does not specify the local log's storage format.** On-disk representation, write-amplification policy, rotation, and recovery-from-corruption policies are `aivu_integrity`'s. §12 specifies the append-only API and the inclusion-proof return type, not the bytes on disk.
- **Does not specify external-verifier APIs.** The Clearinghouse / insurer / external-verifier interfaces to the signed records are downstream concerns. §12 specifies what gets signed and how to retrieve a signed record by hash; the API a third party hits to verify is `aivu_integrity`'s.

---

## 12.6 Out of scope

The following are explicitly out of §12 v0.1:

- **Threshold attestation live implementation.** Stub-attestation ships for the pilot per Phoenix-pivot scope-narrowing. The v0.1 spec carries the function signature and the stub-attestation flag; the live 2-of-3 protocol is post-pilot `aivu_integrity` work.
- **MMR commitment to a publicly-anchored root.** Local append-only log ships for the pilot. MMR commitment + OpenTimestamps anchoring are post-pilot.
- **Multi-HPM cohort attestation.** v0.1 covers one pilot home with one HPM. Cohort-level signing patterns (e.g., a Clearinghouse attestation across N homes' Birth Certificates) are post-pilot.
- **Revocation of a previously-signed record.** Append-only forbids this by construction. The architecture for handling a discovered error in a signed posterior is: emit a corrective record that supersedes the previous one, with the supersession relationship signed into the new record. This pattern is `aivu_integrity`'s to specify, not §12's.
- **Backward-compatible decryption of v0.1 records under post-pilot key rotation.** Long-term-retention semantics under key rotation are an `aivu_integrity` v0.2+ concern.

---

*End of §12 v1 draft. Three signing surfaces named (`sign_record`, `commit_to_log`, `threshold_attest`) with interface contracts pinned. Two of three surfaces ship with pilot-floor implementations (per-packet signing, local append-only log); the third (`threshold_attest`) ships with stub-attestation behind the invariant function signature, replaceable in place when post-pilot `aivu_integrity` lands. Seven invariants emitted (INV-SIGN12-1 through INV-SIGN12-7) covering signing-before-emission, signing-paired-with-logging, attestation-moment correctness, stub-attestation honesty, interface invariance across the transition, post-hoc retrievability, and monotonic-timestamp strict ordering. Call sites in §§4, 5, 6, 8 enumerated. §12 closes `aivu_greybox` v0.1 spec; §10 test plan covers §12 invariants via signed-record verification tests already enumerated in §10.5.*
