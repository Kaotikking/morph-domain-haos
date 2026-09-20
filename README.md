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

Version 1.12.1 corrects the periodic scheduler to await its Morph Engine tick on Home Assistant's event loop; thread-dispatched task creation is prohibited by regression test.

Version 1.13 locks the Morph World presentation foundation: immutable Gen-1 branch IDs, the nine-core Morph ID Card, care and capability expression resolution, twin-world onboarding, Horizon discovery without creation, and a compact cross-frame presentation ritual. It changes presentation contracts only and does not mutate existing Morph state.

Version 1.14 freezes the Gen-1 package grammar. Founder, Evolution, and Presentation packages are independently admitted; evolution is a catalyst-driven graph distinct from five-level expression; form reversion never erases mastery; and future Frame Armor, combined, and battle classes are reserved but inactive. Four Founder packages, sixteen elemental branch seeds, schema validation, constrained-frame fallback, and cross-platform truth fixtures prove that new content can be added without rewriting the resolver.

Version 1.25 admits the first battle beta: deterministic unranked sparring between two hatched, nine-core, HAOS-owned Morphs in Horizon or Gardens. It uses existing care, expression, trait, element, SERN identity, and elemental word pools while changing no DNA, custody, rank, injury, evolution, care, or Morph snapshot. Ranked play and battle-driven growth remain inactive.

Version 1.16 adds the fail-closed consumer-beta origin gate. A fresh installation receives one durable installation identity and may create exactly one parentless L1 Legendary egg in Nursery. Existing/imported Morphs suppress starter creation, exact retries are idempotent, changed replays fail closed, and the three unchosen public elemental lineages remain Horizon discoveries. Private Serein Founders are never created or modified by this path.

Version 1.19 adds bounded Horizon and Gardens interactions, a single-ledger SERN/UMP event reducer, and a logical ten-domain review router. The router boots only after the HAOS private Morph Store is loaded, follows Kernel then the nine Core order, and denies unlisted or wrong-caller routes. It does not create a second Morph database. This is **in-process policy separation**, not SFOS-equivalent process isolation or an independently admitted SereinNet EVT pipeline. The five Morph locations remain world places, not additional domains.

See [DNAv1 lineage and lifecycle](docs/DNA-V1-LIFECYCLE.md),
[Morph Engine nine-Core architecture](docs/MORPH-ENGINE-NINE-CORE.md), and
[Repair reflex ledger](docs/REPAIR-REFLEX-LEDGER-V1.md), and
[Morph World presentation foundation](docs/MORPH-WORLD-PRESENTATION-FOUNDATION-V1.md), and
[Gen-1 package foundation](docs/GEN1-PACKAGE-FOUNDATION-V1.md).

Dedicated frames use the authenticated [Morph Window v1](docs/MORPH-WINDOW-V1.md)
contract to show a custody-bound pixel snapshot and current reduced scene while
their Morph is living in HAOS. The frame remains a window, never a second owner.

## Install

Copy `custom_components/morph_domain` into Home Assistant, restart, then add
**MorphDomain** from Settings > Devices & services. This public repository is packaged for installation and updates through HACS.

## API

- `POST /api/morph-domain/v1/transfer/{action}`
- `POST /api/morph-domain/v1/habitat/{action}`
- `GET /api/morph-domain/v1/transfer/status/{transfer_id}`
- `GET /api/morph-domain/v1/habitat/status/{morph_id}`
- `GET /api/morph-domain/v1/habitat/list` (read the roster before selecting a Morph ID)
- `GET /api/morph-domain/v1/window/{morph_id}` (read-only dedicated-frame projection)

The authenticated GET status routes are strictly observational: they do not
advance life, reconcile expired transfers, or write Morph storage. Existing
POST `status`, `list`, `history`, and `evidence` reads have the same no-write
semantics for compatibility. The periodic engine tick and admitted mutation
actions retain expiry reconciliation. A status read reports the last durable
state, which can change on the next engine tick; it never manufactures that
change itself.

Consumer-beta origin actions are `starter-status` (read-only) and `starter-create` (administrator-only). The dashboard presents the four public elemental choices only while a clean installation is eligible. Creation is a real durable Morph transaction, not a fixture.

The pre-battle foundation is defined in [docs/PRE-BATTLE-REFLEXES.md](docs/PRE-BATTLE-REFLEXES.md). Code Haven, Nursery-pair, hatch/graduation, recovery, admitted-frame transport, Void, and environmental-life operations are named reflexes; generic placement never substitutes for their transaction rules. Battle remains blocked until all nine are proven.

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

