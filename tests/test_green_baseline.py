from pathlib import Path

PANEL = Path(__file__).parents[1] / "custom_components/morph_domain/frontend/morph-domain-panel.js"
PROFILE = Path(__file__).parents[1] / "docs/HARDWARE-PROFILES.md"


def test_green_panel_is_visibility_aware_and_sixty_second_bounded():
    source = PANEL.read_text(encoding="utf-8")
    assert 'setInterval(()=>{if(!document.hidden)this.refresh()},60000)' in source
    assert 'document.addEventListener("visibilitychange",this.onVisibility)' in source
    assert 'document.removeEventListener("visibilitychange",this.onVisibility)' in source
    assert "15000" not in source


def test_green_portraits_are_deterministic_cached_svg():
    source = PANEL.read_text(encoding="utf-8")
    assert "this.portraits=new Map()" in source
    assert '<svg class="portrait"' in source
    assert "this.portraits.size>32" in source
    assert "canvas" not in source.lower()
    assert "webgl" not in source.lower()


def test_green_profile_preserves_one_canonical_truth():
    source = PROFILE.read_text(encoding="utf-8")
    assert "GREEN_BASELINE" in source
    assert "EXPANDED" in source
    assert "ACCELERATED" in source
    assert "must never alter Morph identity or life truth" in source
