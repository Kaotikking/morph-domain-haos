"""Append-only Gen-1 elemental vocabulary and deterministic hatch naming."""

from __future__ import annotations

import hashlib

WORD_POOLS = {
    "FIRE": {
        "A": ("Ember", "Blaze", "Fuego", "Cinder", "Flare", "Pyra", "Solis", "Brasa", "Ignis", "Kindle", "Scoria", "Vesta", "Aster", "Caldera", "Glow", "Torch", "Nova", "Ardent", "Sear", "Lucent"),
        "B": ("Kindled", "Radiant", "Smoldering", "Flaming", "Solar", "Molten", "Incandescent", "Ashen", "Corona", "Starborn"),
        "C": ("Spark", "Flare", "Roar", "Crackle", "Ignite", "Surge", "Flash", "Brand", "Burst", "Radiate"),
    },
    "AIR": {
        "A": ("Breeze", "Gale", "Zephyr", "Brisa", "Vento", "Aero", "Mistral", "Sora", "Cirrus", "Whisper", "Draft", "Skylark", "Nimbus", "Aloft", "Wisp", "Current", "Flutter", "Sirocco", "Kaze", "Vela"),
        "B": ("Drifting", "Soaring", "Whirling", "Weightless", "Swift", "Cloudborn", "Cyclonic", "Highwind", "Luminous", "Tempest"),
        "C": ("Gust", "Sweep", "Lift", "Rush", "Whistle", "Spiral", "Glide", "Scatter", "Vault", "Howl"),
    },
    "EARTH": {
        "A": ("Stone", "Terra", "Tierra", "Flint", "Onyx", "Basalt", "Petra", "Slate", "Cairn", "Dune", "Boulder", "Moss", "Grove", "Clay", "Jade", "Ore", "Mesa", "Crag", "Roca", "Gaia"),
        "B": ("Rooted", "Granite", "Verdant", "Mountain", "Crystal", "Ironbound", "Seismic", "Ancient", "Grounded", "Titanic"),
        "C": ("Quake", "Brace", "Root", "Rise", "Crush", "Rumble", "Fortify", "Bloom", "Burrow", "Resound"),
    },
    "WATER": {
        "A": ("Ripple", "Tide", "Aqua", "Agua", "Mizu", "Maris", "Rill", "Brook", "Nami", "Cove", "Rain", "Delta", "Lagoon", "Pearl", "Mist", "River", "Cascade", "Dew", "Azure", "Current"),
        "B": ("Flowing", "Tidal", "Glacial", "Rainborn", "Deepwater", "Crystalline", "Moonpulled", "Rushing", "Stillwater", "Resonant"),
        "C": ("Surge", "Splash", "Flow", "Wave", "Echo", "Drift", "Pour", "Chime", "Undertow", "Cascade"),
    },
}


def pool(element: str, family: str) -> tuple[str, ...]:
    return WORD_POOLS[element.upper()][family.upper()]


def hatch_name(*, morph_id: str, genome_sha256: str, element: str) -> str:
    """Choose once from Pool A using immutable Morph material."""
    names = pool(element, "A")
    digest = hashlib.sha256(f"{morph_id}|{genome_sha256}|hatch-name-v1".encode()).digest()
    return names[int.from_bytes(digest[:8], "big") % len(names)]

