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

See [DNAv1 lineage and lifecycle](docs/DNA-V1-LIFECYCLE.md).

## Install

Copy `custom_components/morph_domain` into Home Assistant, restart, then add
**MorphDomain** from Settings > Devices & services. This layout is ready for HACS
once published as a public repository and released.

## API

- `POST /api/morph-domain/v1/transfer/{action}`
- `POST /api/morph-domain/v1/habitat/{action}`

Both require Home Assistant authentication. HTTP success alone never establishes
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


