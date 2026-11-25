"""
Archipelago World implementation for NieR: Automata
"""

from typing import Dict, Any, List
from BaseClasses import Tutorial, Item, ItemClassification
from worlds.AutoWorld import World, WebWorld

import logging

from .Items import NieRItem, item_table, item_counts, AP_BASE_ID, CHAPTER_NAMES, CHAPTER_ITEMS
from .Locations import (NieRLocation, location_table, locations_for_goal, START_CHAPTERS,
                        CHAPTER_SHUFFLE_GOALS)
from .Regions import create_regions
from .Rules import set_rules
from .Options import NieRAutomataOptions

# Options.Goal value -> region of the "Victory" event (Rules.py also ties it to the goal's ending location)
GOAL_REGIONS = {0: "Abandoned Factory", 1: "Copied City", 3: "Route B", 4: "Route C", 5: "Route D", 2: "Route D"}
# Characters each goal needs (9S = route B, A2 = routes C/D); the others are left out of the pool.
# Prologue is a test goal that keeps every check, so it keeps both.
GOAL_CHARACTERS = {0: ("9S", "A2"), 1: (), 3: ("9S",), 4: ("9S", "A2"), 5: ("9S", "A2"), 2: ("9S", "A2")}
CHARACTER_ITEMS = ("9S", "A2")

class NieRAutomataWeb(WebWorld):
    theme = "ocean"
    tutorials = [
        Tutorial(
            "NieR: Automata MultiWorld Setup Guide",
            "A guide to setting up the NieR: Automata Archipelago Randomizer mod.",
            "English",
            "setup_en.md",
            "setup/en",
            ["Google DeepMind"]
        )
    ]

class NieRAutomataWorld(World):
    """
    NieR: Automata is an action role-playing game developed by PlatinumGames.
    Explore an open, ruined Earth as androids 2B and 9S in a proxy war against machine lifeforms.
    """
    game: str = "NieR Automata"
    web = NieRAutomataWeb()
    options_dataclass = NieRAutomataOptions
    options: NieRAutomataOptions

    item_name_to_id = {name: data.code for name, data in item_table.items()}
    location_name_to_id = {name: data.code for name, data in location_table.items()}

    base_id = AP_BASE_ID

    def create_item(self, name: str) -> NieRItem:
        item_data = item_table[name]
        return NieRItem(name, item_data.classification, item_data.code, self.player)

    def generate_early(self) -> None:
        if self.options.chapter_shuffle and self.options.goal.value not in CHAPTER_SHUFFLE_GOALS:
            logging.warning(f"NieR Automata ({self.player_name}): chapter_shuffle only supports goal ending_a or "
                            f"ending_b for now, it is turned off.")
            self.options.chapter_shuffle.value = 0
        # Chapter shuffle: the starting chapter is given at the start, the others are in the pool
        self.start_chapter = self.random.choice(START_CHAPTERS) if self.options.chapter_shuffle else None
        if self.start_chapter:
            self.multiworld.push_precollected(self.create_item(CHAPTER_NAMES[self.start_chapter]))

    def create_items(self) -> None:
        itempool: List[NieRItem] = []
        characters = GOAL_CHARACTERS[self.options.goal.value]
        shuffle = bool(self.options.chapter_shuffle)

        # 1. Every defined item at least once (progression, useful AND filler such as chips, consumables, gold),
        # except the characters of routes the goal doesn't need
        for name, data in item_table.items():
            if name in CHARACTER_ITEMS and name not in characters:
                continue
            if name in CHAPTER_ITEMS and (not shuffle or name == CHAPTER_NAMES.get(self.start_chapter)):
                continue  # chapters: chapter_shuffle only, the starting one is already given
            for _ in range(item_counts.get(name, 1)):
                itempool.append(self.create_item(name))

        # 2. Exactly one item per location (the "Victory" event is not in the pool): drop filler if there are
        # more items than locations, otherwise fill with materials, recovery items and bonus gold
        total_locations = len(self.goal_locations)
        if len(itempool) > total_locations:
            fillers_in_pool = [item for item in itempool if item.classification == ItemClassification.filler]
            for item in fillers_in_pool[total_locations - len(itempool):]:
                itempool.remove(item)
        remaining = total_locations - len(itempool)

        fillers = [
            "Small Recovery", "Medium Recovery", "Large Recovery", "Iron Ore", "Copper Ore",
            "Silver Ore", "Gold Ore", "Titanium Alloy", "Memory Alloy", "Rusted Clump",
            "Natural Rubber", "Pyrite", "Meteorite", "Gold Bundle (1000 G)", "Gold Bundle (2500 G)"
        ]
        filler_idx = 0
        for _ in range(remaining):
            itempool.append(self.create_item(fillers[filler_idx % len(fillers)]))
            filler_idx += 1

        self.multiworld.itempool += itempool

    def create_regions(self) -> None:
        # Only the checks that can be done before the goal's ending (an ending A seed has no route B/C/D checks)
        self.goal_locations = locations_for_goal(self.options.goal.value)
        shuffle = bool(self.options.chapter_shuffle)
        create_regions(self.multiworld, self.player, self.goal_locations,
                       bool(self.options.quest_progression.value), shuffle)

        # Goal event, in the region where the goal is reached. The bridge reports the goal to the server
        # when the matching location (Engels / Ending A to E) is checked.
        region = self.multiworld.get_region("Chapters" if shuffle else GOAL_REGIONS[self.options.goal.value],
                                            self.player)
        victory = NieRLocation(self.player, "Victory", None, region)
        victory.place_locked_item(NieRItem("Victory", ItemClassification.progression, None, self.player))
        region.locations.append(victory)

    def set_rules(self) -> None:
        set_rules(self)

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "goal": self.options.goal.value,
            "death_link": self.options.death_link.value,
            "chapter_shuffle": self.options.chapter_shuffle.value,
            "start_chapter": self.start_chapter or 0,
            "version": "0.2.0"
        }
