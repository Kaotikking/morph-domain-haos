# Morph Transfer Protocol v1

This is the normative Android/HAOS handoff contract for `serein.morph-transfer.v1`.

## Authority invariant

One Morph has one immutable lineage and one active authority. A recovery copy is inactive and is not ownership.

## Android to HAOS

1. Android creates and durably stores `transfer_id`, request, life snapshot, digest, lineage, generation, and recovery checkpoint.
2. Android calls `prepare`.
3. HAOS validates and records the offer while Android remains authority.
4. Android durably freezes local life.
5. Android calls `commit` with the exact prepared digest.
6. Android reads terminal status. Only `ACTIVE_HAOS` with authority `HAOS`, matching generation, and matching operation/current digest completes custody.
7. Android transitions its journal to inactive/away and retains recovery.

## HAOS to Android

1. Android creates and durably stores the exact `return_id` before any network request.
2. Android calls `prepare_return` with that ID, Morph ID, original source frame, and expiry.
3. HAOS freezes the current Morph and returns `RETURN_PREPARED` with the snapshot.
4. Android validates identity, lineage, generation, genome, and snapshot; then durably stages the snapshot inactive.
5. Android calls `commit_return` with the exact prepared snapshot digest.
6. HAOS changes authority to the original Android frame.
7. Android reads terminal `RETURNED_ANDROID` status with the snapshot, durably installs the returned life state, then activates locally.
8. Both endpoints reconcile Morph ID, lineage, generation, digest, authority, and presentation.

HAOS never creates or substitutes a destination `return_id`. A helper without an Android-supplied exact ID must fail before contacting HAOS.

## Terminal expiry

`RETURN_EXPIRED` is authenticated, snapshot-free cancellation evidence. After expiry HAOS may resume time, so:

- the operation `snapshot_digest` identifies the expired frozen offer;
- `current_snapshot_digest` identifies current HAOS life;
- those digests may legitimately differ;
- authority must be `HAOS`;
- Morph state must be `ACTIVE_DEFERRED_TICK`.

Android clears only the bound return attempt, retains recovery, stays inactive, and may start a new return with a new durably saved ID.

## Code Haven boundary

Code Haven is the only Morph DNA, state-migration, repair, and presentation-write boundary. Frame software defects—parsing, storage canonicalization, rendering, or adapters—are repaired in that frame's source. A Morph must not be rewritten to hide a frame defect.

## Acceptance gates

Report these independently:

- `CUSTODY_COMMITTED`: authoritative endpoint says the new owner holds the exact generation and digest.
- `DESTINATION_STATE_DURABLE`: destination readback proves the exact returned state is persisted.
- `DESTINATION_RENDER_VERIFIED`: the named physical/UI surface visibly renders that same Morph.

HTTP success, a transfer receipt, or custody success does not prove render success.

## Canonicalization

Validated private-state encodings must be normalized once. Recovery hashes, returned-tuple comparison, identity comparison, and render admission use the canonical encoding, never raw padded storage.

## Required public regressions

A release claiming Android transfer compatibility must publish and execute fixtures for:

1. destination-owned return ID;
2. lost prepare response and idempotent reconciliation;
3. interrupted commit;
4. expired return with changed current digest and no snapshot;
5. inactive staging before commit;
6. wrong lineage/target rejection;
7. duplicate and replay rejection;
8. custody success with render failure remaining unverified.

Until those fixtures and tests are present in the exact published tree, this repository is an implementation candidate, not the canonical Android contract proof source.
