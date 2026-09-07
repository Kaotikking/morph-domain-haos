# MorphDomain for Home Assistant

The HAOS integration is a transport and presentation adapter over the canonical
host-neutral `packages/morph-sdk` and `packages/morph-engine` sources. Its
vendored copy must remain byte-for-byte parity checked before release.

Code Haven is the sole presentation-write boundary. Every accepted revision
must produce a visible palette, silhouette, or marking change while immutable
birth DNA and lineage remain unchanged: a Morph never leaves Code Haven looking
the same.

MorphDomain is an optional, local-first Home Assistant habitat for Serein Morphs.
It supplies Void, Nursery, Horizon, Serein Gardens, and Code Haven together with
the bounded life engine and authenticated single-owner transfer contract.

## Clean-install identity law

A public installation starts with an empty Morph roster and contains no bundled
Morph snapshots, identities, lineage records, or private Serein state. It may
create ordinary Morphs rooted in exactly one primitive element: Fire, Water,
Air, or Earth.

Only four Founder identities can ever exist: Ember, Pulse, Spark, and Sentinel.
They and their authentic descendant lineages belong to Serein and cannot be
minted, cloned, repaired into existence, or inferred by a public installation.
An ordinary Morph can share a primitive element with a Founder without being
that Founder or belonging to that Founder lineage. Founder ancestry is accepted
only through attributable Serein lineage evidence; names and elemental matches
are never proof.

Installation does not create or claim a Morph. A Morph becomes active only after
the prepare/commit contract completes. Gender is mutable presentation state, not
a DNA, lineage, element, or authority lock. Surfaces use neutral language when no
presentation preference is present.

## Install

Copy `custom_components/morph_domain` into Home Assistant, restart, then add
**MorphDomain** from Settings > Devices & services. This layout is ready for HACS
once published as a public repository and released.

## API

- `POST /api/morph-domain/v1/transfer/{action}`
- `POST /api/morph-domain/v1/habitat/{action}`

Both require Home Assistant authentication. HTTP success alone never establishes
ownership. The normative return order, expiry semantics, and separate custody,
durability, and render gates are defined in
[`docs/TRANSFER-PROTOCOL-V1.md`](docs/TRANSFER-PROTOCOL-V1.md).

## Transfer proof status

The versioned transfer implementation is present, but the language-neutral
Android/HAOS fixture bundle and executable transfer regression suite are not yet
published in this repository. Do not treat this tree as the canonical Android
contract proof source until the required proof set in
[`docs/TRANSFER-PROTOCOL-V1.md`](docs/TRANSFER-PROTOCOL-V1.md) is present and
passes against the exact released tree. The current public test covers elemental
expression only. Presentation bindings remain outside life snapshots.

## Safe migration

First make a Home Assistant backup, then disable Serein Gateway. On first setup,
if MorphDomain has no state, it copies `serein_gateway.morph_transfer`. The source
is never changed or deleted. MorphDomain refuses to run beside the legacy engine.
After removal, restart Home Assistant. Private Morph state remains for recovery
or reinstall; uninstall never deletes it.

