"""
NieR: Automata Archipelago Regions and Connections
"""

from typing import Dict
from BaseClasses import MultiWorld, Region, Entrance, LocationProgressType
from .Locations import (NieRLocation, LocationData, EXCLUDED_LOCATIONS, VERIFIED_QUEST_LOCATIONS, STORY_CHAPTERS,
                        REGION_CHAPTERS)

def create_regions(multiworld: MultiWorld, player: int, locations: Dict[str, LocationData],
                   quest_progression: bool = False, chapter_shuffle: bool = False) -> None:
    """Creates the regions with the given locations (Locations.locations_for_goal: only the checks that can be
    done before the goal's ending).
    chapter_shuffle: no geographic graph, every area is entered from the menu with one of its chapters (Rules.py)
    and the story checks sit in a "Chapters" region, each behind its own chapter."""
    excluded = EXCLUDED_LOCATIONS - VERIFIED_QUEST_LOCATIONS if quest_progression else EXCLUDED_LOCATIONS
    if chapter_shuffle:
        # Starting a chapter from the Chapter Select presets the story state before it: quests done, access points
        # on. Those checks come for free, or can no longer be done in that save: filler only, so neither matters.
        excluded = excluded | {name for name in locations if name.startswith(("Quest: ", "Terminal: "))}
    region_names = [
        "Menu",
        "Abandoned Factory",
        "City Ruins",
        "Resistance Camp",
        "Desert Zone",
        "Amusement Park",
        "Pascal's Village",
        "Forest Kingdom",
        "Flooded City",
        "Copied City",
        "Emil's Residence",
        # Story routes after route A: B behind 9S, C and D behind A2 (see Rules.py)
        "Route B",
        "Route C",
        "Route D",
        "Chapters",  # chapter_shuffle only
    ]

    regions: Dict[str, Region] = {}
    for name in region_names:
        regions[name] = Region(name, player, multiworld)

    # Populate locations
    for loc_name, loc_data in locations.items():
        region = regions["Chapters" if chapter_shuffle and loc_name in STORY_CHAPTERS else loc_data.region]
        location = NieRLocation(player, loc_name, loc_data.code, region)
        if loc_name in excluded:
            location.progress_type = LocationProgressType.EXCLUDED  # filler only (unverified detection)
        region.locations.append(location)

    # Connect regions with standard entrance naming "{source} to {target}"
    def connect(source: str, target: str, two_way: bool = False):
        source_region = regions[source]
        target_region = regions[target]
        entrance = Entrance(player, f"{source} to {target}", source_region)
        source_region.exits.append(entrance)
        entrance.connect(target_region)
        if two_way:
            back_entrance = Entrance(player, f"{target} to {source}", target_region)
            target_region.exits.append(back_entrance)
            back_entrance.connect(source_region)

    if chapter_shuffle:
        for area in REGION_CHAPTERS:
            connect("Menu", area)
        connect("Menu", "Chapters")
        connect("Menu", "Route B")
        for region in regions.values():
            multiworld.regions.append(region)
        return

    # World Connectivity Graph
    connect("Menu", "Abandoned Factory")
    connect("Abandoned Factory", "City Ruins", two_way=True)
    connect("City Ruins", "Resistance Camp", two_way=True)
    connect("City Ruins", "Desert Zone", two_way=True)
    connect("City Ruins", "Amusement Park", two_way=True)
    connect("Amusement Park", "Pascal's Village", two_way=True)
    connect("Pascal's Village", "Forest Kingdom", two_way=True)
    connect("City Ruins", "Flooded City", two_way=True)
    connect("City Ruins", "Copied City", two_way=True)
    connect("City Ruins", "Emil's Residence", two_way=True)
    connect("Copied City", "Route B")
    connect("Route B", "Route C")
    connect("Route C", "Route D")

    for region in regions.values():
        multiworld.regions.append(region)
