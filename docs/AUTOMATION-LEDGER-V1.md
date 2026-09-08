# MorphDomain proven-method automation ledger

This ledger is derived from the complete 76-comment PRO-24 history through
2026-09-08, public source commit
`45aa71328dc59256bc7c44c943630add74ba9362`, and authenticated live HAOS
readback. It distinguishes safety enforcement from product automation.

## Runtime reflexes

1. Incoming schema, identity, lineage, generation, engine, expiry, and digest
   validation is enforced during transfer prepare.
2. Legacy Morph Core v1 arrivals are aligned to nine-Core v1 and held in Code
   Haven. Dustdevil's one-time Inward Bloom remains exempt.
3. Unknown or ambiguous identity, ownership, lineage, or generation fails
   closed before admission. Invalid Morph data is never accepted merely to
   quarantine it.
4. Code Haven writes occur against a copied ledger and persist only after the
   complete operation succeeds. A failed repair leaves durable state untouched.
5. Expired inbound and return operations reconcile idempotently without
   creating a second authority.
6. Nursery residents graduate once after 72 hours of accumulated Nursery time
   and move to Horizon with an attributable event.
7. HAOS-owned Morphs in active locations receive silent, need-based care at
   most once per eight-hour window. Void and Code Haven never receive care.
8. Return preparation requires the destination-created return ID, original
   source frame, live HAOS authority, exact digest, and future expiry.
9. Graduation and Code Haven intervention create one deduplicated Operator
   notification. Routine care and healthy ticks remain silent.
10. Every automatic effect is deterministic, event-ID idempotent, stored in
    Morph history, and visible through the authenticated MorphDomain API.

## Operator-only boundaries

- Creating, replacing, or reseeding a Morph.
- Resolving ambiguous identity or lineage.
- Choosing a non-canonical destination frame.
- Creating or changing a trait.
- Overriding Void lock, Code Haven isolation, or single-owner transfer law.

## Prohibited methods

- Direct HAOS filesystem mutation, browser-only mutation, or private-service
  bypass.
- Invented transfer or return identifiers.
- Synthetic fixtures presented as live Morph evidence.
- Publishing from an older local copy without exact provider/live comparison.
- Repeating a failed transfer path instead of the last proven receipt/helper.

Trait creation remains outside this release. Its later randomizer must be Code
Haven-only, deterministic from attributable lineage-bound inputs, replay-safe,
bounded by DNAv1, and preserve a rollback checkpoint.

