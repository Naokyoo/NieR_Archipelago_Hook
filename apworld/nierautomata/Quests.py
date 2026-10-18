"""
NieR: Automata side quests.

Quest ids and names come from the YoRHa Protocol overlay ("Lost Girl (quest/q110)"), cross-checked
against the SceneState of real saves. Quest ids are hex. "qNNN/<state>" is the current state
(REQ = accepted, DONE/FIN = completed, BREAK = no longer possible) while "qNNN_DONE"/"qNNN_FIN" is a
permanent marker that survives a later BREAK; either one means the quest was completed.
Regions are approximate (quest giver area).
"""

from typing import Dict, Tuple

QUEST_LOCATION_OFFSET = 10000  # location id = AP_BASE_ID + QUEST_LOCATION_OFFSET + int(qid[1:], 16)

QUEST_TABLE: Dict[str, Tuple[str, str]] = {
    "q020": ("Jean-Paul's Melancholy", "Pascal's Village"),
    "q031": ("Machine Examination 1", "Resistance Camp"),
    "q032": ("Machine Examination 2", "Resistance Camp"),
    "q040": ("Family Squabble", "Pascal's Village"),
    "q070": ("Of Machines and Beasts", "City Ruins"),
    "q071": ("Animal Care", "City Ruins"),
    "q072": ("Turf War", "Desert Zone"),
    "q085": ("Mysterious Letter", "City Ruins"),
    "q090": ("Underground Colosseum", "City Ruins"),
    "q091": ("Gambler's Colosseum", "City Ruins"),
    "q092": ("Trial of Sand", "Desert Zone"),
    "q095": ("Mysterious Invitation", "City Ruins"),
    "q100": ("Robo Dojo - White Belt", "City Ruins"),
    "q101": ("Robo Dojo - Brown Belt", "City Ruins"),
    "q102": ("Robo Dojo - Black Belt", "City Ruins"),
    "q103": ("Robo Dojo - Red and White Belt", "City Ruins"),
    "q104": ("Robo Dojo - Red Belt", "City Ruins"),
    "q110": ("Lost Girl", "City Ruins"),
    "q120": ("The Supply Trader's Request", "Resistance Camp"),
    "q121": ("The Manager's Request", "Resistance Camp"),
    "q122": ("Camp Development", "Resistance Camp"),
    "q123": ("Anemone's Past", "Resistance Camp"),
    "q130": ("Amnesia", "Resistance Camp"),
    "q140": ("Resistance Disappearance", "Resistance Camp"),
    "q150": ("Jackass's Research", "Desert Zone"),
    "q160": ("Improving Communications", "City Ruins"),
    "q162": ("Investigating Communications", "City Ruins"),
    "q170": ("Terminal Repairs", "Resistance Camp"),
    "q171": ("Find a Present", "Resistance Camp"),
    "q180": ("Data Analysis Freak", "Resistance Camp"),
    "q181": ("Data Analysis Freak 2", "Resistance Camp"),
    "q210": ("Lord of the Valley", "Forest Kingdom"),
    "q220": ("Vanquish the Bad Bot", "Pascal's Village"),
    "q221": ("Play with Us!", "Pascal's Village"),
    "q222": ("Storage Element", "Pascal's Village"),
    "q240": ("Half-wit Inventor", "Pascal's Village"),
    "q250": ("Idiot Savant", "Pascal's Village"),
    "q290": ("Game Dev Machine Lv.1", "Amusement Park"),
    "q291": ("Game Dev Machine Lv.2", "Amusement Park"),
    "q292": ("Game Dev Machine Lv.3", "Amusement Park"),
    "q300": ("Speed Star", "City Ruins"),
    "q330": ("Emil's Memories", "City Ruins"),
    "q340": ("Photographs", "Resistance Camp"),
    "q360": ("In A High Place", "City Ruins"),
    "q400": ("The Vengeful Warrior", "City Ruins"),
    "q401": ("The Vengeful Warrior Returns", "City Ruins"),
    "q403": ("The Vengeful Warrior's Finale", "City Ruins"),
    "q410": ("11B's Memento", "Resistance Camp"),
    "q440": ("Treasure Hunt at the Castle", "Forest Kingdom"),
    "q500": ("The Wandering Couple", "Pascal's Village"),
    "q520": ("Data on the Old World", "City Ruins"),
    "q532": ("Culinary Researcher", "Resistance Camp"),
    "q540": ("YoRHa Betrayers", "City Ruins"),
    "q550": ("Reconnaissance Squad", "Resistance Camp"),
    "q560": ("Devola's Request", "Resistance Camp"),
    "q561": ("Popola's Errand", "Resistance Camp"),
    "q562": ("The Twins' Request", "Resistance Camp"),
    "q590": ("Heritage of the Past", "Desert Zone"),
    "q640": ("Retrieve the Confidential Intel", "Desert Zone"),
    "q650": ("Sorting Trouble", "Resistance Camp"),
    "q651": ("Sorting Trouble 2", "Resistance Camp"),
    "q652": ("Sorting Trouble 3", "Resistance Camp"),
    "q660": ("Stamp Collecting", "Amusement Park"),
    "q680": ("Parade Escort", "Amusement Park"),
    "q720": ("Gathering Keepsakes", "Resistance Camp"),
    "q770": ("The Weapon Dealer's Request", "Resistance Camp"),
    "q800": ("The Recluse", "City Ruins"),
    "q801": ("The Recluse Stays Home", "City Ruins"),
    "q802": ("The Permanent Recluse", "City Ruins"),
    "q900": ("Emil's Determination", "Emil's Residence"),
    "q920": ("A Steal of a Deal", "City Ruins"),
}

# Quests seen as DONE/FIN in a real save (the user's playthrough + a 100% save): completable in a normal
# playthrough and detected by the bridge. Only these may hold progression items (option
# quest_progression), since any quest can turn to BREAK as the story advances.
# Not seen completed anywhere yet: q360, q401, q403, q920.
VERIFIED_QUESTS = {
    "q020", "q031", "q032", "q040", "q070", "q071", "q072", "q085", "q090", "q091", "q092", "q095",
    "q100", "q101", "q102", "q103", "q104", "q110", "q120", "q121", "q122", "q123", "q130", "q140",
    "q150", "q160", "q162", "q170", "q171", "q180", "q181", "q210", "q220", "q221", "q222", "q240",
    "q250", "q290", "q291", "q292", "q300", "q330", "q340", "q400", "q410", "q440", "q500", "q520",
    "q532", "q540", "q550", "q560", "q561", "q562", "q590", "q640", "q650", "q651", "q652", "q660",
    "q680", "q720", "q770", "q800", "q801", "q802", "q900",
}
assert VERIFIED_QUESTS <= set(QUEST_TABLE)


def quest_location_name(qid: str) -> str:
    return f"Quest: {QUEST_TABLE[qid][0]}"


def quest_location_offset(qid: str) -> int:
    return QUEST_LOCATION_OFFSET + int(qid[1:], 16)
