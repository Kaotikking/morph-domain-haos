# MorphDomain DNAv1 lineage and lifecycle freeze

This contract supplements `serein.morph-domain.dna.v1` without rewriting an
existing Morph merely because the integration upgrades.

## Immutable birth truth

Every new Morph receives one `serein.morph-lineage-capsule.v1` containing its
identity, parentage, founder ancestry, birth device, primitive and recessive
lineage, ordered five-stage primary expression path, birth-authorized awakened
set, trait seed, egg/hatch receipt, twin binding, and genome version. Its
canonical SHA-256 digest is the portable lineage witness.

## Lifecycle

`SEALED -> HATCHING -> JUVENILE -> MATURE -> AWAKENED`

Transitions advance one step and never regress. Eggs expose no element or
lineage: the public projection is a Void-black silhouette with one white line.
The hatch receipt is the first presentation of lineage. Recessives remain
dormant until MATURE. AWAKENED may switch only among the expression set fixed at
birth, one expression at a time, with an attributable cooldown.

## Social and family truth

Social edges are directional and use exactly five states:
`UNFAMILIAR -> AWARE -> FAMILIAR -> BONDED -> RESONANT`.
Family links are immutable `PARENT`, `CHILD`, `SIBLING`, or `TWIN`
relationships and never substitute for earned social state.

## Breeding gate

Both parents must be MATURE or AWAKENED, mutually FAMILIAR or higher,
consent-admitted, cooldown-clear, distinct identities, and admitted together in
one atomic Nursery transaction. Nursery overflow is isolated in Void rather
than silently discarded or activated.

## Migration law

Existing Morphs are preserved as-is. A capsule backfill may be prepared only for
the same Morph identity and applied only through Code Haven. The backfill must
preserve identity, lineage, life, growth, mastery, Chronicle, generation,
authority, and custody. Installation alone has no Morph-state effect.
