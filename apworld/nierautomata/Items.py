"""
NieR: Automata Archipelago Item Definitions
"""

from typing import Dict, NamedTuple
from BaseClasses import Item, ItemClassification

AP_BASE_ID = 92000000

class NieRItem(Item):
    game: str = "NieR Automata"

class ItemData(NamedTuple):
    code: int
    classification: ItemClassification

# Item ID mapping (AP Base 92000000 + in-game ID)
item_table: Dict[str, ItemData] = {
    # --- Weapons (Progression) ---
    "Virtuous Contract": ItemData(AP_BASE_ID + 1070, ItemClassification.progression),
    "Cruel Oath":        ItemData(AP_BASE_ID + 1071, ItemClassification.progression),
    "Machine Sword":     ItemData(AP_BASE_ID + 1090, ItemClassification.useful),
    "Iron Pipe":         ItemData(AP_BASE_ID + 1013, ItemClassification.progression),
    "Beastbane":         ItemData(AP_BASE_ID + 1020, ItemClassification.progression),
    "Ancient Overlord":  ItemData(AP_BASE_ID + 1030, ItemClassification.progression),
    "Type-4O Sword":     ItemData(AP_BASE_ID + 1050, ItemClassification.progression),
    "Type-3 Sword":      ItemData(AP_BASE_ID + 1060, ItemClassification.useful),
    "Virtuous Treaty":   ItemData(AP_BASE_ID + 1260, ItemClassification.progression),
    "Cruel Blood Oath":  ItemData(AP_BASE_ID + 1261, ItemClassification.progression),
    "Machine Axe":       ItemData(AP_BASE_ID + 1270, ItemClassification.useful),
    "Beastlord":         ItemData(AP_BASE_ID + 1220, ItemClassification.progression),
    "Iron Will":         ItemData(AP_BASE_ID + 1203, ItemClassification.progression),
    "Phoenix Sword":     ItemData(AP_BASE_ID + 1230, ItemClassification.progression),
    "Type-4O Blade":     ItemData(AP_BASE_ID + 1240, ItemClassification.progression),
    "Virtuous Dignity":  ItemData(AP_BASE_ID + 1470, ItemClassification.progression),
    "Cruel Arrogance":   ItemData(AP_BASE_ID + 1471, ItemClassification.progression),
    "Machine Spear":     ItemData(AP_BASE_ID + 1480, ItemClassification.useful),
    "Beastcurse":        ItemData(AP_BASE_ID + 1420, ItemClassification.progression),
    "Dragoon Lance":      ItemData(AP_BASE_ID + 1430, ItemClassification.progression),
    "Phoenix Lance":     ItemData(AP_BASE_ID + 1400, ItemClassification.progression),
    "Type-4O Lance":     ItemData(AP_BASE_ID + 1450, ItemClassification.progression),
    "Virtuous Grief":    ItemData(AP_BASE_ID + 1620, ItemClassification.progression),
    "Cruel Lament":      ItemData(AP_BASE_ID + 1621, ItemClassification.progression),
    "Machine Heads":     ItemData(AP_BASE_ID + 1650, ItemClassification.useful),
    "Type-4O Fists":     ItemData(AP_BASE_ID + 1610, ItemClassification.progression),
    "Demon's Cry":       ItemData(AP_BASE_ID + 1630, ItemClassification.progression),
    "Engine Blade":      ItemData(AP_BASE_ID + 1875, ItemClassification.progression),
    "Cypress Stick":     ItemData(AP_BASE_ID + 1876, ItemClassification.useful),
    "Emil Heads":        ItemData(AP_BASE_ID + 1877, ItemClassification.progression),

    # --- Pod Programs & Key Modules (Progression & Useful) ---
    "Pod Program: Laser (R010)":     ItemData(AP_BASE_ID + 2001, ItemClassification.progression),
    "Pod Program: Mirage (R020)":    ItemData(AP_BASE_ID + 2002, ItemClassification.progression),
    "Pod Program: Hammer (R030)":    ItemData(AP_BASE_ID + 2003, ItemClassification.progression),
    "Pod Program: Blade (R040)":     ItemData(AP_BASE_ID + 2004, ItemClassification.progression),
    "Pod Program: Spear (R050)":     ItemData(AP_BASE_ID + 2005, ItemClassification.progression),
    "Pod Program: P Shield (A060)":    ItemData(AP_BASE_ID + 2007, ItemClassification.useful),
    "Pod Program: Wave (A080)":      ItemData(AP_BASE_ID + 2008, ItemClassification.useful),
    "Pod Program: Slow (A110)":      ItemData(AP_BASE_ID + 2011, ItemClassification.useful),
    "Pod Program: Missile (A160)":   ItemData(AP_BASE_ID + 2022, ItemClassification.progression),
    "Pod Program: Wire (A090)":      ItemData(AP_BASE_ID + 2009, ItemClassification.useful),
    "Pod Program: Gravity (A140)":   ItemData(AP_BASE_ID + 2019, ItemClassification.useful),
    "Pod Program: Volt (A150)":      ItemData(AP_BASE_ID + 2021, ItemClassification.useful),
    "Pod Program: Repair (A120)":    ItemData(AP_BASE_ID + 2012, ItemClassification.useful),
    "Pod Program: M Shield (R070)":  ItemData(AP_BASE_ID + 2006, ItemClassification.useful),
    "Pod Program: Decoy (A100)":     ItemData(AP_BASE_ID + 2010, ItemClassification.useful),
    "Pod Program: Bomb (A130)":      ItemData(AP_BASE_ID + 2015, ItemClassification.useful),
    "Hacking Module (9S Ability)":   ItemData(AP_BASE_ID + 2100, ItemClassification.progression),
    "Pod Program: Scanner (A170)":   ItemData(AP_BASE_ID + 2024, ItemClassification.progression),

    # --- Plug-in Chips (Useful) ---
    "Plug-in Chip: Weapon Attack Up +3": ItemData(AP_BASE_ID + 3004, ItemClassification.filler),
    "Plug-in Chip: Max HP Up +3":        ItemData(AP_BASE_ID + 3076, ItemClassification.filler),
    "Plug-in Chip: Auto-Heal +2":        ItemData(AP_BASE_ID + 3102, ItemClassification.filler),
    "Plug-in Chip: Overclock +3":        ItemData(AP_BASE_ID + 3193, ItemClassification.filler),
    "Plug-in Chip: Moving Speed Up +3":  ItemData(AP_BASE_ID + 3121, ItemClassification.filler),
    "Plug-in Chip: Shockwave +3":        ItemData(AP_BASE_ID + 3148, ItemClassification.filler),
    "Plug-in Chip: Drop Rate Up +3":     ItemData(AP_BASE_ID + 3130, ItemClassification.filler),

    # --- System / HUD Chips (Progression & Useful) ---
    "HUD: HP Gauge":        ItemData(AP_BASE_ID + 3335, ItemClassification.progression),
    "HUD: Enemy Data":      ItemData(AP_BASE_ID + 3337, ItemClassification.useful),
    "HUD: Objectives":      ItemData(AP_BASE_ID + 3349, ItemClassification.useful),
    "HUD: Mini-map":        ItemData(AP_BASE_ID + 3345, ItemClassification.progression),
    "HUD: Skill Gauge":     ItemData(AP_BASE_ID + 3343, ItemClassification.useful),
    "HUD: Text Log":        ItemData(AP_BASE_ID + 3344, ItemClassification.useful),
    "HUD: Damage Values":   ItemData(AP_BASE_ID + 3348, ItemClassification.useful),
    "HUD: Save Points":       ItemData(AP_BASE_ID + 3347, ItemClassification.useful),
    "HUD: Control":         ItemData(AP_BASE_ID + 3350, ItemClassification.useful),
    "HUD: Sound Waves":     ItemData(AP_BASE_ID + 3336, ItemClassification.filler),

    # --- Consumables & Buffs (Useful) ---
    "Small Recovery":      ItemData(AP_BASE_ID + 0, ItemClassification.filler),
    "Medium Recovery":     ItemData(AP_BASE_ID + 1, ItemClassification.filler),
    "Large Recovery":      ItemData(AP_BASE_ID + 2, ItemClassification.filler),
    "Full Recovery":            ItemData(AP_BASE_ID + 3, ItemClassification.filler),
    "Speed Salve (S)":     ItemData(AP_BASE_ID + 160, ItemClassification.filler),
    "Speed Salve (L)":     ItemData(AP_BASE_ID + 162, ItemClassification.filler),
    "Melee Attack Up (S)": ItemData(AP_BASE_ID + 100, ItemClassification.filler),
    "Melee Attack Up (L)": ItemData(AP_BASE_ID + 102, ItemClassification.filler),
    "Ranged Attack Up (L)":ItemData(AP_BASE_ID + 112, ItemClassification.filler),

    # --- Gold Bundles (Useful) ---
    "Gold Bundle (1000 G)":  ItemData(AP_BASE_ID + 4001, ItemClassification.filler),
    "Gold Bundle (2500 G)":  ItemData(AP_BASE_ID + 4002, ItemClassification.filler),
    "Gold Bundle (5000 G)":  ItemData(AP_BASE_ID + 4003, ItemClassification.filler),
    "Gold Bundle (10000 G)": ItemData(AP_BASE_ID + 4004, ItemClassification.filler),

    # --- Progressive Upgrades (Useful) ---
    # Each copy = one "Storage +8" chip capacity upgrade (the shop purchases are checks instead)
    "Progressive Chip Capacity": ItemData(AP_BASE_ID + 4100, ItemClassification.useful),

    # --- Characters (Progression): their routes stay locked in game until they are received ---
    # 9S = route B (and 9S in the Chapter Select), A2 = routes C and D. (5003 was "Route D Key".)
    "9S": ItemData(AP_BASE_ID + 5001, ItemClassification.progression),
    "A2": ItemData(AP_BASE_ID + 5002, ItemClassification.progression),

    # --- Materials (Filler) ---
    "Copper Ore":          ItemData(AP_BASE_ID + 600, ItemClassification.filler),
    "Iron Ore":            ItemData(AP_BASE_ID + 601, ItemClassification.filler),
    "Silver Ore":          ItemData(AP_BASE_ID + 602, ItemClassification.filler),
    "Gold Ore":            ItemData(AP_BASE_ID + 603, ItemClassification.filler),
    "Titanium Alloy":      ItemData(AP_BASE_ID + 535, ItemClassification.filler),
    "Memory Alloy":        ItemData(AP_BASE_ID + 536, ItemClassification.filler),
    "Severed Cable":       ItemData(AP_BASE_ID + 550, ItemClassification.filler),
    "Dented Plate":        ItemData(AP_BASE_ID + 610, ItemClassification.filler),
    "Rusted Clump":        ItemData(AP_BASE_ID + 530, ItemClassification.filler),
    "Natural Rubber":      ItemData(AP_BASE_ID + 634, ItemClassification.filler),
    "Pyrite":              ItemData(AP_BASE_ID + 632, ItemClassification.filler),
    "Meteorite":           ItemData(AP_BASE_ID + 688, ItemClassification.filler),
    "Simple Gadget":       ItemData(AP_BASE_ID + 580, ItemClassification.filler),
    "Elaborate Gadget":    ItemData(AP_BASE_ID + 581, ItemClassification.filler),
    "Complex Gadget":      ItemData(AP_BASE_ID + 582, ItemClassification.filler),
}

# --- Fishing catches (Filler): one copy of each in the pool (item ids 8001..8041, NieREdit) ---
FISH_ITEM_NAMES = [
    "Arowana", "Twinfish", "Killifish", "Carp", "Bloat Fish", "Koi Carp", "Fur Carp", "Freshwater Ray",
    "Arapaima", "Oil Sardine", "Water Flea", "Twoface", "Coelacanth", "Blowfish", "Swordfish", "Mackerel",
    "Horseshoe Crab", "Beetle Fish", "Starfish", "Bream", "Basking Shark", "Killifish Machine",
    "Koi Carp Machine", "Arapaima Machine", "Carp Machine", "Bloat Fish Machine", "Blowfish Machine",
    "Swordfish Machine", "Starfish Machine", "Bream Machine", "Coelacanth Machine", "Mackerel Machine",
    "Horseshoe Crab Machine", "Arowana Machine", "Basking Shark Machine", "Freshwater Ray Machine",
    "Machine Lifeform Head", "Tire", "Gas Cylinder", "Battery", "Broken Firearm",
]
item_table.update({name: ItemData(AP_BASE_ID + 8001 + i, ItemClassification.filler)
                   for i, name in enumerate(FISH_ITEM_NAMES)})

# Items placed more than once in the pool (default: 1 copy)
item_counts: Dict[str, int] = {
    "Progressive Chip Capacity": 6,
}
