"""
NieR: Automata Archipelago World Options
"""

from dataclasses import dataclass
from Options import Choice, Toggle, PerGameCommonOptions

class Goal(Choice):
    """The victory condition for NieR: Automata."""
    display_name = "Goal"
    option_prologue_engels = 0
    option_ending_a = 1
    option_ending_e = 2
    default = 0

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
    quest_progression: QuestProgression
    death_link: DeathLink
