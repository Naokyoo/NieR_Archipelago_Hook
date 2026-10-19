#!/usr/bin/env python3
"""
NieR: Automata - Archipelago MultiWorld Bridge & Client
Connects to the C++ dinput8.dll hook via TCP (127.0.0.1:52140)
and to the Archipelago MultiWorld Server via WebSocket.
"""

import socket
import json
import threading
import time
import sys
import os
import math
import uuid
import asyncio
import ssl
import struct
import re
import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import websockets
except ImportError:
    websockets = None

# Verify wss:// certificates with certifi's CA bundle when available: the Windows certificate store
# can lack the root used by archipelago.gg, which makes the connection fail with CERTIFICATE_VERIFY_FAILED.
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 52140

AP_BASE_ID = 92000000

# -------------------------------------------------------------
# Archipelago Database Loader (Locations & Items)
# -------------------------------------------------------------
AP_LOCATIONS = {}
AP_ITEMS = {}

def load_ap_definitions():
    global AP_LOCATIONS, AP_ITEMS
    paths_to_check = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ap_definitions.json"),
        os.path.join(os.getcwd(), "ap_definitions.json"),
        "C:\\Program Files (x86)\\Steam\\steamapps\\common\\NieRAutomata\\ap_definitions.json"
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    AP_LOCATIONS = data.get("locations", {})
                    AP_ITEMS = data.get("items", {})
                    print(f"[+] Loaded {len(AP_LOCATIONS)} locations and {len(AP_ITEMS)} items from {p}")
                    return
            except Exception as e:
                print(f"[-] Error loading {p}: {e}")

load_ap_definitions()

# -------------------------------------------------------------
# Chest Location Database (Mapped by 3D World GPS)
# -------------------------------------------------------------
KNOWN_CHESTS = []

def load_chests_database():
    global KNOWN_CHESTS
    paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_chests.json"),
        os.path.join(os.getcwd(), "known_chests.json")
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    KNOWN_CHESTS = json.load(f)
                verified = sum(1 for c in KNOWN_CHESTS if c.get("verified"))
                print(f"[+] [Database] Loaded {len(KNOWN_CHESTS)} chests from {p} ({verified} verified GPS)")
                return
            except Exception as e:
                print(f"[-] [Database] Error loading {p}: {e}")

load_chests_database()

# -------------------------------------------------------------
# Persistent "received items" state (prevents duplicate consumables/gold across sessions)
# -------------------------------------------------------------
RECEIVED_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ap_received_state.json")
_state_lock = threading.Lock()

def load_received_state():
    try:
        with open(RECEIVED_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_received_state(state):
    try:
        tmp = RECEIVED_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, RECEIVED_STATE_FILE)
    except Exception as e:
        print(f"[-] Could not persist received-items state: {e}")

# Gold bundle item IDs -> gold amount
GOLD_BUNDLE_AMOUNTS = {4001: 1000, 4002: 2500, 4003: 5000, 4004: 10000}

# Characters (apworld Items.py): routes stay locked in game until their character is received.
# "9S" opens route B (and 9S in the Chapter Select), "A2" routes C and D. 5003 = the old "Route D Key" (old seeds).
CHARACTER_ITEMS = {5001: ("9S", ("B",)), 5002: ("A2", ("C", "D")), 5003: ("Route D Key", ("D",))}

def is_idempotent_item(nier_id):
    """Pod programs (2001..2024), the logic-only Hacking Module (2100) and the characters: single-ownership
    items, safe to re-send. Plug-in chips are counted like stackable items (a player can own several copies).
    Weapons are handled by is_weapon_id."""
    try:
        nid = int(nier_id)
        return (2001 <= nid <= 2024) or nid == 2100 or nid in CHARACTER_ITEMS
    except Exception:
        return False

# Memory ID to Friendly Name
# Real in-game weapon IDs (NieRHook memory reference sheet; 1070 = Virtuous Contract and
# 1240 = Type-40 Blade confirmed in-game 2026-10-17). AP ids are AP_BASE_ID + these ids.
WEAPON_NAMES = {
    1003: "Faith",
    1013: "Iron Pipe",
    1020: "Beastbane",
    1030: "Ancient Overlord",
    1040: "Phoenix Dagger",
    1050: "Type-4O Sword",
    1060: "Type-3 Sword",
    1070: "Virtuous Contract",
    1071: "Cruel Oath",
    1080: "YoRHa-issue Blade",
    1090: "Machine Sword",
    1203: "Iron Will",
    1213: "Fang of the Twins",
    1220: "Beastlord",
    1230: "Phoenix Sword",
    1240: "Type-4O Blade",
    1250: "Type-3 Blade",
    1260: "Virtuous Treaty",
    1261: "Cruel Blood Oath",
    1270: "Machine Axe",
    1400: "Phoenix Lance",
    1420: "Beastcurse",
    1430: "Dragoon Lance",
    1440: "Spear of the Usurper",
    1450: "Type-4O Lance",
    1460: "Type-3 Lance",
    1470: "Virtuous Dignity",
    1471: "Cruel Arrogance",
    1480: "Machine Spear",
    1600: "Type-3 Fists",
    1610: "Type-4O Fists",
    1620: "Virtuous Grief",
    1621: "Cruel Lament",
    1630: "Demon's Cry",
    1640: "Angel's Folly",
    1650: "Machine Heads",
    1875: "Engine Blade",
    1876: "Cypress Stick",
    1877: "Emil Heads",
}

def is_weapon_id(item_id):
    """Returns True if the ID represents a weapon in NieR: Automata."""
    try:
        return int(item_id) in WEAPON_NAMES
    except Exception:
        return False

# -------------------------------------------------------------
# Archipelago Location Mappings (Save-Backed 215 Checks)
# -------------------------------------------------------------
# 1. Weapon checks (AP_BASE_ID + weapon_id)
WEAPON_TO_LOCATION_MAP = {w_id: (AP_BASE_ID + w_id, f"Weapon: {w_name}") for w_id, w_name in WEAPON_NAMES.items()}

# 2. Pod Programs & Special Shop Modules - 14 checks
# Real pod program ids (NieREdit PodProgramId) -> location. Key modules are inventory items:
# Dress Module = 980, Heavy Armor A/B = 981/982 (the player keeps them, the hook only reports the check).
POD_PROGRAM_MAP = {
    2001: (AP_BASE_ID + 290, "Pod Program: Laser (R010)"),
    2002: (AP_BASE_ID + 291, "Pod Program: Mirage (R020)"),
    2003: (AP_BASE_ID + 292, "Pod Program: Hammer (R030)"),
    2004: (AP_BASE_ID + 293, "Pod Program: Blade (R040)"),
    2005: (AP_BASE_ID + 294, "Pod Program: Spear (R050)"),
    2007: (AP_BASE_ID + 295, "Pod Program: P Shield (A060)"),
    2008: (AP_BASE_ID + 296, "Pod Program: Wave (A080)"),
    2009: (AP_BASE_ID + 297, "Pod Program: Wire (A090)"),
    2010: (AP_BASE_ID + 298, "Pod Program: Decoy (A100)"),
    2011: (AP_BASE_ID + 299, "Pod Program: Slow (A110)"),
    2012: (AP_BASE_ID + 300, "Pod Program: Repair (A120)"),
    2015: (AP_BASE_ID + 301, "Pod Program: Bomb (A130)"),
    2019: (AP_BASE_ID + 302, "Pod Program: Gravity (A140)"),
    2021: (AP_BASE_ID + 303, "Pod Program: Volt (A150)"),
    2022: (AP_BASE_ID + 304, "Pod Program: Missile (A160)"),
    2024: (AP_BASE_ID + 305, "Pod Program: Scanner (A170)"),
    2006: (AP_BASE_ID + 306, "Pod Program: M Shield (R070)"),
    980: (AP_BASE_ID + 289, "Module: Dress Module (Emil's Shop)"),
    981: (AP_BASE_ID + 386, "Module: Heavy Armor"),
    982: (AP_BASE_ID + 386, "Module: Heavy Armor"),
}

# -------------------------------------------------------------
# Save Data Maps (Endings, Terminals, Quests, Bosses)
# -------------------------------------------------------------
ENDING_BIT_MAP = {
    0: (AP_BASE_ID + 350, "Ending A: Flowers for m[A]chines"),
    1: (AP_BASE_ID + 351, "Ending B: or not to [B]e"),
    2: (AP_BASE_ID + 352, "Ending C: meaningless [C]ode"),
    3: (AP_BASE_ID + 353, "Ending D: chil[D]hood's end"),
    4: (AP_BASE_ID + 354, "Ending E: the [E]nd of YoRHa"),
    # Past E, bit = internal letter index + 1 (bit 5 unused). Internal index = cPf30 ending phase id - 4,
    # cross-checked with the flag array at save 0x39514. Verified in game by diffing saves: K (11), T (20),
    # W (23, fresh game + broken wings). U (21) is the only other bit set in that run. Others follow the rule.
    6: (AP_BASE_ID + 355, "Ending F: mission [F]ailed"),
    7: (AP_BASE_ID + 356, "Ending G: hun[G]ry for knowledge"),
    8: (AP_BASE_ID + 357, "Ending H: a mountain too [H]igh"),
    9: (AP_BASE_ID + 358, "Ending I: no [I] in team"),
    10: (AP_BASE_ID + 359, "Ending J: bad [J]udgement"),
    11: (AP_BASE_ID + 360, "Ending K: aji wo [K]utta (Mackerel Eaten)"),  # verified 2026-10-17
    12: (AP_BASE_ID + 361, "Ending L: [L]one wolf"),
    13: (AP_BASE_ID + 362, "Ending M: break ti[M]e"),
    14: (AP_BASE_ID + 363, "Ending N: [N]o man's village"),
    15: (AP_BASE_ID + 364, "Ending O: just y[O]u and me"),
    16: (AP_BASE_ID + 365, "Ending P: corru[P]tion"),
    17: (AP_BASE_ID + 366, "Ending Q: [Q]uestionable actions"),
    18: (AP_BASE_ID + 367, "Ending R: mav[R]ick"),
    19: (AP_BASE_ID + 368, "Ending S: city e[S]cape"),
    20: (AP_BASE_ID + 369, "Ending T: fa[T]al error (OS Chip Removed)"),  # verified 2026-10-17
    21: (AP_BASE_ID + 370, "Ending U: deb[U]nked"),  # verified 2026-10-17
    22: (AP_BASE_ID + 371, "Ending V: reckamp [V]anished"),
    23: (AP_BASE_ID + 372, "Ending W: broken [W]ings (Prologue Death)"),  # verified 2026-10-17
    24: (AP_BASE_ID + 373, "Ending X: time for thin[X]ing"),
    25: (AP_BASE_ID + 374, "Ending Y: head[Y] battle (Emil Climax)"),
    26: (AP_BASE_ID + 375, "Ending Z: over[Z]ealous"),
}

# Number of "Storage +8" upgrades bought at the Resistance Camp shop (uint32 at file offset 0x324B8,
# right before the plug-in chip table). Verified 2026-10-17: 0 -> 1 after buying the first upgrade.
# Each entry: (upgrades bought >=, location id, name).
# Progressive Chip Capacity: the hook reports each purchase live (STORAGE_UPGRADE check) and keeps this
# counter equal to the number of "Progressive Chip Capacity" items received, so the save no longer
# reflects purchases -> save-based storage checks stay disabled.
STORAGE_UPGRADES_OFFSET = 0x324B8
STORAGE_CAP_VERIFIED = False
STORAGE_CAPACITY_CHECKS = [
    (1, AP_BASE_ID + 380, "Storage: Chip Capacity Upgrade 40 -> 48"),
    (2, AP_BASE_ID + 381, "Storage: Chip Capacity Upgrade 48 -> 64"),
    (3, AP_BASE_ID + 382, "Storage: Chip Capacity Upgrade 64 -> 80"),
    (4, AP_BASE_ID + 383, "Storage: Chip Capacity Upgrade 80 -> 96"),
    (5, AP_BASE_ID + 384, "Storage: Chip Capacity Upgrade 96 -> 112"),
    (6, AP_BASE_ID + 385, "Storage: Chip Capacity Upgrade 112 -> 128"),
]

# Shop overlay: what the maintenance shops (Resistance Camp / Bunker) sell, whose contents are scouted
# and shown in game: R020-R070 pod programs (the others are quest rewards / field finds), then the
# storage upgrades, of which only the next one to buy is displayed
SHOP_POD_IDS = (2002, 2003, 2004, 2005, 2007, 2006)
SHOP_HINT_LOCATIONS = [POD_PROGRAM_MAP[pid] for pid in SHOP_POD_IDS] + [(cid, name) for _, cid, name in STORAGE_CAPACITY_CHECKS]
SHOP_HINT_IDS = {cid for cid, _ in SHOP_HINT_LOCATIONS}
STORAGE_LOCATION_IDS = {cid for _, cid, _ in STORAGE_CAPACITY_CHECKS}

# Player level milestones: the hook computes the level from the engine's level table and sends
# {"event": "level"} whenever it changes. Location id = AP_BASE_ID + 400 + level.
LEVEL_MILESTONES = range(5, 55, 5)
LEVEL_LOCATION_BASE = AP_BASE_ID + 400
# EXP needed for each level 1..99, dumped by the hook from the engine table ([LEVEL_TABLE] log line).
LEVEL_XP_TABLE = [
    0, 48, 139, 294, 525, 843, 1259, 1782, 2421, 3184, 4080, 5116, 6300, 7638, 9139, 10809, 12654, 14682,
    16898, 19309, 21920, 24739, 27770, 31019, 34493, 38196, 42134, 46312, 50736, 55412, 60343, 65536, 70994,
    76724, 82730, 89017, 95590, 102453, 109611, 117070, 124832, 132904, 141288, 149991, 159016, 168368,
    178051, 188068, 198426, 209127, 220177, 231578, 243336, 255454, 267937, 280788, 294011, 307611, 321591,
    335956, 350709, 365854, 381395, 397336, 413680, 430431, 447594, 465171, 483167, 501585, 520429, 539702,
    559408, 579552, 600135, 621162, 642637, 664562, 686942, 709780, 733079, 756843, 781075, 805779, 830958,
    856615, 882754, 909379, 936491, 964096, 992196, 1020794, 1049894, 1079499, 1109612, 1140237, 1171376,
    1203033, 1235211,
]
assert len(LEVEL_XP_TABLE) == 99
SAVE_XP_OFFSET = 0x3871C          # int32 EXP in SlotData
SAVE_INVENTORY_OFFSET = 0x30570   # 256 x {id, status, qty}

def level_from_xp(xp):
    return sum(1 for need in LEVEL_XP_TABLE if need <= xp)

# Story milestones of routes A/B, detected from the story phase (hook "phase" event + save phase string).
# Phase names come from the game exe and the YoRHa Protocol phase list; a boss counts as defeated once the
# phase after its fight is reached. Matched by prefix: the save holds internal names ("51_AB_MainDesert")
# while YP shows descriptions ("51_AB_Great Desert_...").
STORY_MILESTONES = [
    (AP_BASE_ID + 500, "Story: Arrive at the Resistance Camp", ("40_AB_",)),
    (AP_BASE_ID + 501, "Story: Reach the Desert", ("51_AB_", "51_00_A_", "51_10_AB_")),
    (AP_BASE_ID + 63, "Desert: Adam Battle Reward", ("58_50_AB_",)),  # 58_AB_ = the floor collapse BEFORE the fight
    (AP_BASE_ID + 502, "Story: Reach the Amusement Park", ("70_AB_", "70_00_AB_")),
    (AP_BASE_ID + 91, "Amusement Park: Golden Machine Tank Defeated", ("70_20_AB_", "76_AB_", "76_10_AB_", "76_20_AB_")),
    (AP_BASE_ID + 83, "Amusement Park: Beauvoir Defeated", ("79_50_AB_", "79_90_AB_", "80_00_AB_", "80_10_AB_")),
    (AP_BASE_ID + 503, "Story: Reach Pascal's Village", ("80_00_AB_", "80_10_AB_")),
    (AP_BASE_ID + 504, "Story: Reach the Forest Castle", ("60_05_AB_", "60_10_AB_", "60_20_AB_")),
    # Seen in a real route A run (2026-10-18): after Pascal's Village, Adam & Eve in the alien ship
    (AP_BASE_ID + 31, "City Ruins: Alien Mothership - Adam & Eve Victory", ("10_30_AB_Alien_Ship_End",)),
    (AP_BASE_ID + 505, "Story: Flooded City Battle", ("90_AB_", "91_AB_")),
    (AP_BASE_ID + 506, "Story: Giant Machine Defeated", ("100_A_", "95_00_B_", "96_B_")),
    (AP_BASE_ID + 172, "Copied City: Adam Battle (Climax) Victory", ("120_AB_", "130_00_A_")),  # route B / route A
    (AP_BASE_ID + 507, "Story: Underground Factory Boss Defeated", ("140_90_A_", "140_90_B_", "150_B_")),
    (AP_BASE_ID + 508, "Story: Eve Defeated", ("200_60_AB_", "200_80_AB_")),
    # Routes C/D (2B start, then A2 / 9S)
    (AP_BASE_ID + 509, "Story C: Invasion of the City Ruins", ("20_CD_", "21_CD_")),
    (AP_BASE_ID + 510, "Story C: Escape from the Bunker", ("40_CD_",)),
    (AP_BASE_ID + 511, "Story C: 2B's Last Stand", ("50_20_CD_", "60_CD_")),
    (AP_BASE_ID + 512, "Story C: Desert Boss Defeated (A2)", ("110_CD_",)),  # back to the village after the desert
    (AP_BASE_ID + 513, "Story C: Giant Robot Battle Won (A2)", ("120_90_CD_", "120_95_CD_")),
    (AP_BASE_ID + 514, "Story C: Forest Castle (9S)", ("160_00_CD_", "170_00_CD_")),
    (AP_BASE_ID + 515, "Story C: Flooded City (9S)", ("180_10_CD_", "180_20_CD_")),
    (AP_BASE_ID + 516, "Story C: Amusement Park (A2)", ("240_50_CD_",)),
    (AP_BASE_ID + 517, "Story C: Reach the Tower", ("270_CD_", "275_CD_", "290_CD_")),
    (AP_BASE_ID + 518, "Story C: Tower Library", ("293_CD_", "297_CD_")),
    (AP_BASE_ID + 519, "Story D: Tower Finale", ("340_D_", "345_D_")),
]

def story_milestones_for(phase):
    return [(loc_id, name) for loc_id, name, prefixes in STORY_MILESTONES if phase.startswith(prefixes)]

# Goal option (apworld Options.Goal) -> location whose check completes the seed
GOAL_LOCATIONS = {
    0: AP_BASE_ID + 6,    # prologue_engels: Factory: Engels Defeated
    1: AP_BASE_ID + 350,  # ending_a: Ending A
    2: AP_BASE_ID + 354,  # ending_e: Ending E
}

# Fishing: one location per species, id = AP_BASE_ID + item id (8001..8041)
FISH_ITEM_IDS = range(8001, 8042)

TERMINAL_MAP = {
    'ft_BK': (AP_BASE_ID + 16, "Terminal: Abandoned Factory - Hangar Access Point"),
    'ft_RC': (AP_BASE_ID + 56, "Terminal: Resistance Camp Access Point"),
    'ft_CC': (AP_BASE_ID + 40, "Terminal: City Center Access Point"),
    'ft_CRb': (AP_BASE_ID + 41, "Terminal: City Ruins - Near Factory Access Point"),
    'ft_CS': (AP_BASE_ID + 42, "Terminal: City Ruins - Near Tower Access Point"),
    'ft_DC': (AP_BASE_ID + 74, "Terminal: Desert Camp Access Point"),
    'ft_DI': (AP_BASE_ID + 75, "Terminal: Desert Center Access Point"),
    'ft_DO': (AP_BASE_ID + 76, "Terminal: Desert Housing Complex Access Point"),
    'ft_AP': (AP_BASE_ID + 92, "Terminal: Amusement Park Entrance Access Point"),
    'ft_AS': (AP_BASE_ID + 93, "Terminal: Amusement Park Square Access Point"),
    'ft_PV': (AP_BASE_ID + 107, "Terminal: Machine Village Access Point"),
    'ft_FC': (AP_BASE_ID + 135, "Terminal: Forest Center Access Point"),
    'ft_FC2': (AP_BASE_ID + 136, "Terminal: Forest Castle Front Access Point"),
    'ft_FC3': (AP_BASE_ID + 137, "Terminal: Forest Royal Chamber Access Point"),
    'ft_SC': (AP_BASE_ID + 159, "Terminal: Flooded Coast Access Point"),
    'ft_Copied': (AP_BASE_ID + 174, "Terminal: Copied City Access Point"),
    # Seen in a 100% save, real names unknown
    'ft_DD': (AP_BASE_ID + 390, "Terminal: Desert Access Point [ft_DD]"),
    'ft_RME': (AP_BASE_ID + 391, "Terminal: Abandoned Factory Access Point [ft_RME]"),
    'ft_RMI2': (AP_BASE_ID + 392, "Terminal: Abandoned Factory Access Point [ft_RMI2]"),
}

# Side quests, built from ap_definitions.json (apworld Quests.py): location id =
# AP_BASE_ID + QUEST_LOCATION_OFFSET + int(qid[1:], 16). Quest ids are hex (q120, qa1c...).
QUEST_LOCATION_OFFSET = 10000
QUEST_MAP = {}
for _loc_id, _loc_name in AP_LOCATIONS.items():
    _q = int(_loc_id) - AP_BASE_ID - QUEST_LOCATION_OFFSET
    if _loc_name.startswith("Quest: ") and 0 <= _q <= 0xfff:
        QUEST_MAP[f"q{_q:03x}"] = (int(_loc_id), _loc_name)

def completed_quests(ascii_blob):
    """Quest ids completed in a SceneState blob. "qNNN/DONE|FIN" is the current state, "qNNN_DONE|FIN"
    a permanent marker that stays after the quest later turns to BREAK."""
    return set(re.findall(r'\b(q[0-9a-f]{3})[/_](?:DONE|FIN)\b', ascii_blob))

# Desert Adam, Golden Tank, Beauvoir and Copied City Adam moved to STORY_MILESTONES (their SceneState tokens
# are transient: gone in a 100% save).
BOSS_MAP = {
    'RM_after_bossbattle': (AP_BASE_ID + 6, "Factory: Engels Defeated (Prologue Complete)"),
    'battle_a2': (AP_BASE_ID + 122, "Forest: A2 Encounter Victory"),
    'forest_clear': (AP_BASE_ID + 122, "Forest: A2 Encounter Victory"),
    'EmilQuest_clear': (AP_BASE_ID + 178, "Emil's Residence: Emil Duel Victory"),
}

def read_file_shared(filepath, retries=3):
    """Safely reads a save file on Windows without conflicting with NieR's file handles."""
    if not filepath or not os.path.exists(filepath):
        return None
    for attempt in range(retries):
        try:
            with open(filepath, 'rb') as f:
                return f.read()
        except (PermissionError, IOError):
            time.sleep(0.05)
    return None

QUEST_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quest_log.json")

def log_quest_discovery(q_id, label, slot_label):
    """Appends a finished quest to quest_log.json (used to map quest ids to their real names)."""
    try:
        entries = json.load(open(QUEST_LOG_FILE, encoding="utf-8")) if os.path.exists(QUEST_LOG_FILE) else []
    except Exception:
        entries = []
    entries.append({"quest": q_id, "mapped_as": label, "slot": slot_label,
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    with open(QUEST_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

PHASE_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase_log.json")

def phase_route(phase):
    """Route tag of a story phase name ("51_AB_MainDesert" -> "AB", "90_CD_2_Pascal..." -> "CD")."""
    for part in phase.split("_"):
        if not part.isdigit():
            return part if part in ("A", "B", "AB", "C", "CD", "D", "E") else "?"
    return "?"

def log_phase_change(phase, phase_id=None):
    """Appends a story phase change to phase_log.json (used to map phases to story milestones)."""
    try:
        entries = json.load(open(PHASE_LOG_FILE, encoding="utf-8")) if os.path.exists(PHASE_LOG_FILE) else []
    except Exception:
        entries = []
    entries.append({"phase": phase, "phase_id": phase_id, "route": phase_route(phase),
                    "time": time.strftime("%Y-%m-%d %H:%M:%S")})
    with open(PHASE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

# Story sub-phases reached per seed/slot: the hook shows only the matching chapters in the Chapter Select
CHAPTER_PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chapter_progress.json")

def reached_phase_key(phase, phase_id):
    """"<phase id>:<name>": the same sub-phase name exists in several phases (e.g. both Pascal village visits)."""
    return f"{phase_id}:{phase}" if phase_id is not None else phase

def _load_chapter_file():
    try:
        return json.load(open(CHAPTER_PROGRESS_FILE, encoding="utf-8")) if os.path.exists(CHAPTER_PROGRESS_FILE) else {}
    except Exception:
        return {}

def load_reached_phases(key):
    """Phases reached in this seed/slot ("seed|slot" key; None = the last one played)."""
    if not os.path.exists(CHAPTER_PROGRESS_FILE):
        # First run with chapter tracking: start from the phases logged before it (they have no phase id)
        try:
            return {e["phase"] for e in json.load(open(PHASE_LOG_FILE, encoding="utf-8"))
                    if e.get("phase") and e.get("phase_id") is None and e["phase"] != "START"}
        except Exception:
            return set()
    data = _load_chapter_file()
    return set(data.get(key if key is not None else data.get("_last", ""), []))

def save_reached_phases(key, phases):
    data = _load_chapter_file()
    data[key] = sorted(phases)
    data["_last"] = key
    with open(CHAPTER_PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class SaveDataWatcher:
    """Monitors local SlotData_*.dat saves for Endings, Terminals, Quests, and Boss milestones."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.save_dir = os.path.expanduser('~/Documents/My Games/NieR_Automata')
        self.last_mtimes = {}
        self.baseline_checks = set()
        self.found_checks = set()
        self.running = True
        self.target_slot = None  # None = Auto (track latest modified), 0 = SlotData_0, 1 = SlotData_1, 2 = SlotData_2
        self.current_active_file = None
        self.last_playtimes = {}
        self._parse_lock = threading.Lock()
        self.baseline_established = False
        self.live_snapshots = 0
        self.live_last_blob_hash = None
        self.live_text_confirmed = False
        self.live_text_warned = False
        self._slot_name_cache = {}
        self.quest_baseline = None      # quest ids already finished when the bridge started
        self.discovered_quests = set()  # quest ids finished (and logged) during this session
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()

    def _watch_loop(self):
        time.sleep(1.0)
        self.scan_saves()
        while self.running:
            try:
                self.scan_saves()
            except Exception as e:
                pass
            time.sleep(2.5)

    def get_slot_player_name(self, data):
        if len(data) >= 0x48:
            raw = data[0x34:0x50]
            name = raw.decode('utf-16le', errors='ignore').split('\x00')[0]
            return name.strip() or 'Unknown'
        return 'Unknown'

    def get_slot_endings(self, data):
        if len(data) >= 0x34:
            mask = struct.unpack('<I', data[0x30:0x34])[0]
            letters = []
            for bit_idx, (loc_id, name) in ENDING_BIT_MAP.items():
                if mask & (1 << bit_idx):
                    letter = name.split()[1].replace(':', '')
                    letters.append(letter)
            return sorted(letters)
        return []

    def get_slots_summary(self):
        summary = []
        if not os.path.exists(self.save_dir):
            return summary

        active_file = self.get_active_filepath()
        for idx in range(3):
            fname = f"SlotData_{idx}.dat"
            fpath = os.path.join(self.save_dir, fname)
            exists = os.path.exists(fpath)
            player = "Empty"
            mtime_str = "N/A"
            endings = []
            if exists:
                try:
                    mtime = os.path.getmtime(fpath)
                    import datetime
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    with open(fpath, 'rb') as fp:
                        data = fp.read()
                    player = self.get_slot_player_name(data)
                    endings = self.get_slot_endings(data)
                except Exception:
                    pass

            is_active = (fpath == active_file)
            summary.append({
                'slot_ui': idx + 1,
                'file_idx': idx,
                'filename': fname,
                'filepath': fpath,
                'exists': exists,
                'player': player,
                'mtime': mtime_str,
                'endings': endings,
                'is_active': is_active
            })
        return summary

    def find_slot_by_player_name(self, player_name):
        if not player_name or not os.path.exists(self.save_dir):
            return None
        target_norm = player_name.strip().lower()
        for idx in range(3):
            fpath = os.path.join(self.save_dir, f"SlotData_{idx}.dat")
            if os.path.exists(fpath):
                try:
                    mtime = os.path.getmtime(fpath)
                    cached_mtime, cached_name = self._slot_name_cache.get(idx, (0, ""))
                    if cached_mtime == mtime and cached_name:
                        pname = cached_name
                    else:
                        data = read_file_shared(fpath)
                        pname = self.get_slot_player_name(data).strip().lower() if data else ""
                        self._slot_name_cache[idx] = (mtime, pname)
                    if pname == target_norm:
                        return idx
                except Exception:
                    pass
        return None

    def get_active_filepath(self):
        if not os.path.exists(self.save_dir):
            return None

        if self.target_slot is not None:
            target_path = os.path.join(self.save_dir, f"SlotData_{self.target_slot}.dat")
            return target_path if os.path.exists(target_path) else None

        slot_files = [os.path.join(self.save_dir, f) for f in os.listdir(self.save_dir) if f.startswith('SlotData_') and f.endswith('.dat')]
        if not slot_files:
            return None
        return max(slot_files, key=lambda p: os.path.getmtime(p))

    def set_slot(self, target):
        """Locks to specific slot (1, 2, 3 or 'auto')."""
        if isinstance(target, str) and target.lower() in ['auto', 'all', 'none']:
            self.target_slot = None
            self.last_mtimes.clear()
            print("[SAVE WATCHER] Monitoring mode set to: AUTO (Dynamic tracking of whichever save you play/save).")
            self.scan_saves(force_report=True)
            return

        try:
            val = int(target)
            new_slot = None
            if val in [1, 2, 3]:
                # User gave UI slot (1-indexed)
                new_slot = val - 1
            elif val in [0, 1, 2]:
                new_slot = val
            else:
                print("[-] Invalid slot number. Choose 1, 2, 3, or 'auto'.")
                return

            if self.target_slot == new_slot:
                return

            self.target_slot = new_slot
            self.last_mtimes.clear()
            fpath = os.path.join(self.save_dir, f"SlotData_{self.target_slot}.dat")
            if not os.path.exists(fpath):
                print(f"[!] Warning: Slot {self.target_slot + 1} ({os.path.basename(fpath)}) does not exist yet.")
            else:
                try:
                    with open(fpath, 'rb') as fp:
                        pname = self.get_slot_player_name(fp.read())
                except Exception:
                    pname = "Unknown"
                print(f"🔒 [SAVE WATCHER] LOCKED strictly to: Slot {self.target_slot + 1} ({os.path.basename(fpath)}) - Player '{pname}'.")
            self.scan_saves(force_report=True)
        except ValueError:
            print("[-] Invalid slot format. Use 'slot 1', 'slot 2', 'slot 3', or 'slot auto'.")

    def print_slots(self):
        summary = self.get_slots_summary()
        mode_str = f"LOCKED to Slot {self.target_slot + 1}" if self.target_slot is not None else "AUTO (Tracks most recently saved)"
        print("\n=========================================================")
        print(" 💾 [NIER: AUTOMATA SAVE SLOTS STATUS]")
        print(f"    Current Mode: {mode_str}")
        print("---------------------------------------------------------")
        for s in summary:
            active_marker = " <<< [ACTIVELY MONITORED]" if s['is_active'] else ""
            end_str = ", ".join(s['endings']) if s['endings'] else "None"
            print(f"  • Slot {s['slot_ui']} ({s['filename']}):")
            print(f"      Player   : '{s['player']}'{active_marker}")
            print(f"      Modified : {s['mtime']}")
            print(f"      Endings  : {end_str}")
        print("---------------------------------------------------------")
        print("  Commands:")
        print("    'slot 2'    -> Lock strictly to Slot 2 (e.g. Nao)")
        print("    'slot 1'    -> Lock strictly to Slot 1")
        print("    'slot auto' -> Auto-detect active slot dynamically")
        print("=========================================================\n")

    def scan_saves(self, force_report=False):
        # When connected to the live game hook, RAM snapshots are the single source of truth.
        # Disk files are only updated on manual save at access points, so reading them while
        # connected causes desyncs with stale data from earlier runs or other slots.
        if self.bridge.connected and not force_report:
            return

        active_sfile = self.get_active_filepath()
        if not active_sfile or not os.path.exists(active_sfile):
            return

        if active_sfile != self.current_active_file or force_report:
            self.current_active_file = active_sfile
            self.baseline_established = False
            self.baseline_checks.clear()
            self.quest_baseline = None
            raw_data = read_file_shared(active_sfile)
            pname = self.get_slot_player_name(raw_data) if raw_data else "Unknown"
            sname = os.path.basename(active_sfile)
            slot_idx = int(sname.replace("SlotData_", "").replace(".dat", ""))
            mode = "MANUAL LOCK" if self.target_slot is not None else "AUTO"
            print(f"\n📡 [SAVE WATCHER ({mode})] Active Playing Slot: Slot {slot_idx + 1} ({sname}) | Player: '{pname}'")

        mtime = os.path.getmtime(active_sfile)
        if self.last_mtimes.get(active_sfile) != mtime:
            self.last_mtimes[active_sfile] = mtime
            self._parse_slot(active_sfile)

    def _parse_slot(self, filepath):
        data = read_file_shared(filepath)
        if not data or len(data) < 0x80:
            return

        slot_name = os.path.basename(filepath)
        slot_idx = int(slot_name.replace("SlotData_", "").replace(".dat", ""))
        player_name = self.get_slot_player_name(data)
        slot_label = f"Slot {slot_idx + 1}: {slot_name} ('{player_name}')"
        self._parse_data(data, slot_label)


    def parse_live_snapshot(self, msg):
        """Handles a 'save_snapshot' event: a live copy of the in-RAM save streamed by the DLL.
        Lets save-backed checks (quests, terminals, bosses, endings, storage) be validated
        without the player having to save."""
        import base64
        import hashlib
        try:
            head = base64.b64decode(msg.get("head", ""))
            blob = base64.b64decode(msg.get("blob", ""))
            cap = int(msg.get("cap", 0))
        except Exception as e:
            print(f"[-] [LIVE SAVE] Invalid snapshot: {e}")
            return

        data = bytearray(STORAGE_UPGRADES_OFFSET + 4)
        data[0:min(len(head), 0x7c)] = head[:0x7c]
        blob = blob[:0x30000 - 0x7c]
        data[0x7c:0x7c + len(blob)] = blob
        struct.pack_into('<I', data, STORAGE_UPGRADES_OFFSET, cap & 0xFFFFFFFF)

        # --- Diagnostics: is the quest/flag text really maintained live in RAM? ---
        has_text = (b"\nFlags\n" in blob) or (b"\nQuest\n" in blob)
        blob_hash = hashlib.md5(blob).hexdigest()
        self.live_snapshots += 1
        if self.live_snapshots == 1:
            if has_text:
                print("\n[LIVE SAVE] Save text (quests/terminals/bosses) is present in RAM. Watching for live updates...")
            elif not self.live_text_warned:
                self.live_text_warned = True
                print("\n[LIVE SAVE] WARNING: the RAM save buffer has no quest/flag text yet. "
                      "If this never changes, quest/terminal/boss checks can only be validated when the game saves.")
        elif has_text and blob_hash != self.live_last_blob_hash and not self.live_text_confirmed:
            active = self.get_active_filepath()
            try:
                file_age = time.time() - os.path.getmtime(active) if active else 9999
            except Exception:
                file_age = 9999
        active_slot = msg.get("active_slot", -1)
        player_name = msg.get("player_name", "").strip()
        if not player_name and len(head) >= 0x50:
            player_name = self.get_slot_player_name(head)

        # Automatically synchronize monitoring with the running game's active slot!
        if active_slot in [0, 1, 2] and self.target_slot != active_slot:
            self.set_slot(active_slot + 1)
        elif player_name and player_name != "Unknown":
            matched = self.find_slot_by_player_name(player_name)
            if matched is not None and self.target_slot != matched:
                self.set_slot(matched + 1)

        slot_label = f"LIVE GAME: Slot {self.target_slot + 1} ('{player_name}')" if self.target_slot is not None else f"LIVE GAME ('{player_name}')"
        self._parse_data(bytes(data), slot_label)

    def _parse_data(self, data, slot_label):
        with self._parse_lock:
            self._parse_data_locked(data, slot_label)

    def _parse_data_locked(self, data, slot_label):
        # Check if a fresh game was just started on this slot (playtime at offset 0x24 in NieR save data)
        playtime = struct.unpack('<I', data[0x24:0x28])[0] if len(data) >= 0x28 else None
        if playtime is not None:
            prev_playtime = self.last_playtimes.get(slot_label, None)
            self.last_playtimes[slot_label] = playtime
            if (prev_playtime is not None and playtime < prev_playtime and playtime < 30) or (prev_playtime is None and playtime < 10):
                print(f"\n🔄 [SAVE WATCHER] Detected New Game started on {slot_label} (Playtime: {playtime}s)! Automatically re-delivering all Archipelago items...")
                self.baseline_established = False
                self.baseline_checks.clear()
                self.quest_baseline = None
                self.found_checks.clear()
                self.bridge.reset_run(from_watcher=True)

        # 1. Endings (offset 0x30, 4-byte bitmask)
        mask = struct.unpack('<I', data[0x30:0x34])[0]

        # 2. Transporters, Quests & Bosses in ASCII section
        ascii_blob = data[0x7c:min(len(data), 0x30000)].split(b'\x00')[0].decode('latin1', errors='ignore')

        # Terminals (STRICT: Unlocked terminals ONLY exist in the \nFlags\n block! mask_ft_ in SceneState are locked!)
        flags_match = re.search(r'\nFlags\n(.*?)(?:\n[A-Za-z0-9_]+/\w+|\nSceneState|\n[A-Z][a-z]+|\Z)', ascii_blob, re.DOTALL)
        unlocked_flags = set(flags_match.group(1).split()) if flags_match else set()

        if not self.baseline_established:
            # Baseline: all milestones already present in the save when loaded are pre-existing progress.
            # They must NOT be re-sent as new checks achieved right now during this session!
            for bit_idx, (loc_id, _) in ENDING_BIT_MAP.items():
                if mask & (1 << bit_idx):
                    self.baseline_checks.add(loc_id)
            for flag, (loc_id, _) in TERMINAL_MAP.items():
                if flag in unlocked_flags:
                    self.baseline_checks.add(loc_id)
            done_quests = completed_quests(ascii_blob)
            for q_token, (loc_id, _) in QUEST_MAP.items():
                if q_token in done_quests:
                    self.baseline_checks.add(loc_id)
            for b_token, (loc_id, _) in BOSS_MAP.items():
                if b_token in ascii_blob:
                    self.baseline_checks.add(loc_id)
            if (AP_BASE_ID + 6) in self.baseline_checks:
                self.baseline_checks.add(AP_BASE_ID + 5)
            if STORAGE_CAP_VERIFIED and len(data) >= STORAGE_UPGRADES_OFFSET + 4:
                chip_cap = struct.unpack('<I', data[STORAGE_UPGRADES_OFFSET:STORAGE_UPGRADES_OFFSET + 4])[0]
                if chip_cap > len(STORAGE_CAPACITY_CHECKS):  # wiped/garbage value, never trust it
                    chip_cap = 0
                for min_cap, loc_id, _ in STORAGE_CAPACITY_CHECKS:
                    if chip_cap >= min_cap:
                        self.baseline_checks.add(loc_id)
            self.baseline_established = True
            print(f"[*] [SAVE WATCHER] Established baseline state for {slot_label}: {len(self.baseline_checks)} existing milestones locked.")

        # 1. Endings
        for bit_idx, (loc_id, default_name) in ENDING_BIT_MAP.items():
            if mask & (1 << bit_idx):
                cname = AP_LOCATIONS.get(str(loc_id), default_name)
                letter = default_name.split()[1].replace(':', '')
                if loc_id not in self.baseline_checks and loc_id not in self.found_checks:
                    self.found_checks.add(loc_id)
                    print(f"\n=========================================================")
                    print(f" 🏆 [SAVE DATA: ENDING ACHIEVED ({slot_label})]")
                    print(f"    Ending {letter}: {cname}")
                    print(f"    Archipelago Location ID: {loc_id}")
                    self.bridge.send_save_check(loc_id, cname, f"Ending {letter}")

        for flag, (loc_id, loc_name) in TERMINAL_MAP.items():
            if flag in unlocked_flags:
                cname = AP_LOCATIONS.get(str(loc_id), loc_name)
                if loc_id not in self.baseline_checks and loc_id not in self.found_checks:
                    self.found_checks.add(loc_id)
                    print(f"\n=========================================================")
                    print(f" 📡 [SAVE DATA: TERMINAL UNLOCKED ({slot_label})]")
                    print(f"    {cname}")
                    print(f"    Archipelago Location ID: {loc_id}")
                    self.bridge.send_save_check(loc_id, cname, "Terminal Unlocked")

        # Quests
        done_quests = completed_quests(ascii_blob)
        for q_token, (loc_id, loc_name) in QUEST_MAP.items():
            if q_token in done_quests:
                cname = AP_LOCATIONS.get(str(loc_id), loc_name)
                if loc_id not in self.baseline_checks and loc_id not in self.found_checks:
                    self.found_checks.add(loc_id)
                    print(f"\n=========================================================")
                    print(f" 📜 [SAVE DATA: QUEST COMPLETED ({slot_label})]")
                    print(f"    {cname}")
                    print(f"    Archipelago Location ID: {loc_id}")
                    self.bridge.send_save_check(loc_id, cname, "Quest Complete")

        # Quest discovery: every quest finished during this session ("qNNN/DONE" or "qNNN/FIN" in
        # SceneState) is logged with its id, so ids can be matched with real quest names (main quests
        # included) and turned into verified locations later. Quest ids are hex (q120, qa1c, qb10, qf01).
        if self.quest_baseline is None:
            self.quest_baseline = done_quests
        for q_id in sorted(done_quests - self.quest_baseline - self.discovered_quests):
            self.discovered_quests.add(q_id)
            label = QUEST_MAP[q_id][1][len("Quest: "):] if q_id in QUEST_MAP else "non repertoriee"
            print(f"\n📜 [QUEST LOG] {q_id} terminee ({label}) - {slot_label}")
            log_quest_discovery(q_id, label, slot_label)
            self.bridge.send_command({"cmd": "notify", "title": "QUETE TERMINEE",
                                      "text": f"{q_id} - {label}"})

        # Bosses
        for b_token, (loc_id, loc_name) in BOSS_MAP.items():
            if b_token in ascii_blob:
                cname = AP_LOCATIONS.get(str(loc_id), loc_name)
                if loc_id not in self.baseline_checks and loc_id not in self.found_checks:
                    self.found_checks.add(loc_id)
                    print(f"\n=========================================================")
                    print(f" ⚔️ [SAVE DATA: BOSS DEFEATED ({slot_label})]")
                    print(f"    {cname}")
                    print(f"    Archipelago Location ID: {loc_id}")
                    self.bridge.send_save_check(loc_id, cname, "Boss Victory")

        # 5. Chip Storage Capacity Upgrades (upgrade count at STORAGE_UPGRADES_OFFSET in SlotData)
        if STORAGE_CAP_VERIFIED and len(data) >= STORAGE_UPGRADES_OFFSET + 4:
            chip_cap = struct.unpack('<I', data[STORAGE_UPGRADES_OFFSET:STORAGE_UPGRADES_OFFSET + 4])[0]
            if chip_cap > len(STORAGE_CAPACITY_CHECKS):  # wiped/garbage value, never trust it
                chip_cap = 0
            for min_cap, loc_id, default_name in STORAGE_CAPACITY_CHECKS:
                if chip_cap >= min_cap:
                    cname = AP_LOCATIONS.get(str(loc_id), default_name)
                    if loc_id not in self.baseline_checks and loc_id not in self.found_checks:
                        self.found_checks.add(loc_id)
                        print(f"\n=========================================================")
                        print(f" 💾 [SAVE DATA: STORAGE UPGRADE ({slot_label})]")
                        print(f"    Capacity: {chip_cap} (Req: >= {min_cap}) -> {cname}")
                        print(f"    Archipelago Location ID: {loc_id}")
                        print(f"=========================================================\n")
                        self.bridge.send_save_check(loc_id, cname, f"Capacity Upgrade {chip_cap}")

    def sync_all_to_ap(self):
        self.sync_all_save_milestones()

    def sync_all_save_milestones(self):
        """Scans the active save file (and live RAM snapshot) and validates all
        unlocked endings, terminals, quests, bosses, and storage upgrades directly on Archipelago!"""
        active_sfile = self.get_active_filepath()
        if not active_sfile or not os.path.exists(active_sfile):
            print("[-] [SAVE SYNC] No active save file found to scan.")
            return

        try:
            with open(active_sfile, 'rb') as fp:
                data = fp.read()
        except Exception as e:
            print(f"[-] [SAVE SYNC] Failed to read save file: {e}")
            return

        if len(data) < 0x80:
            return

        slot_name = os.path.basename(active_sfile)
        player_name = self.get_slot_player_name(data)
        print(f"\n🔄 [SAVE SYNC] Scanning {slot_name} ('{player_name}') for unlocked checks to send to Archipelago...")

        mask = struct.unpack('<I', data[0x30:0x34])[0]
        ascii_blob = data[0x7c:min(len(data), 0x30000)].split(b'\x00')[0].decode('latin1', errors='ignore')
        flags_match = re.search(r'\nFlags\n(.*?)(?:\n[A-Za-z0-9_]+/\w+|\nSceneState|\n[A-Z][a-z]+|\Z)', ascii_blob, re.DOTALL)
        unlocked_flags = set(flags_match.group(1).split()) if flags_match else set()

        synced = 0

        # 1. Endings (mask)
        for bit_idx, (loc_id, default_name) in ENDING_BIT_MAP.items():
            if mask & (1 << bit_idx):
                if not self.bridge.ap_client.connected or loc_id in self.bridge.ap_client.missing_locations:
                    cname = AP_LOCATIONS.get(str(loc_id), default_name)
                    letter = default_name.split()[1].replace(':', '')
                    print(f"  🏆 [SYNC] Found unlocked Ending {letter} in save: {cname} (Location #{loc_id})!")
                    self.bridge.send_save_check(loc_id, cname, f"Ending {letter}")
                    synced += 1


        # 2. Terminals
        for flag, (loc_id, default_name) in TERMINAL_MAP.items():
            if flag in unlocked_flags:
                if not self.bridge.ap_client.connected or loc_id in self.bridge.ap_client.missing_locations:
                    cname = AP_LOCATIONS.get(str(loc_id), default_name)
                    print(f"  📡 [SYNC] Found unlocked Terminal in save: {cname} (Location #{loc_id})!")
                    self.bridge.send_save_check(loc_id, cname, "Terminal")
                    synced += 1

        # 3. Quests
        done_quests = completed_quests(ascii_blob)
        for q_token, (loc_id, default_name) in QUEST_MAP.items():
            if q_token in done_quests:
                if not self.bridge.ap_client.connected or loc_id in self.bridge.ap_client.missing_locations:
                    cname = AP_LOCATIONS.get(str(loc_id), default_name)
                    print(f"  📜 [SYNC] Found completed Quest in save: {cname} (Location #{loc_id})!")
                    self.bridge.send_save_check(loc_id, cname, "Quest")
                    synced += 1

        # 4. Bosses
        for b_token, (loc_id, default_name) in BOSS_MAP.items():
            if b_token in ascii_blob:
                if not self.bridge.ap_client.connected or loc_id in self.bridge.ap_client.missing_locations:
                    cname = AP_LOCATIONS.get(str(loc_id), default_name)
                    print(f"  ⚔️ [SYNC] Found defeated Boss in save: {cname} (Location #{loc_id})!")
                    self.bridge.send_save_check(loc_id, cname, "Boss")
                    synced += 1

        # 5. Chip Storage Capacity Upgrades
        if STORAGE_CAP_VERIFIED and len(data) >= STORAGE_UPGRADES_OFFSET + 4:
            chip_cap = struct.unpack('<I', data[STORAGE_UPGRADES_OFFSET:STORAGE_UPGRADES_OFFSET + 4])[0]
            if chip_cap > len(STORAGE_CAPACITY_CHECKS):  # wiped/garbage value, never trust it
                chip_cap = 0
            for min_cap, loc_id, default_name in STORAGE_CAPACITY_CHECKS:
                if chip_cap >= min_cap:
                    if not self.bridge.ap_client.connected or loc_id in self.bridge.ap_client.missing_locations:
                        cname = AP_LOCATIONS.get(str(loc_id), default_name)
                        print(f"  💾 [SYNC] Found Storage Upgrade in save: {cname} (Cap {chip_cap} >= {min_cap}) (Location #{loc_id})!")
                        self.bridge.send_save_check(loc_id, cname, f"Capacity Upgrade {chip_cap}")
                        synced += 1

        # 6. Fish in the inventory (catches made while the bridge was offline). Fish species received as
        # Archipelago items are skipped: owning them says nothing about having fished them.
        if len(data) >= SAVE_INVENTORY_OFFSET + 256 * 12:
            entries = [struct.unpack_from('<iIi', data, SAVE_INVENTORY_OFFSET + i * 12) for i in range(256)]
            received_fish = {entry[0] for entry in self.bridge.ap_client.received_items_history
                             if entry and entry[0] in FISH_ITEM_IDS}
            owned = {item_id for item_id, _, qty in entries if qty > 0} - received_fish
            for fish_id in FISH_ITEM_IDS:
                loc_id = AP_BASE_ID + fish_id
                if fish_id in owned and self.bridge.ap_client.connected and loc_id in self.bridge.ap_client.missing_locations:
                    cname = AP_LOCATIONS.get(str(loc_id), f"Fishing: #{fish_id}")
                    print(f"  🎣 [SYNC] Found fish in save inventory: {cname} (Location #{loc_id})!")
                    self.bridge.send_save_check(loc_id, cname, "Fishing")
                    synced += 1

        # 7. Story milestone of the phase stored in the save
        if len(data) >= 0x395F4 + 64:
            save_phase = data[0x395F4:0x395F4 + 64].split(b'\x00')[0].decode('latin1', errors='ignore')
            if save_phase:
                self.bridge.check_story_phase(save_phase)

        # 8. Level milestones from the save EXP
        if len(data) >= SAVE_XP_OFFSET + 4:
            save_level = level_from_xp(struct.unpack_from('<i', data, SAVE_XP_OFFSET)[0])
            if save_level > self.bridge.last_level:
                self.bridge.check_level_milestones(save_level)

        if synced > 0:
            print(f"🎉 [SAVE SYNC COMPLETE] Synced {synced} save milestone check(s) to Archipelago Server!\n> ", end="", flush=True)
        else:
            print(f"[*] [Save Sync] All save milestones are already up-to-date on Archipelago.\n> ", end="", flush=True)


# -------------------------------------------------------------
# Archipelago WebSocket Client
# -------------------------------------------------------------
class ArchipelagoClient:
    def __init__(self, bridge):
        self.bridge = bridge
        self.ws = None
        self.loop = None
        self.thread = None
        self.connected = False
        self.server_url = ""
        self.slot_name = ""
        self.password = ""
        self.slot_id = None
        self.players = {}
        self.checked_locations = set()
        self.missing_locations = set()
        self.received_items_history = []
        self.last_item_index = 0
        self.seed_name = ""
        self.committed_index = 0        # items below this index were delivered AND confirmed in a previous run
        self.pending_commit_index = 0   # highest index handed to the game (waiting for its confirmation)
        self.initial_items_received = False  # False until the first ReceivedItems packet of a connection
        self.client_uuid = str(uuid.uuid4())
        self.slot_games = {}     # slot -> game name (for item names of other worlds)
        self.item_names = {}     # game -> {item id: item name} (DataPackage)
        self.scouted = {}        # location id -> (item id, receiving slot, flags) (LocationScouts)
        self.goal_location = None  # location whose check completes the goal (from slot_data "goal")
        self.goal_sent = False
        self.death_link = False    # slot_data "death_link"

    def send_death(self):
        """DeathLink: tells every DeathLink player that we died."""
        if not (self.connected and self.death_link):
            return
        payload = [{"cmd": "Bounce", "tags": ["DeathLink"],
                    "data": {"time": time.time(), "source": self.slot_name,
                             "cause": f"{self.slot_name} s'est fait detruire dans NieR: Automata"}}]
        asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(payload)), self.loop)
        print(f"\n💀 [DEATHLINK] Mort envoyee aux autres joueurs.\n> ", end="", flush=True)

    def _sync_if_no_items(self):
        if self.connected and not self.initial_items_received:
            self.bridge.send_command({"cmd": "items_synced"})
            self.bridge.push_chapter_progress()

    def _check_goal(self):
        """Tells the server the goal is complete (ClientStatus GOAL = 30) once its location is checked."""
        if self.goal_sent or self.goal_location is None or self.goal_location not in self.checked_locations:
            return
        self.goal_sent = True
        asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps([{"cmd": "StatusUpdate", "status": 30}])), self.loop)
        goal_name = AP_LOCATIONS.get(str(self.goal_location), f"#{self.goal_location}")
        print(f"\n🏁 [GOAL] Objectif atteint ({goal_name}) -> victoire envoyee au serveur !\n> ", end="", flush=True)
        self.bridge.send_command({"cmd": "notify", "title": "OBJECTIF ATTEINT", "text": goal_name})

    async def _request_shop_scouts(self):
        """Asks the server what the shop locations contain, plus the item names of every game."""
        games = sorted({g for g in self.slot_games.values() if g})
        locs = [cid for cid, _ in SHOP_HINT_LOCATIONS if cid in self.missing_locations or cid in self.checked_locations]
        payload = [{"cmd": "GetDataPackage", "games": games}]
        if locs:
            payload.append({"cmd": "LocationScouts", "locations": locs, "create_as_hint": 0})
        await self.ws.send(json.dumps(payload))

    def connect(self, server, slot_name, password=""):
        if not websockets:
            print("[-] Python 'websockets' library is required. Run 'pip install websockets'.")
            return False

        if not server.startswith("ws://") and not server.startswith("wss://"):
            if "localhost" in server or "127.0.0.1" in server:
                server = "ws://" + server
            else:
                server = "wss://" + server

        self.server_url = server
        self.slot_name = slot_name
        self.password = password

        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        return True

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._ws_handler())

    async def _ws_handler(self):
        urls = [self.server_url]
        if self.server_url.startswith("wss://"):
            urls.append("ws://" + self.server_url[6:])
        elif self.server_url.startswith("ws://"):
            urls.append("wss://" + self.server_url[5:])

        connected_any = False
        for target_url in urls:
            print(f"\n[*] [Archipelago] Trying connection to {target_url}...")
            try:
                ssl_ctx = SSL_CONTEXT if target_url.startswith("wss://") else None
                async with websockets.connect(target_url, ssl=ssl_ctx, ping_interval=20, ping_timeout=20) as ws:
                    self.ws = ws
                    self.connected = True
                    connected_any = True
                    print(f"[+] [Archipelago] Connected to {target_url}! Awaiting RoomInfo...\n")

                    async for message in ws:
                        try:
                            packets = json.loads(message)
                            for packet in packets:
                                await self._handle_packet(packet)
                        except Exception as e:
                            print(f"[-] [Archipelago] Packet error: {e}")
                    break
            except Exception as e:
                print(f"[-] [Archipelago] Connection to {target_url} failed: {e}")

        if not connected_any:
            print(f"\n[-] [Archipelago] Failed to connect to any WebSocket protocol for {self.server_url}")
            self.bridge.send_command({
                "event": "ap_status",
                "connected": False
            })
        self.connected = False
        self.ws = None

    async def _handle_packet(self, packet):
        cmd = packet.get("cmd")

        if cmd == "RoomInfo":
            self.seed_name = packet.get('seed_name', '') or ''
            print(f">>> [Archipelago Server] Connected to Seed: {packet.get('seed_name', 'Unknown')}")
            print(f">>> Authenticating slot '{self.slot_name}' for game 'NieR Automata'...")
            connect_packet = [{
                "cmd": "Connect",
                "password": self.password,
                "game": "NieR Automata",
                "name": self.slot_name,
                "version": {"major": 0, "minor": 5, "build": 0, "class": "Version"},
                "items_handling": 7,
                "tags": ["AP"],
                "uuid": self.client_uuid
            }]
            await self.ws.send(json.dumps(connect_packet))

        elif cmd == "Connected":
            self.slot_id = packet.get("slot")
            self.checked_locations = set(packet.get("checked_locations", []))
            self.missing_locations = set(packet.get("missing_locations", []))
            self.initial_items_received = False
            self.goal_location = GOAL_LOCATIONS.get(packet.get("slot_data", {}).get("goal"))
            self.goal_sent = False
            self.death_link = bool(packet.get("slot_data", {}).get("death_link"))
            if self.death_link:
                await self.ws.send(json.dumps([{"cmd": "ConnectUpdate", "tags": ["AP", "DeathLink"]}]))
                print("[*] [DEATHLINK] Actif pour ce slot.")

            # Restore which items were already delivered (and confirmed) in a previous run
            with _state_lock:
                entry = load_received_state().get(self._state_key(), {})
            self.committed_index = int(entry.get("committed_index", 0))
            self.pending_commit_index = self.committed_index
            print(f"[*] [Items] Already delivered in previous runs: {self.committed_index} item(s).")

            # Cache players
            for player_info in packet.get("players", []):
                self.players[player_info.get("slot")] = player_info.get("alias", player_info.get("name"))
            for slot, info in packet.get("slot_info", {}).items():
                self.slot_games[int(slot)] = info.get("game", "")

            print(f"\n=========================================================")
            print(f" 🎉 [ARCHIPELAGO MULTIWORLD ONLINE]")
            print(f"    Slot: {self.slot_name} (Slot #{self.slot_id})")
            print(f"    Total Checks in Pool: {len(self.missing_locations) + len(self.checked_locations)}")
            print(f"    Already Checked: {len(self.checked_locations)}")
            print(f"    Remaining Checks: {len(self.missing_locations)}")
            print(f"    Connected Players: {', '.join(self.players.values()) if self.players else 'None'}")
            if self.goal_location is not None:
                print(f"    Goal: {AP_LOCATIONS.get(str(self.goal_location), self.goal_location)}")
            print(f"=========================================================\n> ", end="", flush=True)
            self._check_goal()
            # No ReceivedItems comes when nothing was received yet: tell the hook it is synced anyway
            self.loop.call_later(3.0, self._sync_if_no_items)

            # Automatically activate interception in NieR!
            self.bridge.set_intercept(True)

            # Automatically synchronize any save milestones (endings, terminals, quests, bosses) that were unlocked!
            self.bridge.save_watcher.sync_all_save_milestones()

            # Notify in-game YoRHa UI of connection status!
            self.bridge.send_command({
                "event": "ap_status",
                "connected": True,
                "slot": self.slot_name,
                "checked": len(self.checked_locations),
                "total": len(self.missing_locations) + len(self.checked_locations)
            })

            # Shop overlay: what each shop purchase contains
            await self._request_shop_scouts()

        elif cmd == "DataPackage":
            for game, gdata in packet.get("data", {}).get("games", {}).items():
                self.item_names[game] = {v: k for k, v in gdata.get("item_name_to_id", {}).items()}
            self.bridge.push_shop_hints()

        elif cmd == "LocationInfo":
            for net_item in packet.get("locations", []):
                self.scouted[net_item.get("location")] = (net_item.get("item"), net_item.get("player"), net_item.get("flags", 0))
            self.bridge.push_shop_hints()

        elif cmd == "ConnectionRefused":
            errors = packet.get("errors", ["Refuse par le serveur"])
            print(f"\n[-] [Archipelago] Connexion refusee: {errors}\n> ", end="", flush=True)
            self.bridge.send_command({
                "event": "ap_status",
                "connected": False
            })

        elif cmd == "ReceivedItems":
            index = packet.get("index", 0)
            items = packet.get("items", [])
            if index == 0:
                self.received_items_history.clear()
                self.last_item_index = 0
                # A saved index beyond the number of items the server really holds is stale
                # (new room / regenerated seed): it would make fresh items look 'already delivered'.
                if self.committed_index > len(items):
                    print(f"[!] [Items] Stale delivery state ({self.committed_index} > {len(items)} items on server) -> reset.")
                    self.committed_index = 0
                    self.pending_commit_index = 0

            # Everything after the very first packet of a connection is a LIVE item (just obtained)
            live = self.initial_items_received
            self.initial_items_received = True

            # Keep the history aligned with AP indexes (None = hole, skipped on delivery)
            del self.received_items_history[index:]
            while len(self.received_items_history) < index:
                self.received_items_history.append(None)

            for item_data in items:
                raw_item_id = item_data.get("item")
                sender_slot = item_data.get("player")
                sender_name = self.players.get(sender_slot, f"Player #{sender_slot}")

                # Unwrap AP ID to NieR in-game ID
                nier_id = raw_item_id - AP_BASE_ID if raw_item_id >= AP_BASE_ID else raw_item_id

                # Resolve clean human-readable name
                clean_item_name = AP_ITEMS.get(str(raw_item_id)) or AP_ITEMS.get(raw_item_id)
                if not clean_item_name:
                    if is_weapon_id(nier_id):
                        clean_item_name = WEAPON_NAMES.get(nier_id, f"Weapon #{nier_id}")
                    else:
                        clean_item_name = f"Item #{nier_id}"

                self.received_items_history.append((nier_id, sender_name, clean_item_name))

            self._deliver(index, index + len(items), live=live)
            if not live:
                # The hook may now treat weapons it does not know as obtained outside Archipelago
                self.bridge.send_command({"cmd": "items_synced"})
                self.bridge.push_chapter_progress()

        elif cmd == "Bounced":
            data = packet.get("data", {})
            if self.death_link and "DeathLink" in packet.get("tags", []) and data.get("source") != self.slot_name:
                source = data.get("source", "?")
                cause = data.get("cause") or f"{source} est mort"
                print(f"\n💀 [DEATHLINK] {cause} -> 2B est detruite !\n> ", end="", flush=True)
                self.bridge.send_command({"cmd": "kill"})
                self.bridge.send_command({"cmd": "notify", "title": "DEATHLINK", "text": cause})

        elif cmd == "RoomUpdate":
            if "checked_locations" in packet:
                self.checked_locations.update(packet["checked_locations"])
                self.bridge.push_shop_hints()

        elif cmd == "PrintJSON":
            # Formatted server messages / hints
            parts = packet.get("data", [])
            text = "".join(part.get("text", "") for part in parts)
            if text.strip():
                print(f"\n💬 [AP MultiWorld]: {text.strip()}\n> ", end="", flush=True)

    def _state_key(self):
        return f"{self.seed_name}|{self.slot_name}"

    def cumulative_count(self, nier_id):
        """How many times this item was received from the server so far."""
        return sum(1 for h in self.received_items_history if h is not None and h[0] == nier_id)

    def gold_totals(self, live_from=None):
        """(total gold received, gold already delivered in a previous run)."""
        total = credited = 0
        for idx, h in enumerate(self.received_items_history):
            if h is None:
                continue
            amount = GOLD_BUNDLE_AMOUNTS.get(h[0])
            if not amount:
                continue
            total += amount
            is_new = (live_from is not None and idx >= live_from) or idx >= self.committed_index
            if not is_new:
                credited += amount
        return total, credited

    def _deliver(self, start, end, live=False):
        """Hands items [start, end) of the received history to the game.

        * Weapons / pod programs / chips are idempotent ("make sure the player owns it") -> always (re)sent.
        * Consumables, materials and gold are ADDITIVE. Items already delivered and confirmed in a
          previous run (idx < committed_index) are only announced as 'known_only' (the game learns the
          cumulative total but grants nothing). Items received live are ALWAYS new.
        """
        floor = self.last_item_index   # already handed over during this session
        ok = True
        grouped = {}                   # (nier_id, sender) -> [new_count, name, total_count_batch]
        gold_total, gold_credited = self.gold_totals(live_from=start if live else None)

        for idx in range(start, min(end, len(self.received_items_history))):
            entry = self.received_items_history[idx]
            if entry is None or idx < floor:
                continue
            nier_id, sender_name, clean_name = entry
            is_new = live or idx >= self.committed_index

            if is_weapon_id(nier_id):
                if is_new:
                    print(f"\n🎁 [MULTIWORLD ITEM RECEIVED] {clean_name} sent by {sender_name}!")
                ok = self.bridge.give_weapon(nier_id, 1, name=clean_name, sender=sender_name, notify=is_new) and ok
            elif is_idempotent_item(nier_id):
                if is_new:
                    print(f"\n🎁 [MULTIWORLD ITEM RECEIVED] {clean_name} (ID {nier_id}) sent by {sender_name}!")
                ok = self.bridge.give_item(nier_id, 1, name=clean_name, sender=sender_name, notify=is_new) and ok
            else:
                if is_new:
                    print(f"\n🎁 [MULTIWORLD ITEM RECEIVED] {clean_name} (ID {nier_id}) sent by {sender_name}!")
                g = grouped.setdefault((nier_id, sender_name), [0, clean_name, 0])
                g[2] += 1
                if is_new:
                    g[0] += 1

        for (nier_id, sender_name), (new_count, clean_name, batch_count) in grouped.items():
            total_count = self.cumulative_count(nier_id)
            is_gold = nier_id in GOLD_BUNDLE_AMOUNTS
            ok = self.bridge.give_item(
                nier_id,
                new_count if new_count > 0 else 1,
                name=clean_name,
                sender=sender_name,
                notify=new_count > 0,
                total_gold=gold_total if is_gold else 0,
                total_count=total_count,
                known_only=(new_count == 0),
                credited_gold=gold_credited if is_gold else 0,
            ) and ok

        self.last_item_index = max(self.last_item_index, end)
        self.pending_commit_index = max(self.pending_commit_index, end)
        if ok:
            # The game answers 'grants_idle' with this index once everything is really in the inventory
            self.bridge.send_command({"cmd": "commit_marker", "index": int(self.pending_commit_index)})

    def commit_delivered(self, marker_index):
        """Called when the game confirms that all items up to marker_index are in the inventory."""
        new_index = min(int(marker_index), self.pending_commit_index)
        if new_index <= self.committed_index or not self.slot_name:
            return
        self.committed_index = new_index
        with _state_lock:
            state = load_received_state()
            state[self._state_key()] = {"committed_index": new_index}
            save_received_state(state)
        print(f"\n✅ [Items] {new_index} item(s) confirmed in the game inventory (saved).\n> ", end="", flush=True)

    def send_location_check(self, location_id):
        if not self.connected or not self.ws:
            return False

        if location_id in self.checked_locations:
            print(f"[*] Location #{location_id} was already checked on Archipelago.")
            return True

        self.checked_locations.add(location_id)
        if location_id in self.missing_locations:
            self.missing_locations.remove(location_id)

        # Notify in-game YoRHa UI of real-time check count update
        self.bridge.send_command({
            "event": "ap_status",
            "connected": True,
            "slot": self.slot_name,
            "checked": len(self.checked_locations),
            "total": len(self.checked_locations) + len(self.missing_locations)
        })

        payload = [{
            "cmd": "LocationChecks",
            "locations": [int(location_id)]
        }]
        asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(payload)), self.loop)
        if location_id in SHOP_HINT_IDS:
            self.bridge.push_shop_hints()
        self._check_goal()
        return True

    def disconnect(self):
        if self.connected and self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
            self.connected = False


# -------------------------------------------------------------
# Local NieR: Automata DLL Bridge Client (TCP)
# -------------------------------------------------------------
class NieRArchipelagoBridge:
    def __init__(self, host=DEFAULT_LOCAL_HOST, port=DEFAULT_LOCAL_PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.connected = False
        self.ap_client = ArchipelagoClient(self)
        self.save_watcher = SaveDataWatcher(self)
        self.discovered_chests = {}
        self.recent_checks = {}
        self.sent_storage_checks = set()
        self.sent_level_checks = set()
        self.last_level = 0
        self.pending_story = {}  # location id -> name, story milestones reached but not sent yet
        self.pending_checks = set()  # location checks detected while Archipelago was offline
        self.reached_key = None  # "seed|slot" whose reached phases are loaded
        self.reached_phases = set()
        self.next_auto_id = 92000100

    def _load_chapter_progress(self):
        # Offline: the last seed played (the Chapter Select stays limited without the server)
        key = self.ap_client._state_key() if self.ap_client.connected else _load_chapter_file().get("_last")
        if self.reached_key != key or key is None:
            self.reached_key, self.reached_phases = key, load_reached_phases(key)

    def push_chapter_progress(self):
        """Sends the hook the story phases reached in this seed (Chapter Select shows only those chapters)."""
        self._load_chapter_progress()
        self.send_command({"cmd": "chapters", "phases": sorted(self.reached_phases)})
        if self.ap_client.connected:
            # Story milestones reached while offline (or before a bridge restart) are sent now
            for key in sorted(self.reached_phases):
                for loc_id, name in story_milestones_for(key.split(":", 1)[-1]):
                    if loc_id not in self.ap_client.checked_locations:
                        self.pending_story.setdefault(loc_id, name)
            self.flush_story_milestones()

    def remember_phase(self, phase, phase_id):
        if phase == "START":
            return
        self._load_chapter_progress()
        key = reached_phase_key(phase, phase_id)
        if key not in self.reached_phases:
            self.reached_phases.add(key)
            if self.reached_key is not None:
                save_reached_phases(self.reached_key, self.reached_phases)

    def check_story_phase(self, phase):
        """Queues the story milestones reached by this phase, then sends them if Archipelago is connected."""
        for loc_id, name in story_milestones_for(phase):
            if loc_id not in self.pending_story:
                print(f"\n📖 [STORY] {name} (phase {phase})")
                self.pending_story[loc_id] = name
        self.flush_story_milestones()

    def flush_story_milestones(self):
        if not self.ap_client.connected:
            return
        for loc_id, name in list(self.pending_story.items()):
            if loc_id not in self.ap_client.checked_locations:
                self.send_save_check(loc_id, AP_LOCATIONS.get(str(loc_id), name), "Story")
            del self.pending_story[loc_id]

    def check_level_milestones(self, level):
        """Sends every level milestone reached. A milestone only counts as sent once Archipelago is
        connected, so milestones reached offline are sent again by the reconciliation loop."""
        self.last_level = level
        for lv in LEVEL_MILESTONES:
            loc_id = LEVEL_LOCATION_BASE + lv
            if lv > level or loc_id in self.sent_level_checks:
                continue
            if self.ap_client.connected and loc_id in self.ap_client.checked_locations:
                self.sent_level_checks.add(loc_id)
                continue
            if not self.ap_client.connected:
                continue
            self.sent_level_checks.add(loc_id)
            print(f"\n⭐ [LEVEL] Niveau {level} atteint -> palier {lv}")
            self.send_save_check(loc_id, AP_LOCATIONS.get(str(loc_id), f"Level: Reach Lv {lv}"), f"Niveau {lv}")

    def send_save_check(self, loc_id, loc_name, tag="Save Check"):
        """Sends an achievement/milestone check detected in local save data to AP & UI."""
        # 1. Send in-game YoRHa UI overlay notification
        self.send_command({
            "cmd": "sent_check_notify",
            "location": loc_name,
            "id": int(loc_id),
            "item": tag
        })
        # 2. Send to Archipelago if connected
        if self.ap_client.connected:
            sent = self.ap_client.send_location_check(loc_id)
            if sent:
                print(f"    -> [ARCHIPELAGO]: Sent LocationCheck #{loc_id} to MultiWorld Server!\n> ", end="", flush=True)
        else:
            self.pending_checks.add(int(loc_id))
            print(f"    -> [LOCAL BRIDGE]: Check #{loc_id} queued, sent as soon as Archipelago is connected\n> ", end="", flush=True)

    def connect(self):
        """Attempts to connect to the NieR hook TCP server."""
        print(f"\n[*] Connecting to NieR: Automata at {self.host}:{self.port}...")
        while not self.connected:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                self.connected = True
                self.running = True
                print(f"[+] CONNECTED to NieR: Automata hook successfully!\n")

                # Start listener thread
                t = threading.Thread(target=self._listen_thread, daemon=True)
                t.start()
                self.push_shop_hints()

                # Start continuous item reconciliation worker (Luigi's Mansion style)
                t_reconcile = threading.Thread(target=self._reconciliation_loop, daemon=True)
                t_reconcile.start()
                return True
            except ConnectionRefusedError:
                print(f"[-] NieR hook not detected on port {self.port}. Retrying in 2 seconds (make sure the game is running)...")
                time.sleep(2)
            except Exception as e:
                print(f"[-] Connection error: {e}. Retrying in 2 seconds...")
                time.sleep(2)

    def _reconciliation_loop(self):
        """Monitors connection. Continuous item reconciliation is handled directly in RAM by the C++ engine hook."""
        while self.running:
            time.sleep(10.0)
            if self.last_level and self.ap_client.connected:
                self.check_level_milestones(self.last_level)
            if self.pending_story:
                self.flush_story_milestones()
            if self.pending_checks and self.ap_client.connected:
                for loc_id in sorted(self.pending_checks):
                    self.ap_client.send_location_check(loc_id)
                print(f"\n📤 [SYNC] {len(self.pending_checks)} check(s) detectes hors ligne envoyes a Archipelago.\n> ", end="", flush=True)
                self.pending_checks.clear()

    def _listen_thread(self):
        """Background thread reading events from NieRAutomata."""
        buffer = ""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    print("\n[-] Connection closed by NieR: Automata (Game exited).")
                    print("[*] Terminating Archipelago bridge cleanly...")
                    self.connected = False
                    self.running = False
                    import os
                    os._exit(0)
                buffer += data.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle_incoming_message(line)
            except Exception as e:
                if self.running:
                    print(f"[-] Receive error: {e}")
                    import os
                    os._exit(0)
                break

    def _resolve_chest_location(self, pos, default_item_id, type_str="CHEST"):
        # 1. Weapon check (chests, rewards, or shop weapons)
        if type_str == "WEAPON_CHEST" or is_weapon_id(default_item_id):
            if default_item_id in WEAPON_TO_LOCATION_MAP:
                cid, cname = WEAPON_TO_LOCATION_MAP[default_item_id]
                if str(cid) in AP_LOCATIONS:
                    cname = AP_LOCATIONS[str(cid)]
                return cid, cname

        # 2. Pod Programs & Special Modules (Shop purchases / key items)
        if default_item_id in POD_PROGRAM_MAP:
            cid, cname = POD_PROGRAM_MAP[default_item_id]
            if str(cid) in AP_LOCATIONS:
                cname = AP_LOCATIONS[str(cid)]
            return cid, cname

        # 3. 9S Hacking Chests (RVA 0x800573)
        if type_str == "HACKING_CHEST":
            return self._resolve_hacking_chest(pos)

        # 4. Boss Defeats (Goliath Buzzsaw, Engels, etc.)
        if type_str == "BOSS_DEFEAT":
            cid = AP_BASE_ID + int(default_item_id)
            cname = AP_LOCATIONS.get(str(cid), f"Boss Defeat #{cid}")
            return cid, cname

        # 5. Storage +8 bought in the shop (Progressive Chip Capacity): next storage location not checked yet
        if type_str == "STORAGE_UPGRADE":
            for _, cid, cname in STORAGE_CAPACITY_CHECKS:
                if cid in self.ap_client.checked_locations or cid in self.sent_storage_checks:
                    continue
                self.sent_storage_checks.add(cid)
                return cid, AP_LOCATIONS.get(str(cid), cname)
            print("[*] [STORAGE] All storage upgrade locations are already checked.")
            return None, None

        # 6. Starting HUD chips: not locations (an older hook may still report them)
        if type_str == "SYSTEM_CHIP":
            return None, None

        # 7. Fishing: one check per species (location id = AP_BASE_ID + item id)
        if type_str == "FISH":
            cid = AP_BASE_ID + int(default_item_id)
            return cid, AP_LOCATIONS.get(str(cid), f"Fishing: #{default_item_id}")

        # 5. Ordinary ground loot / generic respawning wooden box: pass through without Archipelago check!
        return None, None

    def _resolve_hacking_chest(self, pos):
        if not pos:
            for hid in range(92000201, 92000233):
                if hid in self.ap_client.missing_locations:
                    return hid, AP_LOCATIONS.get(str(hid), f"Hacking Chest #{hid}")
            return 92000201, AP_LOCATIONS.get("92000201", "Hacking Chest")

        px, py, pz = pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)

        # Check if this exact spot was already assigned
        for key, (cid, cname) in self.discovered_chests.items():
            if isinstance(key, tuple):
                cx, cy, cz = key
                dist = math.sqrt((px - cx)**2 + (py - cy)**2 + (pz - cz)**2)
                if dist <= 25.0:
                    return cid, cname

        # Determine region
        if pz >= 150.0 and px <= -400.0:  # Desert
            region_chests = list(range(92000213, 92000218))
        elif px >= 10.0 and px <= 80.0 and pz >= -160.0 and pz <= -90.0:  # Resistance Camp
            region_chests = [92000212]
        elif px >= 550.0 and pz >= 50.0 and pz <= 350.0:  # Amusement Park
            region_chests = [92000218, 92000219, 92000220, 92000221]
        elif px >= 400.0 and px <= 550.0 and pz >= -250.0 and pz <= -140.0:  # Pascal's Village
            region_chests = [92000222, 92000223]
        elif px >= 750.0 and pz <= -350.0:  # Forest Kingdom
            region_chests = list(range(92000224, 92000229))
        elif pz >= 350.0 and px >= -250.0 and px <= 0.0:  # Flooded City
            region_chests = [92000229, 92000230, 92000231]
        elif pz >= 400.0 and px >= 100.0:  # Factory
            region_chests = [92000201, 92000202, 92000203, 92000204]
        elif py <= -80.0 and pz <= -700.0:  # Copied City
            region_chests = [92000232]
        else:  # City Ruins default
            region_chests = list(range(92000205, 92000212))

        # Pick first missing hacking chest in this region
        chosen_id = None
        for hid in region_chests:
            if hid in self.ap_client.missing_locations:
                chosen_id = hid
                break
        if not chosen_id:
            for hid in region_chests:
                if not any(cid == hid for cid, _ in self.discovered_chests.values()):
                    chosen_id = hid
                    break
        if not chosen_id:
            chosen_id = region_chests[0]

        cname = AP_LOCATIONS.get(str(chosen_id), f"Hacking Chest #{chosen_id}")
        self.discovered_chests[(px, py, pz)] = (chosen_id, cname)
        return chosen_id, cname

    def _handle_incoming_message(self, raw_line):
        try:
            msg = json.loads(raw_line)
            event = msg.get("event", "")

            if event == "handshake":
                print(f"\n>>> [NIER ENGINE CONNECTED] Game: {msg.get('game')} | Hook Version: {msg.get('version')}")
                print(">>> Type 'help' for available commands.\n")
                if self.ap_client.connected and self.ap_client.received_items_history:
                    print(f"[*] Re-delivering {len(self.ap_client.received_items_history)} Archipelago item(s) to the game...")
                    self.ap_client.last_item_index = 0
                    self.ap_client._deliver(0, len(self.ap_client.received_items_history))
                if self.ap_client.connected:
                    self.send_command({"cmd": "items_synced"})
                self.push_chapter_progress()

            elif event == "player_spawned":
                is_new_run = msg.get("new_run", False)
                pt = msg.get("playtime", 0)
                if is_new_run:
                    print(f"\n🔄 [AUTO RUN DETECTED] Hook detected fresh game / new run (Playtime: {pt}s)! Automatically resetting & re-injecting all items...")
                    self.reset_run(from_watcher=False)
                else:
                    print(f"\n[*] [SPAWN] Player spawned into world (Playtime: {pt}s). Synchronizing permanent items...")
                    self.resync_received_items(include_consumables=False)

            elif event == "check":
                check_num = msg.get("check_num")
                type_str = msg.get("type", "UNKNOWN")
                item_id = msg.get("item_id")
                qty = msg.get("quantity", 1)
                name = msg.get("name", "Unknown Item")
                rva = msg.get("caller_rva")
                call_stack = msg.get("call_stack", [])
                pos = msg.get("pos")

                loc_id, loc_name = self._resolve_chest_location(pos, item_id, type_str)
                if not loc_id:
                    # Ground loot or non-chest drop: ignored, passes through as normal vanilla loot!
                    return

                # Deduplicate / debounce: ignore duplicate events for the same location within 3 seconds
                now = time.time()
                if loc_id in self.recent_checks and (now - self.recent_checks[loc_id]) < 3.0:
                    print(f"[*] Suppressing duplicate check event for #{loc_id} ({loc_name})")
                    return
                self.recent_checks[loc_id] = now

                # Resolve clean vanilla item name
                clean_vanilla = name
                if not clean_vanilla or clean_vanilla in ["Unknown Item", "NieR Item", "NieR Weapon"]:
                    if item_id in WEAPON_NAMES:
                        clean_vanilla = WEAPON_NAMES[item_id]
                    elif str(AP_BASE_ID + item_id) in AP_ITEMS:
                        clean_vanilla = AP_ITEMS[str(AP_BASE_ID + item_id)]

                print(f"\n=========================================================")
                print(f" 🔥 [LOCATION CHECK DETECTED #{check_num}]")
                print(f"    Type: {type_str} | Identified Location: {loc_name}")
                print(f"    Archipelago Location ID: {loc_id}")
                print(f"    Vanilla Contents: {clean_vanilla} (ID: {item_id}) x{qty}")
                print(f"    Caller RVA: {rva}")
                if pos:
                    print(f"    2B World GPS: X={pos.get('x'):.2f}, Y={pos.get('y'):.2f}, Z={pos.get('z'):.2f}")

                # Send clean notification back to in-game YoRHa UI overlay!
                self.send_command({
                    "cmd": "sent_check_notify",
                    "location": loc_name,
                    "id": int(loc_id),
                    "item": clean_vanilla
                })

                # Send to Archipelago if connected!
                if self.ap_client.connected:
                    sent = self.ap_client.send_location_check(loc_id)
                    if sent:
                        print(f"    -> [ARCHIPELAGO]: Sent LocationCheck #{loc_id} to MultiWorld Server!")
                else:
                    self.pending_checks.add(int(loc_id))
                    print(f"    -> [LOCAL BRIDGE]: Check queued, sent as soon as Archipelago is connected")
                print(f"=========================================================\n> ", end="", flush=True)

            elif event == "item_granted":
                item_id = msg.get("item_id")
                qty = msg.get("quantity")
                status = msg.get("status")
                new_count = msg.get("new_count")
                count_info = f" (Total in Inventory: {new_count} / 99)" if new_count is not None else ""
                print(f"\n✨ [ITEM GRANTED] Item ID {item_id} x{qty} injected into NieR: {status}!{count_info}\n> ", end="", flush=True)

            elif event == "weapon_granted":
                weapon_id = msg.get("weapon_id")
                wname = msg.get("name", "NieR Weapon")
                lvl = msg.get("level", 1)
                status = msg.get("status")
                print(f"\n⚔️  [WEAPON GRANTED] {wname} (ID {weapon_id}) Lv.{lvl} injected into NieR: {status}!\n> ", end="", flush=True)

            elif event == "intercept_mode":
                enabled = msg.get("enabled")
                status_str = "ACTIVE (Vanilla chests blocked -> AP items granted)" if enabled else "OFF (Normal vanilla gameplay)"
                print(f"\n⚙️  [INTERCEPT MODE]: {status_str}\n> ", end="", flush=True)

            elif event == "level":
                self.check_level_milestones(int(msg.get("level", 0)))

            elif event == "death":
                self.ap_client.send_death()

            elif event == "phase":
                phase = msg.get("phase", "")
                if phase:
                    print(f"\n🗺️  [PHASE] {phase} (route {phase_route(phase)})\n> ", end="", flush=True)
                    log_phase_change(phase, msg.get("phase_id"))
                    self.remember_phase(phase, msg.get("phase_id"))
                    self.check_story_phase(phase)

            elif event == "status":
                money = msg.get("money", 0)
                exp = msg.get("exp", 0)
                level = int(msg.get("level", 0))
                checks = msg.get("checks", 0)
                intercept = msg.get("intercept", False)
                if level:
                    self.check_level_milestones(level)
                print(f"\n📊 [NIER IN-GAME STATUS]")
                print(f"    Money: {money:,} G")
                print(f"    Experience: {exp:,} XP (Lv {level})")
                print(f"    Total Checks Intercepted: {checks}")
                print(f"    Intercept Mode: {'ON' if intercept else 'OFF'}")
                print(f"    Archipelago MultiWorld: {'CONNECTED' if self.ap_client.connected else 'OFFLINE'}\n> ", end="", flush=True)

            elif event == "pong":
                print(f"\n🏓 [PONG] Hook is responsive!\n> ", end="", flush=True)

            elif event == "grants_idle":
                # The game confirms every item sent up to this index is really in the inventory
                self.ap_client.commit_delivered(msg.get("index", -1))

            elif event == "save_snapshot":
                # Live copy of the in-RAM save: validates quests/terminals/bosses/endings without saving
                self.save_watcher.parse_live_snapshot(msg)

            elif event == "active_slot":
                slot = msg.get("slot", -1)
                if slot in [0, 1, 2]:
                    self.save_watcher.set_slot(slot + 1)

            elif msg.get("cmd") == "set_slot":
                target = msg.get("target", "auto")
                self.save_watcher.set_slot(target)

            elif event == "inventory_weapons":
                weapons = msg.get("weapons", [])
                print(f"\n[*] [Save Inventory] Player holds {len(weapons)} weapons in save data.")
                synced = 0
                for w_id in weapons:
                    if w_id in WEAPON_TO_LOCATION_MAP:
                        loc_id, loc_name = WEAPON_TO_LOCATION_MAP[w_id]
                        if self.ap_client.connected:
                            if loc_id in self.ap_client.missing_locations:
                                print(f"  -> [AUTO-SYNC CHEST] Found already-acquired weapon in save: {loc_name} (Location #{loc_id})!")
                                self.ap_client.send_location_check(loc_id)
                                synced += 1
                if synced > 0:
                    print(f"🎉 [AUTO-SYNC COMPLETE] Synced {synced} missing checks to Archipelago Server!\n> ", end="", flush=True)
                else:
                    print(f"[*] [Save Sync] All owned weapons are already registered on Archipelago.\n> ", end="", flush=True)

            elif msg.get("cmd") in ["sync_weapons", "sync_save_checks", "sync_save"]:
                print(f"\n[In-Game YoRHa Menu] Syncing all save milestones (Endings, Terminals, Quests) & Weapons with Archipelago...\n> ", end="", flush=True)
                self.save_watcher.sync_all_save_milestones()
                self.send_command({"cmd": "get_weapons"})

            elif msg.get("cmd") == "ap_connect_request":
                server = msg.get("server")
                slot = msg.get("slot")
                pw = msg.get("password", "")
                print(f"\n[In-Game YoRHa Menu] Connecting to Archipelago: {server} (Slot: {slot})...\n> ", end="", flush=True)
                self.ap_client.connect(server, slot, pw)

            elif msg.get("cmd") == "ap_disconnect_request":
                print(f"\n[In-Game YoRHa Menu] Disconnecting from Archipelago...\n> ", end="", flush=True)
                self.ap_client.disconnect()

            elif msg.get("cmd") in ["resync_items", "sync_items"]:
                include_all = msg.get("include_all", True)
                print(f"\n[In-Game YoRHa Menu] Re-injecting all received Archipelago items into player's save (include_all={include_all})...")
                self.resync_received_items(include_consumables=include_all)

            elif msg.get("cmd") in ["reset_run", "reset_new_game", "new_game", "reset"]:
                print(f"\n[In-Game YoRHa Menu] New Game Reset requested! Resetting Archipelago state...")
                self.reset_run()

            else:
                print(f"\n[Raw Hook Message]: {raw_line}\n> ", end="", flush=True)

        except json.JSONDecodeError:
            print(f"\n[Hook Text]: {raw_line}\n> ", end="", flush=True)

    def send_command(self, cmd_dict):
        if not self.connected or not self.sock:
            print("[-] Cannot send command: Not connected to NieR.")
            return False
        try:
            payload = json.dumps(cmd_dict) + "\n"
            self.sock.sendall(payload.encode("utf-8"))
            return True
        except Exception as e:
            print(f"[-] Send failed: {e}")
            return False

    def push_shop_hints(self):
        """Sends the overlay what every not-yet-bought shop location contains (from LocationScouts)."""
        import unicodedata
        ap = self.ap_client
        if not self.connected:
            return  # pushed again once the game connects

        def clean(text):
            # The overlay font is ASCII only and the hook parses strings naively: no accents/quotes
            text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
            return text.replace('"', "'").replace("\\", "/")

        hints = []
        storage_shown = False
        for cid, cname in SHOP_HINT_LOCATIONS:
            if cid not in ap.scouted or cid in ap.checked_locations:
                continue
            if cid in STORAGE_LOCATION_IDS:
                if storage_shown:
                    continue  # purchases always go to the next storage location
                storage_shown = True
                cname = "Stockage +8 (prochain achat)"
            item_id, player, flags = ap.scouted[cid]
            game = ap.slot_games.get(player, "")
            item_name = ap.item_names.get(game, {}).get(item_id, f"Item #{item_id}")
            label = AP_LOCATIONS.get(str(cid), cname) if cid not in STORAGE_LOCATION_IDS else cname
            hints.append({"cmd": "shop_hint", "location": clean(label), "item": clean(item_name),
                          "player": clean(ap.players.get(player, f"Player #{player}")), "flags": int(flags)})

        self.send_command({"cmd": "shop_hint_clear"})
        for h in hints:
            self.send_command(h)

    def give_item(self, item_id, quantity=1, name="", sender="Archipelago MultiWorld", notify=True, total_gold=0, total_count=0, known_only=False, credited_gold=0):
        """Tells NieR to grant an item to the player.

        total_count: cumulative amount of this item received from the server (lets the hook merge
        re-sends without counting twice). known_only: the item was already delivered in a previous
        run, the hook only records it (nothing is granted)."""
        character = CHARACTER_ITEMS.get(int(item_id))
        if character:
            char_name, routes = character
            if notify:
                self.send_command({"cmd": "notify", "title": f"{char_name} DEBLOQUE",
                                   "text": f"Route {'/'.join(routes)} ouverte ({sender})"})
            return all([self.send_command({"cmd": "route_key", "route": r}) for r in routes])
        return self.send_command({
            "cmd": "give",
            "item_id": int(item_id),
            "quantity": int(quantity),
            "target_quantity": int(quantity),
            "total_count": int(total_count if total_count > 0 else quantity),
            "name": str(name),
            "sender": str(sender),
            "notify": bool(notify),
            "known_only": bool(known_only),
            "total_gold": int(total_gold),
            "credited_gold": int(credited_gold)
        })

    def resync_received_items(self, include_consumables=False):
        """Re-sends Archipelago items to NieR: Automata without spamming UI notifications.

        By default only permanent items are replayed (weapons, pod programs) so nothing gets
        duplicated. Pass include_consumables=True to also replay chips / consumables / materials /
        gold (brand-new run or manual 'give me everything'). The hook merges using cumulative totals,
        so replaying never counts an item twice."""
        history = [h for h in self.ap_client.received_items_history if h is not None]
        if not history:
            print("[*] No Archipelago items have been received yet in this room/session.")
            return
        print(f"\n🎁 [SYNC ITEMS] Re-ensuring {len(history)} received item(s) in your NieR: Automata save "
              f"({'including' if include_consumables else 'excluding'} consumables/gold)...")
        counts = {}   # nier_id -> [count, sender, name]
        for nier_id, sender_name, clean_name in history:
            if is_weapon_id(nier_id):
                self.give_weapon(nier_id, 1, name=clean_name, sender=sender_name, notify=False)
            elif is_idempotent_item(nier_id):
                self.give_item(nier_id, 1, name=clean_name, sender=sender_name, notify=False)
            elif include_consumables:
                c = counts.setdefault(nier_id, [0, sender_name, clean_name])
                c[0] += 1
            time.sleep(0.01)
        gold_total, _ = self.ap_client.gold_totals()
        for nier_id, (count, sender_name, clean_name) in counts.items():
            self.give_item(nier_id, count, name=clean_name, sender=sender_name, notify=False,
                           total_count=count,
                           total_gold=gold_total if nier_id in GOLD_BUNDLE_AMOUNTS else 0)
        print("✅ [SYNC ITEMS] Done!\n> ", end="", flush=True)

    def reset_run(self, from_watcher=False):
        """Full reset for a fresh game / new run:
        - Resets Archipelago item delivery state (committed_index = 0)
        - Clears local baseline & found check caches
        - Signals the C++ hook to clear intercepted starting checks & arm all items
        - Re-injects all received weapons, pod programs, chips, consumables, materials, and gold!
        """
        print("\n=========================================================")
        print(" 🔄 [RESET NOUVELLE PARTIE] Réinitialisation de la session de jeu...")
        print("=========================================================")

        self.ap_client.committed_index = 0
        self.ap_client.last_item_index = 0
        self.ap_client.pending_commit_index = 0
        with _state_lock:
            state = load_received_state()
            if self.ap_client._state_key() in state:
                state[self.ap_client._state_key()] = {"committed_index": 0}
                save_received_state(state)

        self.save_watcher.baseline_established = False
        self.save_watcher.baseline_checks.clear()
        self.save_watcher.quest_baseline = None
        self.save_watcher.found_checks.clear()
        self.save_watcher.live_last_blob_hash = None
        self.save_watcher.live_text_confirmed = False

        # Tell DLL to clear intercepted checks and arm all items
        self.send_command({"cmd": "reset_run_state"})

        # Re-inject ALL received items
        self.resync_received_items(include_consumables=True)
        print("✅ [RESET RUN] Prêt ! Tous vos objets ont été ré-injectés dans votre nouvelle partie.\n> ", end="", flush=True)

    def give_weapon(self, weapon_id, level=1, name="", sender="Archipelago MultiWorld", notify=True):
        """Tells NieR to grant a weapon directly to the player."""
        return self.send_command({
            "cmd": "give_weapon",
            "weapon_id": int(weapon_id),
            "level": int(level),
            "name": str(name),
            "sender": str(sender),
            "notify": bool(notify)
        })

    def set_intercept(self, enable=True):
        """Enables or disables item drop interception in NieR."""
        return self.send_command({
            "cmd": "set_intercept",
            "enabled": bool(enable)
        })

    def query_status(self):
        """Queries current in-game money, exp, and stats."""
        return self.send_command({"cmd": "status"})

    def ping(self):
        return self.send_command({"cmd": "ping"})


def print_help():
    print("""
========================================================================
  NieR: Automata - Archipelago MultiWorld Client CLI
========================================================================
Archipelago Commands:
  ap_connect <server:port> <slot> [pw] - Connect to Archipelago MultiWorld
                                        (ex: 'ap_connect archipelago.gg:38281 Player1')
  ap_disconnect                        - Disconnect from Archipelago Server
  ap_status                            - Show MultiWorld room & checks status
  sync_items [all]                     - Re-ensure received weapons/pod programs in the game.
                                         'sync_items all' ALSO re-adds consumables/materials/gold (duplicates them!)

Save & Progression Commands:
  slot [1|2|3|auto]                    - View or set monitored save slot (ex: 'slot 2' for Nao)

In-Game Testing Commands:
  give <id> [count]                    - Inject item into player's inventory
                                        (ex: 'give 0 5' = 5x Small Recovery, 'give 601 10' = 10x Iron Ore)
  give_weapon <id> [lvl 1-4]           - Inject weapon into player's weapon list
                                        (ex: 'give_weapon 1220 4' = Beastlord Lv.4, 'give_weapon 1610 1' = Type-4O Fists)
  intercept <on|off>                   - Toggle Chest Intercept Mode
  status                               - Query in-game Money, EXP, and stats
  ping                                 - Test latency with the DLL hook
  cls / clear                          - Clear screen
  help                                 - Show this help message
  exit / quit                          - Disconnect and exit
========================================================================
""")


def main():
    bridge = NieRArchipelagoBridge()
    try:
        bridge.connect()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

    print_help()

    while bridge.running:
        try:
            if not sys.stdin or not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
                time.sleep(0.5)
                continue
            cmd = input("> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action in ["exit", "quit"]:
                print("Disconnecting...")
                bridge.ap_client.disconnect()
                bridge.running = False
                break

            elif action == "help":
                print_help()

            elif action in ["cls", "clear"]:
                import os
                os.system("cls" if os.name == "nt" else "clear")

            elif action == "slot":
                if len(parts) == 1:
                    bridge.save_watcher.print_slots()
                else:
                    bridge.save_watcher.set_slot(parts[1])

            elif action in ["ap_connect", "apconnect", "connect"]:
                if len(parts) < 3:
                    print("Usage: ap_connect <host:port> <slot_name> [password]")
                    print("  Example: ap_connect archipelago.gg:38281 2B")
                    continue
                server = parts[1]
                slot = parts[2]
                pw = parts[3] if len(parts) > 3 else ""
                bridge.ap_client.connect(server, slot, pw)

            elif action in ["ap_disconnect", "disconnect"]:
                bridge.ap_client.disconnect()
                print("[*] Disconnected from Archipelago MultiWorld.")

            elif action in ["ap_status", "apstatus"]:
                ap = bridge.ap_client
                print(f"\n🌐 [ARCHIPELAGO STATUS]")
                print(f"    Server: {ap.server_url if ap.connected else 'Disconnected'}")
                print(f"    Slot: {ap.slot_name} (ID: {ap.slot_id})")
                print(f"    Checked Locations: {len(ap.checked_locations)}")
                print(f"    Remaining Locations: {len(ap.missing_locations)}")
                print(f"    Connected Players: {', '.join(ap.players.values()) if ap.players else 'None'}\n")

            elif action in ["reset", "reset_run", "new_game", "restart"]:
                bridge.reset_run()

            elif action in ["sync_items", "resync_items", "resync"]:
                all_flag = (len(parts) > 1 and parts[1].lower() in ["all", "tout", "1", "true"]) or (len(parts) == 1)
                bridge.resync_received_items(include_consumables=all_flag)

            elif action in ["sync", "sync_save", "sync_checks"]:
                bridge.save_watcher.sync_all_save_milestones()
                bridge.send_command({"cmd": "get_weapons"})

            elif action == "give":
                if len(parts) < 2:
                    print("Usage: give <item_id> [count]")
                    continue
                item_id = int(parts[1])
                count = int(parts[2]) if len(parts) > 2 else 1
                bridge.give_item(item_id, count)

            elif action in ["give_weapon", "giveweapon", "weapon"]:
                if len(parts) < 2:
                    print("Usage: give_weapon <weapon_id> [level]")
                    print("  Examples: 'give_weapon 1070 1' (Virtuous Contract), 'give_weapon 1220 4' (Beastlord Lv.4), 'give_weapon 1610 1' (Type-4O Fists)")
                    continue
                weapon_id = int(parts[1])
                level = int(parts[2]) if len(parts) > 2 else 1
                bridge.give_weapon(weapon_id, level)

            elif action == "intercept":
                if len(parts) < 2 or parts[1].lower() not in ["on", "off", "1", "0", "true", "false"]:
                    print("Usage: intercept on | intercept off")
                    continue
                enable = parts[1].lower() in ["on", "1", "true"]
                bridge.set_intercept(enable)

            elif action == "status":
                bridge.query_status()

            elif action == "ping":
                bridge.ping()

            else:
                print(f"Unknown command: '{action}'. Type 'help' for list of commands.")

        except (EOFError, KeyboardInterrupt):
            time.sleep(0.5)
            continue
        except Exception as e:
            print(f"[-] Command error: {e}")

    if bridge.sock:
        bridge.sock.close()
    bridge.ap_client.disconnect()
    print("[*] Bridge terminated.")


if __name__ == "__main__":
    main()
