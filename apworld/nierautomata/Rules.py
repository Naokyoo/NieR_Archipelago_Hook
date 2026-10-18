"""
NieR: Automata Archipelago Logic Rules (Pack Ultime - 216 Checks)
"""

from typing import TYPE_CHECKING
from worlds.generic.Rules import set_rule
from .Locations import location_table

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

def set_rules(world: "NieRAutomataWorld") -> None:
    player = world.player

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
    for loc_name in location_table:
        if "Hacking Chest" in loc_name:
            set_rule(world.multiworld.get_location(loc_name, player),
                     lambda state: state.has("Hacking Module (9S Ability)", player))

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

    # 7. Goal: the "Victory" event sits in the goal region (Abandoned Factory for Engels, Copied City for
    # ending A, Route D for ending E). Beating Engels needs a weapon, like leaving the factory.
    if world.options.goal.value == 0:
        set_rule(world.multiworld.get_location("Victory", player),
                 lambda state: state.has_any(["Virtuous Contract", "Beastlord", "Cruel Oath", "Iron Will", "Type-4O Sword", "Machine Sword"], player))
    world.multiworld.completion_condition[player] = lambda state: state.has("Victory", player)
