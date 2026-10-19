"""Builds the player release zip: release/NieR-Automata-Archipelago-<version>.zip

Run build.bat first (the zip ships the compiled dinput8.dll).
    python tools/make_release.py 0.1.0-prebeta
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_FILES = ["dinput8.dll", "nier_archipelago_bridge.py", "Lancer_Pont_Archipelago.bat",
              "ap_definitions.json", "known_chests.json"]


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    missing = [f for f in GAME_FILES if not os.path.exists(os.path.join(ROOT, f))]
    if missing:
        sys.exit(f"Missing files (run build.bat first?): {', '.join(missing)}")

    out_dir = os.path.join(ROOT, "release")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"NieR-Automata-Archipelago-{version}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # Files that go next to NieRAutomata.exe
        for f in GAME_FILES:
            zf.write(os.path.join(ROOT, f), f"NieRAutomata folder/{f}")

        # The Archipelago world (an .apworld is a zip of the nierautomata package)
        apworld_path = os.path.join(out_dir, "nierautomata.apworld")
        world_dir = os.path.join(ROOT, "apworld", "nierautomata")
        with zipfile.ZipFile(apworld_path, "w", zipfile.ZIP_DEFLATED) as world:
            for name in sorted(os.listdir(world_dir)):
                if name.endswith(".py"):
                    world.write(os.path.join(world_dir, name), f"nierautomata/{name}")
        zf.write(apworld_path, "nierautomata.apworld")

        zf.write(os.path.join(ROOT, "NieR Automata.yaml"), "NieR Automata.yaml")
        zf.write(os.path.join(ROOT, "README.md"), "README.md")
        zf.write(os.path.join(ROOT, "LICENSE"), "LICENSE")
    print(f"[+] {out}")


if __name__ == "__main__":
    main()
