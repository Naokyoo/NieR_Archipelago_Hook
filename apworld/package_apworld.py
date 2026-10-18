#!/usr/bin/env python3
"""
Packages the nierautomata/ folder into nierautomata.apworld and installs to MultiworldGG
"""
import zipfile
import os
import shutil

def package():
    source_dir = os.path.join(os.path.dirname(__file__), "nierautomata")
    output_apworld = os.path.join(os.path.dirname(__file__), "nierautomata.apworld")

    print(f"[*] Packaging {source_dir} -> {output_apworld}...")
    with zipfile.ZipFile(output_apworld, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith((".py", ".json", ".md", ".txt")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, os.path.dirname(source_dir))
                    zf.write(full_path, rel_path)
                    print(f"  + Added {rel_path}")

    print(f"[+] Successfully generated {output_apworld}!")

    # MultiworldGG target paths
    target_paths = [
        r"C:\Program Files\MultiworldGG\lib\worlds\nierautomata.apworld",
        r"C:\Program Files\MultiworldGG\custom_worlds\nierautomata.apworld",
    ]

    for target in target_paths:
        target_dir = os.path.dirname(target)
        if os.path.exists(target_dir):
            try:
                shutil.copy2(output_apworld, target)
                print(f"[+] Installed to {target}")
            except Exception as e:
                print(f"[-] Could not copy to {target}: {e}")

if __name__ == "__main__":
    package()
