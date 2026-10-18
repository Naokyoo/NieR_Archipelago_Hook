import urllib.request
import zipfile
import os
import shutil

url = "https://github.com/ocornut/imgui/archive/refs/tags/v1.91.8.zip"
temp_zip = "imgui_temp.zip"
extract_dir = "imgui_temp_dir"
target_dir = os.path.abspath("imgui")

print(f"[*] Downloading ImGui from {url}...")
urllib.request.urlretrieve(url, temp_zip)

print("[*] Extracting zip...")
with zipfile.ZipFile(temp_zip, "r") as zf:
    zf.extractall(extract_dir)

subfolder = [os.path.join(extract_dir, f) for f in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, f))][0]

os.makedirs(target_dir, exist_ok=True)

files_to_copy = [
    "imgui.h", "imgui.cpp", "imgui_draw.cpp", "imgui_tables.cpp", "imgui_widgets.cpp",
    "imgui_internal.h", "imstb_rectpack.h", "imstb_textedit.h", "imstb_truetype.h",
    "imconfig.h", "LICENSE.txt"
]

for f in files_to_copy:
    src = os.path.join(subfolder, f)
    dst = os.path.join(target_dir, f)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  + Copied {f}")

backends_dir = os.path.join(subfolder, "backends")
backend_files = [
    "imgui_impl_win32.h", "imgui_impl_win32.cpp",
    "imgui_impl_dx11.h", "imgui_impl_dx11.cpp"
]

for f in backend_files:
    src = os.path.join(backends_dir, f)
    dst = os.path.join(target_dir, f)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  + Copied {f}")

# Cleanup
os.remove(temp_zip)
shutil.rmtree(extract_dir, ignore_errors=True)
print(f"[+] Dear ImGui successfully installed in: {target_dir}")
