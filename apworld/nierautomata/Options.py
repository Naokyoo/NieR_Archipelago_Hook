"""
NieR: Automata Archipelago World Options
"""

from dataclasses import dataclass
from Options import Choice, Toggle, PerGameCommonOptions

class Goal(Choice):
    """The ending that completes your game. Only the checks you can do before that ending are in the seed
    (an ending A seed has no route B, C or D checks, and no 9S or A2 items).
    prologue_engels: beat Engels at the end of the prologue (test goal, every check stays in the seed).
    ending_a: Ending A (route A, 2B).
    ending_b: Ending B (route B, needs the 9S item).
    ending_c: Ending C (routes C/D, choose A2 at the end; needs 9S and A2).
    ending_d: Ending D (routes C/D, choose 9S at the end; needs 9S and A2).
    ending_e: Ending E (after endings C and D; needs 9S and A2)."""
    display_name = "Goal"
    # Values are sent to the bridge in slot_data (GOAL_LOCATIONS): keep the old ones as they are.
    option_prologue_engels = 0
    option_ending_a = 1
    option_ending_e = 2
    option_ending_b = 3
    option_ending_c = 4
    option_ending_d = 5
    default = 1

class ChapterShuffle(Toggle):
    """Chapters are items. You start with one random chapter and play it from the title screen's Chapter Select;
    the other chapters come from the multiworld, in any order. Entering a chapter you haven't received sends you
    back to the title screen, so the story is played in a random order.
    Starting a chapter presets the story before it (quests done, access points on), so side quests and access
    points only hold filler with this option.
    Routes A/B (chapters 1 to 10) only for now: goal ending_a or ending_b (with another goal it is turned off)."""
    display_name = "Chapter Shuffle"

class QuestProgression(Toggle):
    """Allow progression and useful items on side quests whose completion was verified in a real save.
    Off: every side quest is still a check but only holds filler (a quest can become impossible as the story advances)."""
    display_name = "Quest Progression"

class DeathLink(Toggle):
    """When you die in NieR: Automata, all linked players die. When another player dies, you take lethal damage."""
    display_name = "Death Link"

@dataclass
class NieRAutomataOptions(PerGameCommonOptions):
    goal: Goal
    chapter_shuffle: ChapterShuffle
    quest_progression: QuestProgression
    death_link: DeathLink
