import json

with open('NieR_Archipelago_Hook/known_chests.json', 'r', encoding='utf-8') as f:
    chests = json.load(f)

verified = [c for c in chests if c.get('verified')]
print(f"// Total verified chests: {len(verified)}")
for c in verified:
    name = c['name'].replace('"', '')
    print(f"    {{ {c['x']}f, {c['y']}f, {c['z']}f, {c['radius']}f, {c['id']} }}, // {name}")
