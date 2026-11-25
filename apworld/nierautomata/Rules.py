"""
NieR: Automata Archipelago Logic Rules (Pack Ultime - 216 Checks)
"""

from typing import TYPE_CHECKING
from worlds.generic.Rules import set_rule
from .Items import CHAPTER_NAMES
from .Locations import GOAL_ENDING_LOCATIONS, STORY_CHAPTERS, STORY_NO_WEAPON, REGION_CHAPTERS

if TYPE_CHECKING:
    from . import NieRAutomataWorld

# Route A/B story order, by the region where each part of the story happens
STORY_CHAIN = ["Abandoned Factory", "City Ruins", "Resistance Camp", "Desert Zone", "Amusement Park",
               "Pascal's Village", "Forest Kingdom", "Flooded City", "Copied City"]

# Story milestones -> the part of the story (STORY_CHAIN region) they come after
STORY_POSITIONS = {
    "Story: Arrive at the Resistance Camp": "Resistance Camp",
    "Story: Reach the Desert": "Desert Zone",
    "Desert: Adam Battle Reward": "Desert Zone",
    "Story: Reach the Amusement Park": "Amusement Park",
    "Amusement Park: Golden Machine Tank Defeated": "Amusement Park",
    "Amusement Park: Beauvoir Defeated": "Amusement Park",
    "Story: Reach Pascal's Village": "Pascal's Village",
    "City Ruins: Alien Mothership - Adam & Eve Victory": "Pascal's Village",
    "Story: Reach the Forest Castle": "Forest Kingdom",
    "Story: Flooded City Battle": "Flooded City",
    "Story: Giant Machine Defeated": "Flooded City",
    "Copied City: Adam Battle (Climax) Victory": "Copied City",
    "Story: Underground Factory Boss Defeated": "Copied City",
    "Story: Eve Defeated": "Copied City",
    "Ending A: Flowers for m[A]chines": "Copied City",
}

WEAPONS = ["Virtuous Contract", "Beastlord", "Cruel Oath", "Iron Will", "Type-4O Sword", "Machine Sword"]
# Extra requirements of some areas (same as the geographic graph's entrances)
AREA_REQUIREMENTS = {
    "Forest Kingdom": ["Pod Program: Laser (R010)", "Pod Program: Hammer (R030)", "Beastlord", "Machine Axe"],
    "Copied City": ["Virtuous Contract", "Type-4O Blade", "Cruel Blood Oath", "Beastbane"],
    "Emil's Residence": ["Hacking Module (9S Ability)", "Pod Program: Laser (R010)"],
}


def set_chapter_shuffle_rules(world: "NieRAutomataWorld") -> None:
    """chapter_shuffle: an area needs a chapter whose story goes there, a story check needs its own chapter."""
    player = world.player
    mw = world.multiworld

    def any_chapter(chapters):
        names = [CHAPTER_NAMES[ch] for ch in chapters]
        return lambda state: state.has_any(names, player)

    for area, chapters in REGION_CHAPTERS.items():
        chapter_rule = any_chapter(chapters)
        extra = AREA_REQUIREMENTS.get(area)
        if extra:
            set_rule(mw.get_entrance(f"Menu to {area}", player),
                     lambda state, c=chapter_rule, e=extra: c(state) and state.has_any(e, player))
        else:
            set_rule(mw.get_entrance(f"Menu to {area}", player), chapter_rule)
    # Route B: played as 9S, its checks are at the Amusement Park (Game Dev Machine) or in its own endings
    set_rule(mw.get_entrance("Menu to Route B", player),
             lambda state: state.has("9S", player) and state.has(CHAPTER_NAMES[4], player))

    for location in mw.get_region("Chapters", player).locations:
        if location.name not in STORY_CHAPTERS:
            continue
        chapter = CHAPTER_NAMES[STORY_CHAPTERS[location.name]]
        needs_weapon = location.name not in STORY_NO_WEAPON
        needs_9s = location.name == "Ending B: or not to [B]e"
        set_rule(location, lambda state, c=chapter, w=needs_weapon, n=needs_9s:
                 state.has(c, player) and (not w or state.has_any(WEAPONS, player))
                 and (not n or state.has("9S", player)))

    victory = mw.get_location("Victory", player)
    ending = mw.get_location(GOAL_ENDING_LOCATIONS[world.options.goal.value], player)
    set_rule(victory, lambda state: ending.can_reach(state))
    mw.completion_condition[player] = lambda state: state.has("Victory", player)


def set_rules(world: "NieRAutomataWorld") -> None:
    player = world.player
    if world.options.chapter_shuffle:
        set_chapter_shuffle_rules(world)
        return

    # 1. To leave Factory (Prologue), player needs combat capability
    set_rule(world.multiworld.get_entrance("Abandoned Factory to City Ruins", player),
             lambda state: state.has_any(["Virtuous Contract", "Beastlord", "Cruel Oath", "Iron Will", "Type-4O Sword", "Machine Sword"], player))

    # 2. Forest Kingdom access requires Pod Program or Heavy Weapon
    set_rule(world.multiworld.get_entrance("Pascal's Village to Forest Kingdom", player),
             lambda state: state.has_any(["Pod Program: Laser (R010)", "Pod Program: Hammer (R030)", "Beastlord", "Machine Axe"], player))

    # 3. Copied City entrance requires combat prowess
    set_rule(world.multiworld.get_entrance("City Ruins to Copied City", player),
             lambda state: state.has_any(["Virtuous Contract", "Type-4O Blade", "Cruel Blood Oath", "Beastbane"], player))

    # 4. Emil's Residence deep access requires Hacking Module (9S Ability) or combat mastery
    set_rule(world.multiworld.get_entrance("City Ruins to Emil's Residence", player),
             lambda state: state.has_any(["Hacking Module (9S Ability)", "Pod Program: Laser (R010)"], player))

    # 6. All 9S Hacking Chests strictly require the Hacking Module
    for location in world.multiworld.get_locations(player):
        if "Hacking Chest" in location.name:
            set_rule(location, lambda state: state.has("Hacking Module (9S Ability)", player))

    # 6a. Story order: regions are geographic, but a story milestone is only reached after every earlier part of
    # the story, so it needs every region that comes before it (otherwise an item gating an earlier region could
    # sit on a later milestone and lock the run).
    def story_rule(position):
        regions = STORY_CHAIN[:position + 1]
        return lambda state: all(state.can_reach(r, "Region", player) for r in regions)

    for loc_name, region in STORY_POSITIONS.items():
        set_rule(world.multiworld.get_location(loc_name, player), story_rule(STORY_CHAIN.index(region)))

    # 6b. Routes: 9S opens route B, A2 routes C and D (the hook sends the player back to the title screen when
    # entering a locked route, and starts route A/B chapters with 2B until 9S is received). Route B follows the
    # whole route A story.
    route_b = world.multiworld.get_entrance("Copied City to Route B", player)
    route_a_done = story_rule(len(STORY_CHAIN) - 1)
    set_rule(route_b, lambda state: state.has("9S", player) and route_a_done(state))
    for region in STORY_CHAIN:
        world.multiworld.register_indirect_condition(world.multiworld.get_region(region, player), route_b)
    set_rule(world.multiworld.get_entrance("Route B to Route C", player),
             lambda state: state.has("A2", player))

    # 7. Goal: the "Victory" event sits in the goal region (GOAL_REGIONS in __init__.py: Abandoned Factory for
    # Engels, Copied City for ending A, Route B/C/D for endings B to E). Beating Engels needs a weapon, like
    # leaving the factory.
    # An ending goal also needs everything its ending location needs (the story before it).
    victory = world.multiworld.get_location("Victory", player)
    if world.options.goal.value == 0:
        set_rule(victory,
                 lambda state: state.has_any(["Virtuous Contract", "Beastlord", "Cruel Oath", "Iron Will", "Type-4O Sword", "Machine Sword"], player))
    else:
        ending = world.multiworld.get_location(GOAL_ENDING_LOCATIONS[world.options.goal.value], player)
        set_rule(victory, lambda state: ending.can_reach(state))
    world.multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
