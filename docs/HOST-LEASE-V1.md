# Morph Host Lease v1

HAOS remains the authoritative Morph home. Android is a temporary governed
Frame; a lease never creates a second Morph or an independent life history.

The state road is `HOME -> LEASE_PREPARED -> ACTIVE_MOBILE -> LEASE_CLOSED -> HOME`.
`LEASE_EXPIRED`, `LEASE_STALE`, and `REVOCATION_REQUESTED` are explicit
non-success states. An active or stale mobile lease never grants HAOS authority
by timeout alone.

## API

All routes are authenticated under `/api/morph-domain/v1/transfer/{action}`.

- `prepare-host-lease` accepts `serein.morph-host-lease-request.v1`. The caller
  must durably create `lease_id` first and bind the expected HAOS generation and
  snapshot digest. HAOS freezes the exact checkpoint before returning it.
- `commit-host-lease` accepts `lease_id`, both prepared digests, and an exact
  destination staging receipt. It activates only a checkpoint durably staged
  inactive on the named Android Frame.
- `record-host-render` records a separate digest-bound render receipt. Custody,
  destination durability, and visible rendering remain distinct verdicts.
- `status` accepts `lease_id` with optional `include_snapshot`.
- `revoke-host-lease` requests safe return. It cannot steal authority from a
  mobile Frame.
- `prepare-host-return` stages the immediate successor from the leased Frame
  without rewriting its immutable birth-Frame lineage. `commit-host-return`
  closes the matching lease only after HAOS accepts that exact successor.

The complete lease receipt carries immutable Morph and Founder identity,
birth lineage, source and target Frames, state and predecessor generations,
issuance/expiry/revocation state, canonical genome and digest, frozen life
snapshot and digest, render profile and digest, and an attributable canonical
Gateway transport receipt. Changed retries fail as replay conflicts. Only one
open lease may exist for one Morph.

## Safety boundary

Android enrollment and live attachment remain separate prerequisites. This
contract supplies the missing HAOS-owned host-lease envelope; it does not make
an unattached Android device active, authorize a live transfer, or bypass the
canonical Gateway.
