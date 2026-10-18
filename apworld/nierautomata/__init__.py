"""
Archipelago World implementation for NieR: Automata
"""

from typing import Dict, Any, List
from BaseClasses import Tutorial, Item, ItemClassification
from worlds.AutoWorld import World, WebWorld

from .Items import NieRItem, item_table, item_counts, AP_BASE_ID
from .Locations import NieRLocation, location_table
from .Regions import create_regions
from .Rules import set_rules
from .Options import NieRAutomataOptions

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

    def create_items(self) -> None:
        itempool: List[NieRItem] = []

        # 1. Every defined item at least once (progression, useful AND filler such as chips, consumables, gold)
        for name, data in item_table.items():
            for _ in range(item_counts.get(name, 1)):
                itempool.append(self.create_item(name))

        # 2. Fill remaining location slots with materials, recovery items and bonus gold
        total_locations = len(location_table)
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
        create_regions(self.multiworld, self.player, bool(self.options.quest_progression.value))

        # Goal event, in the region where the goal is reached. The bridge reports the goal to the server
        # when the matching location (Engels / Ending A / Ending E) is checked.
        goal_region = {0: "Abandoned Factory", 1: "Copied City", 2: "Route D"}[self.options.goal.value]
        region = self.multiworld.get_region(goal_region, self.player)
        victory = NieRLocation(self.player, "Victory", None, region)
        victory.place_locked_item(NieRItem("Victory", ItemClassification.progression, None, self.player))
        region.locations.append(victory)

    def set_rules(self) -> None:
        set_rules(self)

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "goal": self.options.goal.value,
            "death_link": self.options.death_link.value,
            "version": "0.1.0"
        }
