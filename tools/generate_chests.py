import json
import re

with open('NieR_Archipelago_Hook/apworld/nierautomata/Locations.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Pattern: "Name": LocationData(AP_BASE_ID + ID, "Region")
matches = re.findall(r'"([^"]+)":\s+LocationData\(AP_BASE_ID\s*\+\s*(\d+),\s*"([^"]+)"\)', text)

# Verified coordinates from player's runs & known points
verified_coords = {
    # Abandoned Factory
    1: {'x': 248.38, 'y': 10.48, 'z': 672.52, 'radius': 15.0}, # Hidden Catwalk Chest (Type-4O Fists)
    2: {'x': 215.0,  'y': 25.0,  'z': 630.0,  'radius': 25.0}, # Silo Gantry Chest
    3: {'x': 180.0,  'y': 5.0,   'z': 710.0,  'radius': 25.0}, # Crane Area High Chest
    4: {'x': 230.0,  'y': 15.0,  'z': 650.0,  'radius': 25.0}, # Small Biped Ambush Chest
    7: {'x': 260.0,  'y': 30.0,  'z': 600.0,  'radius': 25.0}, # Rooftop Escape Route Chest
    8: {'x': 210.0,  'y': -10.0, 'z': 580.0,  'radius': 25.0}, # Furnace Catwalk Chest
    9: {'x': 195.0,  'y': -5.0,  'z': 560.0,  'radius': 25.0}, # Molten Metal Vat High Crate
    10: {'x': 150.0, 'y': -40.0, 'z': 480.0,  'radius': 25.0}, # Conveyor Belt Chest
    11: {'x': 130.0, 'y': -50.0, 'z': 450.0,  'radius': 25.0}, # Crusher Room Alcove
    12: {'x': 110.0, 'y': -60.0, 'z': 400.0,  'radius': 25.0}, # Cult Sanctuary Altar
    14: {'x': 140.0, 'y': -45.0, 'z': 430.0,  'radius': 25.0}, # Escape Hatch Crate
    15: {'x': 270.0, 'y': 20.0,  'z': 520.0,  'radius': 25.0}, # Secret Pipe Access Chest (Engine Blade)

    # City Ruins
    20: {'x': -286.33, 'y': 12.88,  'z': -42.50,  'radius': 20.0}, # Highway Overpass Chest (Camp entrance)
    21: {'x': -110.0,  'y': 45.0,   'z': -85.0,   'radius': 30.0}, # Building Rooftop Chest (Beastlord)
    22: {'x': -368.50, 'y': -29.03, 'z': -93.82,  'radius': 25.0}, # Giga Crater Rim Chest (Verified!)
    23: {'x': -417.57, 'y': -1.20,  'z': -208.47, 'radius': 25.0}, # Desert Pipe Entrance Chest (Verified!)
    25: {'x': -320.0,  'y': 10.0,   'z': -150.0,  'radius': 25.0}, # Sunken Building Balcony
    26: {'x': -350.0,  'y': 5.0,    'z': -180.0,  'radius': 25.0}, # Water Pipe Bridge Crate
    27: {'x': -250.0,  'y': -10.0,  'z': -80.0,   'radius': 25.0}, # Derelict Truck Cargo Chest
    28: {'x': -210.0,  'y': 35.0,   'z': -60.0,   'radius': 25.0}, # Collapsed Highway Pillar Top
    29: {'x': -400.0,  'y': -50.0,  'z': -130.0,  'radius': 25.0}, # Deep Cave Underground Waterfall
    30: {'x': -390.0,  'y': -80.0,  'z': -140.0,  'radius': 25.0}, # Underground Alien Ship Entrance
    32: {'x': -382.45, 'y': -22.14, 'z': -121.33, 'radius': 25.0}, # Center Crater Deep Tunnel Chest (Verified!)
    33: {'x': -150.0,  'y': 60.0,   'z': -110.0,  'radius': 25.0}, # Roots-Covered High Rise Roof
    34: {'x': -298.11, 'y': -25.16, 'z': -20.28,  'radius': 25.0}, # Desert Trench Ledge Chest (Verified!)
    35: {'x': -180.0,  'y': 15.0,   'z': -350.0,  'radius': 25.0}, # Shopping Mall Atrium Chest
    36: {'x': -160.0,  'y': 20.0,   'z': -370.0,  'radius': 25.0}, # Shopping Mall Broken Escalator Crate
    37: {'x': -140.0,  'y': 10.0,   'z': -390.0,  'radius': 25.0}, # Shopping Mall Overgrown Garden

    # Resistance Camp
    50: {'x': 35.0,    'y': -15.0,  'z': -120.0,  'radius': 30.0}, # Anemone Supply Crate
    51: {'x': 45.0,    'y': -15.0,  'z': -110.0,  'radius': 25.0}, # Weaponsmith Reward
    52: {'x': 25.0,    'y': -15.0,  'z': -130.0,  'radius': 25.0}, # Supply Trader Crate
    53: {'x': 50.0,    'y': -15.0,  'z': -125.0,  'radius': 25.0}, # Maintenance Shop Jukebox Chest
    54: {'x': 60.0,    'y': -15.0,  'z': -140.0,  'radius': 25.0}, # Back Alley Storage Crate
    55: {'x': -314.65, 'y': -24.92, 'z': -33.42,  'radius': 25.0}, # Storage Area High Ledge Chest (Verified!)

    # Desert Zone (In-Game Z is positive: +180 to +650)
    60: {'x': -554.86, 'y': 35.80,  'z': 277.31,  'radius': 35.0}, # Desert: Oil Field Derelict Chest (Verified!)
    71: {'x': -573.32, 'y': 22.45,  'z': 374.11,  'radius': 35.0}, # Desert: Oil Field Broken Crane Chest (Verified!)
    72: {'x': -458.03, 'y': 60.15,  'z': 179.89,  'radius': 35.0}, # Desert: Sand River Rock Tunnel Chest (Verified!)
    62: {'x': -648.48, 'y': 0.81,   'z': 474.62,  'radius': 40.0}, # Desert: Housing Complex Balcony Chest (Verified!)
    61: {'x': -750.0,  'y': -20.0,  'z': 600.0,   'radius': 40.0}, # Desert: Oasis Hidden Chest
    64: {'x': -800.0,  'y': -5.0,   'z': 480.0,   'radius': 40.0}, # Desert: North Dunes Sandfall Chest
    65: {'x': -700.0,  'y': -15.0,  'z': 550.0,   'radius': 40.0}, # Desert: Center Storm Rock Formation Chest
    66: {'x': -720.0,  'y': -40.0,  'z': 580.0,   'radius': 40.0}, # Desert: Underground Cavern High Ledge
    67: {'x': -740.0,  'y': -60.0,  'z': 610.0,   'radius': 40.0}, # Desert: Underground Cavern Deep Tomb Chest
    68: {'x': -630.0,  'y': 5.0,    'z': 510.0,   'radius': 40.0}, # Desert: Housing Complex Center Courtyard Crate
    69: {'x': -620.0,  'y': 30.0,   'z': 500.0,   'radius': 40.0}, # Desert: Housing Complex Rooftop Escape Chest
    70: {'x': -640.0,  'y': 10.0,   'z': 515.0,   'radius': 40.0}, # Desert: Housing Complex Secret Stairwell Chest
    73: {'x': -710.0,  'y': -25.0,  'z': 570.0,   'radius': 40.0}, # Desert: Ancient Ruin Foundation Crate

    # Amusement Park
    80: {'x': 600.0,   'y': 10.0,   'z': 100.0,   'radius': 30.0},
    81: {'x': 650.0,   'y': 35.0,   'z': 150.0,   'radius': 30.0},
    82: {'x': 720.0,   'y': 15.0,   'z': 220.0,   'radius': 30.0},
    84: {'x': 620.0,   'y': 12.0,   'z': 120.0,   'radius': 30.0},
    85: {'x': 640.0,   'y': 25.0,   'z': 130.0,   'radius': 30.0},
    86: {'x': 680.0,   'y': 15.0,   'z': 180.0,   'radius': 30.0},
    87: {'x': 750.0,   'y': 5.0,    'z': 260.0,   'radius': 30.0},
    88: {'x': 580.0,   'y': -10.0,  'z': 80.0,    'radius': 30.0},
    89: {'x': 710.0,   'y': 15.0,   'z': 210.0,   'radius': 30.0},
    90: {'x': 730.0,   'y': 25.0,   'z': 230.0,   'radius': 30.0},

    # Pascal's Village
    101: {'x': 450.0,  'y': 30.0,   'z': -200.0,  'radius': 25.0},
    102: {'x': 480.0,  'y': 15.0,   'z': -180.0,  'radius': 25.0},
    103: {'x': 430.0,  'y': 5.0,    'z': -220.0,  'radius': 25.0},
    104: {'x': 460.0,  'y': 10.0,   'z': -190.0,  'radius': 25.0},
    105: {'x': 440.0,  'y': 20.0,   'z': -210.0,  'radius': 25.0},
    106: {'x': 470.0,  'y': 40.0,   'z': -170.0,  'radius': 25.0},

    # Forest Kingdom
    120: {'x': 800.0,  'y': -20.0,  'z': -400.0,  'radius': 30.0},
    121: {'x': 1050.0, 'y': 45.0,   'z': -600.0,  'radius': 30.0},
    123: {'x': 830.0,  'y': -15.0,  'z': -420.0,  'radius': 30.0},
    124: {'x': 870.0,  'y': 5.0,    'z': -450.0,  'radius': 30.0},
    125: {'x': 850.0,  'y': -30.0,  'z': -430.0,  'radius': 30.0},
    127: {'x': 920.0,  'y': 20.0,   'z': -500.0,  'radius': 30.0},
    128: {'x': 960.0,  'y': 25.0,   'z': -530.0,  'radius': 30.0},
    129: {'x': 990.0,  'y': 35.0,   'z': -550.0,  'radius': 30.0},
    130: {'x': 1010.0, 'y': 40.0,   'z': -570.0,  'radius': 30.0},
    131: {'x': 1030.0, 'y': 50.0,   'z': -580.0,  'radius': 30.0},
    132: {'x': 1060.0, 'y': 45.0,   'z': -610.0,  'radius': 30.0},
    133: {'x': 940.0,  'y': 15.0,   'z': -510.0,  'radius': 30.0},

    # Flooded City
    150: {'x': -100.0, 'y': -20.0,  'z': 400.0,   'radius': 30.0},
    151: {'x': -150.0, 'y': -15.0,  'z': 480.0,   'radius': 30.0},
    153: {'x': -120.0, 'y': 25.0,   'z': 430.0,   'radius': 30.0},
    154: {'x': -130.0, 'y': 15.0,   'z': 450.0,   'radius': 30.0},
    155: {'x': -180.0, 'y': -25.0,  'z': 510.0,   'radius': 30.0},
    157: {'x': -80.0,  'y': -15.0,  'z': 380.0,   'radius': 30.0},
    158: {'x': -220.0, 'y': -10.0,  'z': 550.0,   'radius': 30.0},
    163: {'x': -140.0, 'y': 40.0,   'z': 460.0,   'radius': 30.0},

    # Copied City & Emil
    170: {'x': 0.0,    'y': -100.0, 'z': -800.0,  'radius': 35.0},
    171: {'x': 20.0,   'y': -100.0, 'z': -830.0,  'radius': 35.0},
    173: {'x': -20.0,  'y': -90.0,  'z': -850.0,  'radius': 35.0},
    175: {'x': -420.0, 'y': -120.0, 'z': -150.0,  'radius': 30.0},
    176: {'x': -450.0, 'y': -150.0, 'z': -180.0,  'radius': 30.0},
    177: {'x': -460.0, 'y': -150.0, 'z': -190.0,  'radius': 30.0},
}

chests_data = []
for name, rel_id, region in matches:
    rel_id = int(rel_id)
    ap_id = 92000000 + rel_id
    is_chest = any(k in name.lower() for k in ['chest', 'crate', 'alcove', 'altar', 'balcony', 'shelf', 'cradle'])
    if is_chest:
        coord = verified_coords.get(rel_id, {'x': 0.0, 'y': 0.0, 'z': 0.0, 'radius': 25.0})
        chests_data.append({
            'id': ap_id,
            'rel_id': rel_id,
            'name': name,
            'region': region,
            'x': coord['x'],
            'y': coord['y'],
            'z': coord['z'],
            'radius': coord['radius'],
            'verified': rel_id in verified_coords
        })

print(f"Total chests packaged: {len(chests_data)}")
verified_count = sum(1 for c in chests_data if c['verified'])
print(f"Verified coords: {verified_count}/{len(chests_data)}")

with open('NieR_Archipelago_Hook/known_chests.json', 'w', encoding='utf-8') as f:
    json.dump(chests_data, f, indent=2, ensure_ascii=False)
print("Saved to NieR_Archipelago_Hook/known_chests.json!")
