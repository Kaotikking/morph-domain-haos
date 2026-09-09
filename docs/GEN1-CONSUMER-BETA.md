# Gen-1 consumer beta

A clean MorphDomain installation owns one durable installation identity. If no Morph has ever been imported or created, an administrator may choose one public Legendary lineage: Fire (`L1-01`), Air (`L1-02`), Earth (`L1-03`), or Water (`L1-04`).

The choice atomically creates one real parentless egg in Nursery with a DNAv1 genome, nine-Core Morph record, platform-of-birth lineage, HAOS custody, and starter-birth Chronicle event. Exact request replay is idempotent. A changed replay, second starter, missing installation identity, or pre-existing Morph fails closed without changing state.

The three unchosen lineages remain `HORIZON_UNDISCOVERED`. Discovery never silently creates another Morph. Private Serein Founders (`F`) are outside this public origin path and remain unchanged.

The consumer-beta admission proof is: package tests pass; exact provider tree is read back; HAOS installs that commit through the supported integration path; Core returns; `starter-status` reports either the four clean choices or the existing durable claim. No starter is created during installation or verification.

