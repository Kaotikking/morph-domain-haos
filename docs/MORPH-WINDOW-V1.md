# Morph Window v1

Morph Window is the consumer-facing projection of one HAOS-owned Morph onto
its dedicated frame. It is a read-only SERN-shaped snapshot, not remote
rendering, custody, or a second active Morph.

`GET /api/morph-domain/v1/window/{morph_id}` requires Home Assistant
authentication and never advances life or writes storage. The response binds:

- exact Morph identity, custody revision, lineage generation and snapshot digest;
- authority, canonical location, current reduced scene and up to two companions;
- a deterministic 12x12 pixel avatar in the Morph's elemental palette;
- mutable presentation revision and separate avatar/window digests;
- a five-minute trust window; and
- any currently open neutral life call.

The producer exposes `DOMAIN_WINDOW`, `RETURNING_HOME`, or `LOCAL_PRESENCE`.
The consuming frame owns two presentation-only states: `CONNECTION_LOST`
(show the last trusted snapshot and timestamp after expiry) and `HOME_RESTORED`
(atomically replace the projection with the local Life Engine after custody is
verified). Neither presentation state may change authority.

Life calls are silent by default. MorphDomain records the intention and its
resolution; a frame or app policy decides whether to show, animate, sound, or
ignore it. Smart-home lights, speakers, alarms, and unrelated domains are not
implicit Morph-call channels.

The first physical acceptance target is Sentinel's dedicated frame. That OTA
must consume this published contract, cache the last valid digest-bound window,
and preserve the existing destination-owned transfer protocol.

## Frame delivery

MorphDomain may deliver the reduced window through an encrypted, local ESPHome
API action when the admitted frame advertises one. Delivery is best-effort and
presentation-only: an offline or older frame cannot block Morph life, custody,
or transfer. Frames validate identity, schema, digests, row count, and authority
before replacing their durable last-trusted cache. No Home Assistant bearer
credential is stored on a frame.

Sentinel's admitted action is `pet_frame_v12_morph_window_update`. Its diagnostic
state exposes the accepted window mode, place, custody revision, lineage
generation, and link status without exposing private Morph history.

