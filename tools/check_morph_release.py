"""Fail-closed source-shape gate for the MorphDomain HACS candidate."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "morph_domain"


def main() -> int:
    required = ("__init__.py", "manifest.json", "services.yaml", "strings.json",
                "translations/en.json", "morph_transfer.py", "morph_habitat.py",
                "_vendor/morph_engine/haos_runtime.py",
                "_vendor/morph_engine/event_reducer.py")
    missing = [name for name in required if not (PACKAGE / name).is_file()]
    if missing:
        print("RELEASE_NOT_READY: missing " + ", ".join(missing))
        return 1
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    if manifest.get("domain") != "morph_domain" or manifest.get("version") != "1.25.0" or hacs.get("name") != "MorphDomain":
        print("RELEASE_NOT_READY: package identity/version mismatch")
        return 1
    adapter = (PACKAGE / "morph_transfer.py").read_text(encoding="utf-8")
    router = (PACKAGE / "_vendor/morph_engine/haos_runtime.py").read_text(encoding="utf-8")
    if ("self.domain_runtime = build_haos_runtime" not in adapter
            or "domain_runtime=domain_runtime" not in adapter
            or "host_ready=store_loaded" not in router):
        print("RELEASE_NOT_READY: single-Store ten-domain route is not wired")
        return 1
    if "MorphDomainLocalApp" in adapter or "DomainStorage(" in adapter:
        print("RELEASE_NOT_READY: second Morph state owner found in HAOS adapter")
        return 1
    print("SOURCE_SHAPE_READY: local tests and installed readback still required")
    return 0


if __name__ == "__main__":
    sys.exit(main())

