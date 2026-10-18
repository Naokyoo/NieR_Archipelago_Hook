"""
NieR: Automata Archipelago Location Definitions (Pack Ultime Propre - Save-Backed Checks)
"""

from typing import Dict, NamedTuple
from BaseClasses import Location
from .Quests import QUEST_TABLE, VERIFIED_QUESTS, quest_location_name, quest_location_offset

AP_BASE_ID = 92000000

class NieRLocation(Location):
    game: str = "NieR Automata"

class LocationData(NamedTuple):
    code: int
    region: str

location_table: Dict[str, LocationData] = {
    # =========================================================
    # 1. WEAPONS (Toutes les 38 Armes du Jeu) - 38 checks
    # =========================================================
    "Weapon: Virtuous Contract":                           LocationData(AP_BASE_ID + 1070, "Abandoned Factory"),
    "Weapon: Cruel Oath":                                  LocationData(AP_BASE_ID + 1071, "Abandoned Factory"),
    "Weapon: Machine Sword":                               LocationData(AP_BASE_ID + 1090, "Pascal's Village"),
    "Weapon: Iron Pipe":                                   LocationData(AP_BASE_ID + 1013, "Flooded City"),
    "Weapon: YoRHa-issue Blade":                           LocationData(AP_BASE_ID + 1080, "Resistance Camp"),
    "Weapon: Faith":                                       LocationData(AP_BASE_ID + 1003, "Flooded City"),
    "Weapon: Beastbane":                                   LocationData(AP_BASE_ID + 1020, "Resistance Camp"),
    "Weapon: Ancient Overlord":                            LocationData(AP_BASE_ID + 1030, "Resistance Camp"),
    "Weapon: Type-4O Sword":                               LocationData(AP_BASE_ID + 1050, "City Ruins"),
    "Weapon: Type-3 Sword":                                LocationData(AP_BASE_ID + 1060, "Resistance Camp"),
    "Weapon: Engine Blade":                                LocationData(AP_BASE_ID + 1875, "Abandoned Factory"),
    "Weapon: Cypress Stick":                               LocationData(AP_BASE_ID + 1876, "Forest Kingdom"),
    "Weapon: Virtuous Treaty":                             LocationData(AP_BASE_ID + 1260, "Abandoned Factory"),
    "Weapon: Cruel Blood Oath":                            LocationData(AP_BASE_ID + 1261, "Desert Zone"),
    "Weapon: Machine Axe":                                 LocationData(AP_BASE_ID + 1270, "Pascal's Village"),
    "Weapon: Fang of the Twins":                           LocationData(AP_BASE_ID + 1213, "Amusement Park"),
    "Weapon: Beastlord":                                   LocationData(AP_BASE_ID + 1220, "City Ruins"),
    "Weapon: Iron Will":                                   LocationData(AP_BASE_ID + 1203, "Desert Zone"),
    "Weapon: Phoenix Sword":                               LocationData(AP_BASE_ID + 1230, "City Ruins"),
    "Weapon: Type-4O Blade":                               LocationData(AP_BASE_ID + 1240, "Resistance Camp"),
    "Weapon: Type-3 Blade":                                LocationData(AP_BASE_ID + 1250, "Resistance Camp"),
    "Weapon: Virtuous Dignity":                            LocationData(AP_BASE_ID + 1470, "Amusement Park"),
    "Weapon: Cruel Arrogance":                             LocationData(AP_BASE_ID + 1471, "Abandoned Factory"),
    "Weapon: Machine Spear":                               LocationData(AP_BASE_ID + 1480, "Pascal's Village"),
    "Weapon: Beastcurse":                                  LocationData(AP_BASE_ID + 1420, "Forest Kingdom"),
    "Weapon: Dragoon Lance":                                LocationData(AP_BASE_ID + 1430, "Forest Kingdom"),
    "Weapon: Phoenix Lance":                               LocationData(AP_BASE_ID + 1400, "Desert Zone"),
    "Weapon: Type-4O Lance":                               LocationData(AP_BASE_ID + 1450, "City Ruins"),
    "Weapon: Spear of the Usurper":                        LocationData(AP_BASE_ID + 1440, "Resistance Camp"),
    "Weapon: Virtuous Grief":                              LocationData(AP_BASE_ID + 1620, "Forest Kingdom"),
    "Weapon: Cruel Lament":                                LocationData(AP_BASE_ID + 1621, "Pascal's Village"),
    "Weapon: Machine Heads":                               LocationData(AP_BASE_ID + 1650, "Pascal's Village"),
    "Weapon: Type-4O Fists":                               LocationData(AP_BASE_ID + 1610, "Resistance Camp"),
    "Weapon: Type-3 Fists":                                LocationData(AP_BASE_ID + 1600, "Resistance Camp"),
    "Weapon: Demon's Cry":                                 LocationData(AP_BASE_ID + 1630, "Amusement Park"),
    "Weapon: Angel's Folly":                               LocationData(AP_BASE_ID + 1640, "City Ruins"),
    "Weapon: Emil Heads":                                  LocationData(AP_BASE_ID + 1877, "Emil's Residence"),
    # Phoenix Dagger: chest at the bottom of the ravine below the Resistance Camp (one of the two chests there
    # needs 9S, which one is unconfirmed -> UNVERIFIED_LOCATIONS). Type-3 Lance: chest on a Flooded City roof.
    "Weapon: Phoenix Dagger":                              LocationData(AP_BASE_ID + 1040, "City Ruins"),
    "Weapon: Type-3 Lance":                                LocationData(AP_BASE_ID + 1460, "Flooded City"),

    # =========================================================
    # 2. 9S HACKING CHESTS (Coffres Verrouillés 9S) - 32 checks
    # =========================================================
    "Factory: Hacking Chest - Silo Crane Upper Floor":     LocationData(AP_BASE_ID + 201, "Abandoned Factory"),
    "Factory: Hacking Chest - Furnace Maintenance Shaft":  LocationData(AP_BASE_ID + 202, "Abandoned Factory"),
    "Factory Underground: Hacking Chest - Cult Sanctuary": LocationData(AP_BASE_ID + 203, "Abandoned Factory"),
    "Factory Underground: Hacking Chest - Crusher Exit":   LocationData(AP_BASE_ID + 204, "Abandoned Factory"),
    "City Ruins: Hacking Chest - Desert Entrance Ledge":   LocationData(AP_BASE_ID + 205, "City Ruins"),
    "City Ruins: Hacking Chest - Giga Crater Water Pipe":  LocationData(AP_BASE_ID + 206, "City Ruins"),
    "City Ruins: Hacking Chest - Broken Highway Span":     LocationData(AP_BASE_ID + 207, "City Ruins"),
    "City Ruins: Hacking Chest - Roots Building 4F Room":  LocationData(AP_BASE_ID + 208, "City Ruins"),
    "City Ruins: Hacking Chest - Commercial Facility 2F":  LocationData(AP_BASE_ID + 209, "City Ruins"),
    "City Ruins: Hacking Chest - Deep Cave Submerged":     LocationData(AP_BASE_ID + 210, "City Ruins"),
    "City Ruins: Hacking Chest - Factory Approach Truck":  LocationData(AP_BASE_ID + 211, "City Ruins"),
    "Resistance Camp: Hacking Chest - Anemone's Quarters": LocationData(AP_BASE_ID + 212, "Resistance Camp"),
    "Desert: Hacking Chest - Housing Complex 3F Balcony":  LocationData(AP_BASE_ID + 213, "Desert Zone"),
    "Desert: Hacking Chest - Deep Cavern Pillar Top":      LocationData(AP_BASE_ID + 214, "Desert Zone"),
    "Desert: Hacking Chest - North Dunes Quicksand Pit":   LocationData(AP_BASE_ID + 215, "Desert Zone"),
    "Desert: Hacking Chest - Oasis Underground Tunnel":    LocationData(AP_BASE_ID + 216, "Desert Zone"),
    "Desert: Hacking Chest - Derelict Oil Pump Rig":       LocationData(AP_BASE_ID + 217, "Desert Zone"),
    "Amusement Park: Hacking Chest - Sewer Pipe Grate":    LocationData(AP_BASE_ID + 218, "Amusement Park"),
    "Amusement Park: Hacking Chest - Coaster Apex Walkway":LocationData(AP_BASE_ID + 219, "Amusement Park"),
    "Amusement Park: Hacking Chest - Theater Basement":    LocationData(AP_BASE_ID + 220, "Amusement Park"),
    "Amusement Park: Hacking Chest - Ferris Wheel Hub":    LocationData(AP_BASE_ID + 221, "Amusement Park"),
    "Pascal's Village: Hacking Chest - High Windmill":     LocationData(AP_BASE_ID + 222, "Pascal's Village"),
    "Pascal's Village: Hacking Chest - Cliffside Hut":     LocationData(AP_BASE_ID + 223, "Pascal's Village"),
    "Forest: Hacking Chest - Castle 1F Throne Approach":   LocationData(AP_BASE_ID + 224, "Forest Kingdom"),
    "Forest: Hacking Chest - Castle 2F Royal Balcony":     LocationData(AP_BASE_ID + 225, "Forest Kingdom"),
    "Forest: Hacking Chest - Castle 3F Library Alcove":    LocationData(AP_BASE_ID + 226, "Forest Kingdom"),
    "Forest: Hacking Chest - Deep Valley Blacksmith":      LocationData(AP_BASE_ID + 227, "Forest Kingdom"),
    "Forest: Hacking Chest - Waterfall Cave Dark Path":    LocationData(AP_BASE_ID + 228, "Forest Kingdom"),
    "Flooded City: Hacking Chest - Sunken Tower Roof":     LocationData(AP_BASE_ID + 229, "Flooded City"),
    "Flooded City: Hacking Chest - Missile Platform Bay":  LocationData(AP_BASE_ID + 230, "Flooded City"),
    "Flooded City: Hacking Chest - Sunken Highway Fallen": LocationData(AP_BASE_ID + 231, "Flooded City"),
    "Copied City: Hacking Chest - Monolith Perimeter":     LocationData(AP_BASE_ID + 232, "Copied City"),

    # =========================================================
    # 3. POD PROGRAMS (Tous les 16 Programmes de Pods) - 16 checks
    # =========================================================
    "Pod Program: Laser (R010)":                           LocationData(AP_BASE_ID + 290, "Resistance Camp"),
    "Pod Program: Mirage (R020)":                          LocationData(AP_BASE_ID + 291, "Resistance Camp"),
    "Pod Program: Hammer (R030)":                          LocationData(AP_BASE_ID + 292, "Resistance Camp"),
    "Pod Program: Blade (R040)":                           LocationData(AP_BASE_ID + 293, "Resistance Camp"),
    "Pod Program: Spear (R050)":                           LocationData(AP_BASE_ID + 294, "Resistance Camp"),
    "Pod Program: P Shield (A060)":                          LocationData(AP_BASE_ID + 295, "Resistance Camp"),
    "Pod Program: Wave (A080)":                            LocationData(AP_BASE_ID + 296, "Pascal's Village"),
    "Pod Program: Wire (A090)":                            LocationData(AP_BASE_ID + 297, "Flooded City"),
    "Pod Program: Decoy (A100)":                           LocationData(AP_BASE_ID + 298, "Resistance Camp"),
    "Pod Program: Slow (A110)":                            LocationData(AP_BASE_ID + 299, "Desert Zone"),
    "Pod Program: Repair (A120)":                          LocationData(AP_BASE_ID + 300, "Resistance Camp"),
    "Pod Program: Bomb (A130)":                            LocationData(AP_BASE_ID + 301, "Resistance Camp"),
    "Pod Program: Gravity (A140)":                         LocationData(AP_BASE_ID + 302, "City Ruins"),
    "Pod Program: Volt (A150)":                            LocationData(AP_BASE_ID + 303, "Route C"),
    "Pod Program: Missile (A160)":                         LocationData(AP_BASE_ID + 304, "Route C"),
    "Pod Program: Scanner (A170)":                         LocationData(AP_BASE_ID + 305, "Route C"),
    "Pod Program: M Shield (R070)":                        LocationData(AP_BASE_ID + 306, "Resistance Camp"),

    # =========================================================
    # 4. BOSSES & HISTOIRE MAJEURE - 20 checks
    # =========================================================
    "Factory: Goliath Buzzsaw Defeated":                   LocationData(AP_BASE_ID + 5, "Abandoned Factory"),
    "Factory: Engels Defeated (Prologue Complete)":         LocationData(AP_BASE_ID + 6, "Abandoned Factory"),
    "Factory Underground: Spider Machine Boss Victory":    LocationData(AP_BASE_ID + 13, "Abandoned Factory"),
    "City Ruins: Goliath Flyer Squadron Defeated":         LocationData(AP_BASE_ID + 39, "City Ruins"),
    "City Ruins: Alien Mothership - Adam & Eve Victory":   LocationData(AP_BASE_ID + 31, "City Ruins"),
    "Desert: Adam Battle Reward":                          LocationData(AP_BASE_ID + 63, "Desert Zone"),
    "Amusement Park: Beauvoir Defeated":                   LocationData(AP_BASE_ID + 83, "Amusement Park"),
    "Amusement Park: Golden Machine Tank Defeated":        LocationData(AP_BASE_ID + 91, "Amusement Park"),
    "Forest: A2 Encounter Victory":                        LocationData(AP_BASE_ID + 122, "Forest Kingdom"),
    "Flooded City: Grun (Ocean Machine) Victory":          LocationData(AP_BASE_ID + 152, "Flooded City"),
    "Copied City: Adam Battle (Climax) Victory":           LocationData(AP_BASE_ID + 172, "Copied City"),
    "Emil's Residence: Emil Duel Victory":                 LocationData(AP_BASE_ID + 178, "Emil's Residence"),
    "The Tower: Main Gate Access Breach":                  LocationData(AP_BASE_ID + 265, "City Ruins"),
    "The Tower: Ko-Shi Battle Victory":                    LocationData(AP_BASE_ID + 269, "City Ruins"),
    "The Tower: Ro-Shi Battle Victory":                    LocationData(AP_BASE_ID + 270, "City Ruins"),
    "The Tower: Ko-Shi & Ro-Shi Fusion Defeated":          LocationData(AP_BASE_ID + 271, "City Ruins"),
    "The Tower: Library of Babel Data Server":             LocationData(AP_BASE_ID + 273, "City Ruins"),
    "The Tower: A2 vs 9S Climax Encounter":                LocationData(AP_BASE_ID + 274, "City Ruins"),
    "Story: Ending A (Battle with Eve Complete)":         LocationData(AP_BASE_ID + 275, "City Ruins"),
    "Story: Ending B (9S Perspective Complete)":          LocationData(AP_BASE_ID + 276, "City Ruins"),

    # =========================================================
    # 5. TERMINAUX D'ACCÈS (Téléporteurs Débloqués) - 16 checks
    # =========================================================
    "Terminal: Resistance Camp Access Point":              LocationData(AP_BASE_ID + 56, "Resistance Camp"),
    "Terminal: City Center Access Point":                  LocationData(AP_BASE_ID + 40, "City Ruins"),
    "Terminal: City Ruins - Near Factory Access Point":    LocationData(AP_BASE_ID + 41, "City Ruins"),
    "Terminal: City Ruins - Near Tower Access Point":      LocationData(AP_BASE_ID + 42, "City Ruins"),
    "Terminal: Abandoned Factory - Hangar Access Point":   LocationData(AP_BASE_ID + 16, "Abandoned Factory"),
    "Terminal: Desert Camp Access Point":                  LocationData(AP_BASE_ID + 74, "Desert Zone"),
    "Terminal: Desert Center Access Point":                LocationData(AP_BASE_ID + 75, "Desert Zone"),
    "Terminal: Desert Housing Complex Access Point":       LocationData(AP_BASE_ID + 76, "Desert Zone"),
    "Terminal: Amusement Park Entrance Access Point":      LocationData(AP_BASE_ID + 92, "Amusement Park"),
    "Terminal: Amusement Park Square Access Point":        LocationData(AP_BASE_ID + 93, "Amusement Park"),
    "Terminal: Machine Village Access Point":              LocationData(AP_BASE_ID + 107, "Pascal's Village"),
    "Terminal: Forest Center Access Point":                LocationData(AP_BASE_ID + 135, "Forest Kingdom"),
    "Terminal: Forest Castle Front Access Point":          LocationData(AP_BASE_ID + 136, "Forest Kingdom"),
    "Terminal: Forest Royal Chamber Access Point":         LocationData(AP_BASE_ID + 137, "Forest Kingdom"),
    "Terminal: Flooded Coast Access Point":                LocationData(AP_BASE_ID + 159, "Flooded City"),
    "Terminal: Copied City Access Point":                  LocationData(AP_BASE_ID + 174, "Copied City"),
    # Access points found in a 100% save, real names unknown (save flag in brackets)
    "Terminal: Desert Access Point [ft_DD]":               LocationData(AP_BASE_ID + 390, "Desert Zone"),
    "Terminal: Abandoned Factory Access Point [ft_RME]":   LocationData(AP_BASE_ID + 391, "Abandoned Factory"),
    "Terminal: Abandoned Factory Access Point [ft_RMI2]":  LocationData(AP_BASE_ID + 392, "Abandoned Factory"),

    # =========================================================
    # Endings: bit = letter index + 1 past E (verified on screen: A-E, K, T, U, W). Story endings A-E and the
    # unverified joke endings sit in the late-game region (Copied City, same as the goal): they can hold
    # important items but never one needed to reach the goal.
    # 7. LES 26 FINS (A à Z Enregistrées dans la Save) - 26 checks
    # =========================================================
    "Ending A: Flowers for m[A]chines":                    LocationData(AP_BASE_ID + 350, "Copied City"),
    "Ending B: or not to [B]e":                            LocationData(AP_BASE_ID + 351, "Route B"),
    "Ending C: meaningless [C]ode":                        LocationData(AP_BASE_ID + 352, "Route C"),
    "Ending D: chil[D]hood's end":                         LocationData(AP_BASE_ID + 353, "Route D"),
    "Ending E: the [E]nd of YoRHa":                        LocationData(AP_BASE_ID + 354, "Route D"),
    "Ending F: mission [F]ailed":                          LocationData(AP_BASE_ID + 355, "Route B"),
    "Ending G: hun[G]ry for knowledge":                    LocationData(AP_BASE_ID + 356, "Route B"),
    "Ending H: a mountain too [H]igh":                     LocationData(AP_BASE_ID + 357, "Copied City"),
    "Ending I: no [I] in team":                            LocationData(AP_BASE_ID + 358, "Copied City"),
    "Ending J: bad [J]udgement":                           LocationData(AP_BASE_ID + 359, "Copied City"),
    "Ending K: aji wo [K]utta (Mackerel Eaten)":           LocationData(AP_BASE_ID + 360, "Resistance Camp"),
    "Ending L: [L]one wolf":                               LocationData(AP_BASE_ID + 361, "Copied City"),
    "Ending M: break ti[M]e":                              LocationData(AP_BASE_ID + 362, "Route C"),
    "Ending N: [N]o man's village":                        LocationData(AP_BASE_ID + 363, "Route C"),
    "Ending O: just y[O]u and me":                         LocationData(AP_BASE_ID + 364, "Route C"),
    "Ending P: corru[P]tion":                              LocationData(AP_BASE_ID + 365, "Route C"),
    "Ending Q: [Q]uestionable actions":                    LocationData(AP_BASE_ID + 366, "Route C"),
    "Ending R: mav[R]ick":                                 LocationData(AP_BASE_ID + 367, "Route C"),
    "Ending S: city e[S]cape":                             LocationData(AP_BASE_ID + 368, "Route C"),
    "Ending T: fa[T]al error (OS Chip Removed)":           LocationData(AP_BASE_ID + 369, "Resistance Camp"),
    "Ending U: deb[U]nked":                                LocationData(AP_BASE_ID + 370, "City Ruins"),
    "Ending V: reckamp [V]anished":                        LocationData(AP_BASE_ID + 371, "Route C"),
    "Ending W: broken [W]ings (Prologue Death)":           LocationData(AP_BASE_ID + 372, "Abandoned Factory"),
    "Ending X: time for thin[X]ing":                       LocationData(AP_BASE_ID + 373, "Route C"),
    "Ending Y: head[Y] battle (Emil Climax)":              LocationData(AP_BASE_ID + 374, "Route C"),
    "Ending Z: over[Z]ealous":                             LocationData(AP_BASE_ID + 375, "Route C"),

    # =========================================================
    # 8. EXTENSIONS DE STOCKAGE & ARÈNES - 14 checks
    # =========================================================
    "Storage: Chip Capacity Upgrade 40 -> 48":             LocationData(AP_BASE_ID + 380, "Resistance Camp"),
    "Storage: Chip Capacity Upgrade 48 -> 64":             LocationData(AP_BASE_ID + 381, "Resistance Camp"),
    "Storage: Chip Capacity Upgrade 64 -> 80":             LocationData(AP_BASE_ID + 382, "Resistance Camp"),
    "Storage: Chip Capacity Upgrade 80 -> 96":             LocationData(AP_BASE_ID + 383, "Resistance Camp"),
    "Storage: Chip Capacity Upgrade 96 -> 112":            LocationData(AP_BASE_ID + 384, "Resistance Camp"),
    "Storage: Chip Capacity Upgrade 112 -> 128":           LocationData(AP_BASE_ID + 385, "Resistance Camp"),
    "Module: Dress Module (Emil's Shop)":                  LocationData(AP_BASE_ID + 289, "City Ruins"),
    "Module: Heavy Armor":                                 LocationData(AP_BASE_ID + 386, "Resistance Camp"),
    "Secret: Kaine's Shack Lunar Tear":                    LocationData(AP_BASE_ID + 260, "City Ruins"),
    "Colosseum: Flooded Colosseum Trial Rank C":           LocationData(AP_BASE_ID + 261, "Flooded City"),
    "Colosseum: Flooded Colosseum Trial Rank B":           LocationData(AP_BASE_ID + 387, "Flooded City"),
    "Colosseum: Desert Trial Arena Rank C":                LocationData(AP_BASE_ID + 262, "Desert Zone"),
    "Colosseum: Desert Trial Arena Rank B":                LocationData(AP_BASE_ID + 263, "Desert Zone"),
    "Colosseum: Forest Colosseum Trial Rank C":            LocationData(AP_BASE_ID + 264, "Forest Kingdom"),
}

# Side quests (real ids/names, see Quests.py)
location_table.update({quest_location_name(qid): LocationData(AP_BASE_ID + quest_location_offset(qid), region)
                       for qid, (_, region) in QUEST_TABLE.items()})
VERIFIED_QUEST_LOCATIONS = {quest_location_name(qid) for qid in VERIFIED_QUESTS}

# Fishing: first catch of each species, fish machines and junk included (item ids 8001..8041, from
# NieREdit). The hook reports every catch (verified 2026-10-17: fishing routine 0x629000, Carp Machine);
# the bridge also syncs fish found in the save inventory. Location id = AP_BASE_ID + item id.
FISH_NAMES = {
    8001: "Arowana",
    8002: "Twinfish",
    8003: "Killifish",
    8004: "Carp",
    8005: "Bloat Fish",
    8006: "Koi Carp",
    8007: "Fur Carp",
    8008: "Freshwater Ray",
    8009: "Arapaima",
    8010: "Oil Sardine",
    8011: "Water Flea",
    8012: "Twoface",
    8013: "Coelacanth",
    8014: "Blowfish",
    8015: "Swordfish",
    8016: "Mackerel",
    8017: "Horseshoe Crab",
    8018: "Beetle Fish",
    8019: "Starfish",
    8020: "Bream",
    8021: "Basking Shark",
    8022: "Killifish Machine",
    8023: "Koi Carp Machine",
    8024: "Arapaima Machine",
    8025: "Carp Machine",
    8026: "Bloat Fish Machine",
    8027: "Blowfish Machine",
    8028: "Swordfish Machine",
    8029: "Starfish Machine",
    8030: "Bream Machine",
    8031: "Coelacanth Machine",
    8032: "Mackerel Machine",
    8033: "Horseshoe Crab Machine",
    8034: "Arowana Machine",
    8035: "Basking Shark Machine",
    8036: "Freshwater Ray Machine",
    8037: "Machine Lifeform Head",
    8038: "Tire",
    8039: "Gas Cylinder",
    8040: "Battery",
    8041: "Broken Firearm",
}
location_table.update({f"Fishing: {name}": LocationData(AP_BASE_ID + fid, "City Ruins")
                       for fid, name in FISH_NAMES.items()})

# Story milestones, detected by the bridge from the story phase (see STORY_MILESTONES in the bridge).
# Trusted from the phase data (2026-10-17, user's call); move back to excluded if one misbehaves.
STORY_LOCATIONS = {
    "Story: Arrive at the Resistance Camp": (500, "Resistance Camp"),
    "Story: Reach the Desert": (501, "Desert Zone"),
    "Story: Reach the Amusement Park": (502, "Amusement Park"),
    "Story: Reach Pascal's Village": (503, "Pascal's Village"),
    "Story: Reach the Forest Castle": (504, "Forest Kingdom"),
    "Story: Flooded City Battle": (505, "Flooded City"),
    "Story: Giant Machine Defeated": (506, "City Ruins"),
    "Story: Underground Factory Boss Defeated": (507, "Abandoned Factory"),
    "Story: Eve Defeated": (508, "Copied City"),
    # Routes C/D: in their route region, behind A2
    "Story C: Invasion of the City Ruins": (509, "Route C"),
    "Story C: Escape from the Bunker": (510, "Route C"),
    "Story C: 2B's Last Stand": (511, "Route C"),
    "Story C: Desert Boss Defeated (A2)": (512, "Route C"),
    "Story C: Giant Robot Battle Won (A2)": (513, "Route C"),
    "Story C: Forest Castle (9S)": (514, "Route C"),
    "Story C: Flooded City (9S)": (515, "Route C"),
    "Story C: Amusement Park (A2)": (516, "Route C"),
    "Story C: Reach the Tower": (517, "Route C"),
    "Story C: Tower Library": (518, "Route C"),
    "Story D: Tower Finale": (519, "Route D"),
}
location_table.update({name: LocationData(AP_BASE_ID + offset, region)
                       for name, (offset, region) in STORY_LOCATIONS.items()})

# Player level milestones (the hook computes the level from the engine level table). Leveling is always
# possible, so they can never lock the run. Location id = AP_BASE_ID + 400 + level.
location_table.update({f"Level: Reach Lv {lv}": LocationData(AP_BASE_ID + 400 + lv,
                                                             "Abandoned Factory" if lv <= 5 else "City Ruins")
                       for lv in range(5, 55, 5)})

# =========================================================
# RUN SAFETY
# =========================================================
# Locations the hook/bridge has NO way to detect yet: removed from the pool so that no item can be
# lost there. Put them back once a detection is implemented and verified in game.
UNDETECTABLE_LOCATIONS = {
    "Terminal: Copied City Access Point",  # ft_Copied never appears, not even in a save past ending D
    "Story: Ending A (Battle with Eve Complete)",  # "Ending_A" token never appears in any save; duplicate of
    "Story: Ending B (9S Perspective Complete)",   # the ending A/B locations, which use the verified mask
    "Factory Underground: Spider Machine Boss Victory",
    "City Ruins: Goliath Flyer Squadron Defeated",
    "Flooded City: Grun (Ocean Machine) Victory",
    "The Tower: Main Gate Access Breach",
    "The Tower: Ko-Shi Battle Victory",
    "The Tower: Ro-Shi Battle Victory",
    "The Tower: Ko-Shi & Ro-Shi Fusion Defeated",
    "The Tower: Library of Babel Data Server",
    "The Tower: A2 vs 9S Climax Encounter",
    "Secret: Kaine's Shack Lunar Tear",
    "Colosseum: Flooded Colosseum Trial Rank C",
    "Colosseum: Flooded Colosseum Trial Rank B",
    "Colosseum: Desert Trial Arena Rank C",
    "Colosseum: Desert Trial Arena Rank B",
    "Colosseum: Forest Colosseum Trial Rank C",
}
# 9S hacking chests: tested 2026-10-17, a hacked chest goes through the normal chest routine (0x80032D);
# 0x800573 only adds weapons. Nothing tells them apart, and these names/counts were never real data.
UNDETECTABLE_LOCATIONS |= {name for name in location_table if "Hacking Chest" in name}
assert UNDETECTABLE_LOCATIONS <= set(location_table), UNDETECTABLE_LOCATIONS - set(location_table)
location_table = {name: data for name, data in location_table.items() if name not in UNDETECTABLE_LOCATIONS}

# Locations whose detection is verified in game (or uses the exact same path as a verified one).
# Everything else is EXCLUDED: still checkable, but it only ever holds filler, so an unverified
# detection can never lock the run.
TRUSTED_PREFIXES = ("Weapon: ", "Storage: ", "Module: ", "Level: ", "Fishing: ",
                    "Story: ", "Story C: ", "Story D: ", "Ending ")
TRUSTED_LOCATIONS = {
    # Pod programs: shop (R020-R070), prologue (R010) and Route A/B side quest rewards
    "Pod Program: Laser (R010)", "Pod Program: Mirage (R020)", "Pod Program: Hammer (R030)",
    "Pod Program: Blade (R040)", "Pod Program: Spear (R050)", "Pod Program: P Shield (A060)",
    "Pod Program: M Shield (R070)", "Pod Program: Wave (A080)", "Pod Program: Wire (A090)",
    "Pod Program: Slow (A110)", "Pod Program: Repair (A120)",
    # Side quest rewards (routes A/B): Find a Present (q171) and Retrieve the Confidential Intel (q640)
    "Pod Program: Bomb (A130)", "Pod Program: Gravity (A140)",
    # Ending bits verified in real saves
    "Ending A: Flowers for m[A]chines", "Ending B: or not to [B]e", "Ending C: meaningless [C]ode",
    "Ending D: chil[D]hood's end", "Ending E: the [E]nd of YoRHa", "Ending U: deb[U]nked",
    "Ending T: fa[T]al error (OS Chip Removed)", "Ending K: aji wo [K]utta (Mackerel Eaten)",
    "Ending W: broken [W]ings (Prologue Death)",
    # Prologue bosses (story phase string)
    "Factory: Goliath Buzzsaw Defeated", "Factory: Engels Defeated (Prologue Complete)",
    # Bosses detected from the story phase (phase after the fight), like the Story milestones
    "Desert: Adam Battle Reward", "Amusement Park: Golden Machine Tank Defeated",
    "Amusement Park: Beauvoir Defeated", "Copied City: Adam Battle (Climax) Victory",
    "City Ruins: Alien Mothership - Adam & Eve Victory",
    # Access points: ft_* entries of the save "Flags" block, all seen unlocked in real saves
    # (ft_BK stays excluded: only in one old save and probably the Bunker, not the factory hangar)
    "Terminal: Resistance Camp Access Point", "Terminal: City Center Access Point",
    "Terminal: City Ruins - Near Factory Access Point", "Terminal: City Ruins - Near Tower Access Point",
    "Terminal: Desert Camp Access Point", "Terminal: Desert Center Access Point",
    "Terminal: Desert Housing Complex Access Point", "Terminal: Amusement Park Entrance Access Point",
    "Terminal: Amusement Park Square Access Point", "Terminal: Machine Village Access Point",
    "Terminal: Forest Center Access Point", "Terminal: Forest Castle Front Access Point",
    "Terminal: Forest Royal Chamber Access Point", "Terminal: Flooded Coast Access Point",
}
assert TRUSTED_LOCATIONS <= set(location_table), TRUSTED_LOCATIONS - set(location_table)
# Detected by a trusted path but with an unknown source/region: filler only for now.
UNVERIFIED_LOCATIONS = {"Weapon: Phoenix Dagger"}
assert UNVERIFIED_LOCATIONS <= set(location_table)
EXCLUDED_LOCATIONS = {name for name in location_table
                      if (name not in TRUSTED_LOCATIONS and not name.startswith(TRUSTED_PREFIXES))
                      or name in UNVERIFIED_LOCATIONS}
