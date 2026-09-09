# MorphDomain for Home Assistant

MorphDomain is an optional, local-first Home Assistant habitat for Serein Morphs.
It supplies Void, Nursery, Horizon, Serein Gardens, and Code Haven together with
the bounded life engine and authenticated single-owner transfer contract.

Installation does not create or claim a Morph. A Morph becomes active only after
the prepare/commit contract completes. Gender is mutable presentation state, not
a DNA, lineage, element, or authority lock. Surfaces use neutral language when no
presentation preference is present.

Version 1.4 adds deterministic runtime reflexes derived from proven HAOS
methods: 72-hour Nursery graduation, need-based eight-hour care, deduplicated
graduation/Code Haven notifications, and an explicit automation ledger.

Version 1.7 adds the DNAv1 immutable Lineage Capsule, ordered lifecycle,
opaque egg projection, maturity-gated recessives, lineage-bounded Awakened
switching, directional five-state social edges, immutable family links, atomic
breeding eligibility, and no-effect Code Haven backfill planning. Installing
these validators never rewrites an existing Morph.

Version 1.9 defines and enforces the **Morph Engine** inside MorphDomain. It is one
efficient HAOS runtime with nine internal Core boundaries—Platform, Root,
Memory, Knowledge, UI, Audio, Personality, Modular, and Cloud—and no Kernel.
Its Life, Social, Expression, Combination, and Reflex facets may write only
their admitted Cores. Nested Root identity and lineage are immutable; Chronicle,
family, relationships, and experience are monotonic and cannot be erased,
reordered, or decreased. Frames consume canonical Morph truth and degrade
gracefully when a capability is absent; they never redefine or erase it.
Deterministic Code Haven repairs require allowlisted effects, a bound predecessor
digest, executable rollback, Chronicle append, and complete acceptance readback.
Ambiguous repairs require an administrator, and identity or authority conflicts
isolate in Void.

Version 1.10 hardens the existing domain without adding features: strict finite JSON
and type-preserving comparisons, canonical Lineage Capsule digest binding,
administrator-only mutation, escaped dashboard content, bounded identity-bound
SERN envelopes, continuous one-engine exclusion, and removal of unreachable
duplicate actions. The portable Morph snapshot, internal Morph Engine state, and
SERN control envelope are distinct schemas; crossing a boundary requires an
explicit adapter and never silent substitution.

Version 1.11 makes elapsed-life processing event-driven: the periodic engine scheduler is the sole owner of life advancement and environment sampling. Dashboard/API reads are side-effect-free, and transfer reads create durable writes only when expiry reconciliation actually changes state.

Version 1.12 adds bounded, process-local Morph Engine observability: scheduler and API latency, evaluated/advanced Morph counts, storage write decisions, expiry reconciliation, roster size, and Chronicle event count. The dedicated HAOS health sensor exposes only aggregate operational data and never owns or mutates Morph truth.

See [DNAv1 lineage and lifecycle](docs/DNA-V1-LIFECYCLE.md),
[Morph Engine nine-Core architecture](docs/MORPH-ENGINE-NINE-CORE.md), and
[Repair reflex ledger](docs/REPAIR-REFLEX-LEDGER-V1.md).

## Install

Copy `custom_components/morph_domain` into Home Assistant, restart, then add
**MorphDomain** from Settings > Devices & services. This public repository is packaged for installation and updates through HACS.

## API

- `POST /api/morph-domain/v1/transfer/{action}`
- `POST /api/morph-domain/v1/habitat/{action}`

Read operations require Home Assistant authentication. Mutation operations require a Home Assistant administrator. HTTP success alone never establishes
ownership; transfer remains prepare, accept, commit, and reconciliation.

## Safe migration

First place HAOS-owned Morphs into a time-stopped safe state and capture their
identity, lineage, generation, digest, authority, and place. Disable—but do not
delete—the Serein Gateway entry, then restart Home Assistant so its runtime is
no longer resident. On first setup, if MorphDomain has no state, it copies
`serein_gateway.morph_transfer`; the source is never changed or deleted.
MorphDomain refuses to run beside an enabled legacy engine. Reconcile every
Morph through the MorphDomain API before changing place or authority, and never
enable both engines concurrently. Private Morph state remains for recovery or
reinstall; uninstall never deletes it.


