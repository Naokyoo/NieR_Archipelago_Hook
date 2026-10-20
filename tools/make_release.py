"""Builds the player release zip: release/NieR-Automata-Archipelago-<version>.zip

Run build.bat first (the zip ships the compiled dinput8.dll). The zip also ships an embeddable Python
with the bridge's packages, so players don't have to install Python.
    python tools/make_release.py 0.1.0-prebeta
"""
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_FILES = ["dinput8.dll", "nier_archipelago_bridge.py", "Lancer_Pont_Archipelago.bat",
              "ap_definitions.json", "known_chests.json"]

# Embeddable Python that runs the bridge (python.org), and the packages the bridge needs
PYTHON_VERSION = "3.13.12"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_EMBED_SHA256 = "76f238f606250c87c6beac75dccd35ee99070a13490555936abb6cb64ecce3d0"
BRIDGE_PACKAGES = ["websockets==17.3", "certifi==2026.10.18"]


def build_python(out_dir):
    """Unpacks the embeddable Python into release/python and installs the bridge's packages in it."""
    cache_dir = os.path.join(out_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    embed_zip = os.path.join(cache_dir, os.path.basename(PYTHON_EMBED_URL))
    if not os.path.exists(embed_zip):
        print(f"[*] Downloading {PYTHON_EMBED_URL}")
        urllib.request.urlretrieve(PYTHON_EMBED_URL, embed_zip)
    with open(embed_zip, "rb") as f:
        if hashlib.sha256(f.read()).hexdigest() != PYTHON_EMBED_SHA256:
            os.remove(embed_zip)
            sys.exit(f"Checksum mismatch for {os.path.basename(embed_zip)}, download removed")

    py_dir = os.path.join(out_dir, "python")
    shutil.rmtree(py_dir, ignore_errors=True)
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(py_dir)

    major, minor = PYTHON_VERSION.split(".")[:2]
    site_packages = os.path.join(py_dir, "Lib", "site-packages")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-compile",
                           "--target", site_packages,
                           "--platform", "win_amd64", "--python-version", f"{major}.{minor}",
                           "--implementation", "cp", "--only-binary=:all:", *BRIDGE_PACKAGES])
    # Command-line launchers pip creates for the packages; the bridge doesn't use them
    shutil.rmtree(os.path.join(site_packages, "bin"), ignore_errors=True)
    # The embeddable Python only searches the paths listed in its ._pth file
    with open(os.path.join(py_dir, f"python{major}{minor}._pth"), "a", encoding="utf-8") as f:
        f.write("Lib\\site-packages\n")
    return py_dir


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
        py_dir = build_python(out_dir)
        for dirpath, dirnames, filenames in os.walk(py_dir):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, py_dir).replace(os.sep, "/")
                zf.write(path, f"NieRAutomata folder/python/{rel}")

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
