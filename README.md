# NieR: Automata Archipelago

An [Archipelago](https://archipelago.gg) multiworld randomizer for **NieR: Automata** (Steam version, Windows).

> **Pre-beta (0.2.0).** It works from start to Ending A in our tests, but expect bugs. Back up your saves
> and please report anything odd (see [Feedback](#feedback)).
>
> **NieR: Automata got a Steam update in November 2026: versions 0.1.x crash the game with it.** Update to
> 0.2.0 (see [Updating](#updating)).

2B starts with no weapons and no HUD chips. Weapons, pod programs, HUD chips, chip storage, characters and
more are shuffled into the multiworld, and the things you do in the game (story, bosses, quests, endings,
fishing, shops…) send items to the other players.

## Contents

- [What you need](#what-you-need)
- [Installing](#installing)
- [Updating](#updating)
- [Playing](#playing)
- [How the randomizer works](#how-the-randomizer-works)
- [Options](#options)
- [Known issues](#known-issues)
- [Uninstalling](#uninstalling)
- [Building from source](#building-from-source)
- [AI disclosure](#ai-disclosure)
- [Credits](#credits)
- [License](#license)

## What you need

- **NieR: Automata on Steam**: the 2021 exe and the update of November 2026 are both supported. Other versions
  (Game Pass / Microsoft Store, or a future Steam update) are not: the hook then shows a warning and stays off
  instead of crashing the game.
- **Windows**.
- **[Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases)** to generate the multiworld
  (only the person who generates needs it).
- No other mod that installs a `dinput8.dll` in the game folder (they would replace each other).

## Installing

Download `NieR-Automata-Archipelago-<version>.zip` from the
[Releases](../../releases) page and unzip it.

1. **Back up your saves**: copy `Documents\My Games\NieR_Automata` somewhere safe.
2. **Install the game files.** In Steam, right-click NieR: Automata → *Manage* → *Browse local files*.
   Copy everything from the zip's `NieRAutomata folder` into that folder (next to `NieRAutomata.exe`):
   - `dinput8.dll`: the game hook
   - `nier_archipelago_bridge.py`: links the game to the Archipelago server
   - `Lancer_Pont_Archipelago.bat`: starts the bridge
   - `python`: the Python that runs the bridge, nothing to install
   - `ap_definitions.json`, `known_chests.json`: data used by the bridge
3. **Install the world** (the person who generates the multiworld, and anyone using the
   [tracker](#tracker-optional)): double-click
   `nierautomata.apworld`, or copy it into Archipelago's `custom_worlds` folder.
4. **Make your settings file**: edit `NieR Automata.yaml` (your slot name, your goal…) and give it to
   the person who generates the multiworld, like any other Archipelago game.

## Updating

From 0.1.0 or 0.1.1 (required since the game's Steam update of November 2026):

1. Close the game and the bridge window.
2. Copy everything from the new zip's `NieRAutomata folder` into the game folder and **replace** the old files
   (`dinput8.dll` is the one that matters: the old one crashes the updated game).
3. The person who generates: install the new `nierautomata.apworld` the same way as before, and delete any
   older `nierautomata.apworld` left in Archipelago's `lib\worlds` or `custom_worlds` folder (two copies make
   Archipelago print "already registered" errors and may load the old one).
4. Your saves and the games you already started keep working: nothing to do on that side.
5. Old settings files still work (the goal stays `ending_a`). The new options are in the zip's
   `NieR Automata.yaml`.

When the hook starts, its console shows `Game build: Steam 2026` (or `Steam 2021`). If the game gets another
update the hook doesn't know yet, it shows a warning and stays off instead of crashing the game.

## Playing

1. Start NieR: Automata. A console window titled *Archipelago Hook* opens next to the game: that's normal,
   leave it open.
2. Double-click `Lancer_Pont_Archipelago.bat` in the game folder. Leave this window open while you play.
3. In game, press **F1** (or **Insert**) to open the Archipelago menu. Enter the server (`host:port`), your
   slot name and the password if there is one, then click *SE CONNECTER A ARCHIPELAGO*.
   You can also connect from the bridge window: `ap_connect archipelago.gg:38281 YourName [password]`.
4. **Start a new game on an empty save slot.** Received items show up as notifications.
   A save already played for more than 2 hours when you first connect (a finished game, for example) keeps
   working, but what it already holds (endings, quests, access points, levels…) doesn't count for the seed.
   Otherwise a finished save would send Ending E and complete your goal at once. If you really started that
   save for this seed and played it offline first, type `trust_save <slot 1-3>` in the bridge window.

| Key | What it does |
|---|---|
| F1 / Insert | Archipelago menu: connection, item and check log, settings |
| F2 | Shop hints: what each shop location contains |

Keep the bridge running while you play. If the Archipelago server can't be reached, your progress is
kept and the checks are sent when you reconnect.

### Tracker (optional)

To see which checks are in logic, use [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases):

1. Install `tracker.apworld` (from the Universal Tracker releases) and `nierautomata.apworld`
   (from this mod's zip) in Archipelago: double-click each file.
2. In the Archipelago Launcher, open *Universal Tracker* and connect with the same server and slot name
   as in game. No YAML needed.

## How the randomizer works

- **Starting kit**: 2B has no weapon and no HUD chip except the OS chip. They come from the multiworld.
  The prologue's Laser pod program is still a check, but it isn't given to you.
- **Characters**: route B needs the **9S** item, routes C and D need the **A2** item. Entering a route you
  haven't unlocked sends you back to the title screen.
- **Chapter Select** is available from the title screen from the start, but it only lists the chapters you
  have already reached in this seed. Picking 9S there starts the chapter with 2B until you receive 9S.
  Use it to go back to anything you missed.
- **Shops**: buying a weapon or a chip storage upgrade from a shop is a check: you get a multiworld item
  instead of the shop item.
- **World chips**: plug-in chips found on the ground or in chests are disabled; chips come from the
  multiworld.
- **Fishing**: the first catch of each fish species is a check. Fish are also in the item pool.
- **Chapter shuffle** (option): the 10 chapters of routes A/B are items. You start with one random chapter:
  start it from the title screen's **Chapter Select**. The Chapter Select lists the first part of each chapter you
  received (and the parts you already reached); when the story runs into a chapter you haven't received, you are
  sent back to the title screen. Each area of the world counts as reachable only with a chapter whose story goes
  there. Starting a chapter presets the story before it (side quests done, access points on), so with this
  option side quests and access points only hold filler.
- **DeathLink** (option): when you die, the other DeathLink players die, and the other way around.

### Checks (up to 259 locations)

Your `goal` decides which checks are in the seed: only the ones you can do before that ending.

| Goal | Routes played | Checks | Characters in the pool |
|---|---|---|---|
| `ending_a` | A | 211 | none |
| `ending_b` | A, B | 216 | 9S |
| `ending_c` | A, B, C (choose A2) | 256 | 9S, A2 |
| `ending_d` | A, B, C/D (choose 9S) | 257 | 9S, A2 |
| `ending_e` | A, B, C, D | 259 | 9S, A2 |
| `prologue_engels` | test goal | 259 | 9S, A2 |

Side quests that only open in a later route (route B for 9S-only quests, routes C/D for A2 quests) are
counted in that route. A few quests whose route isn't confirmed yet are counted in route C to be safe.


| Kind | What sends it |
|---|---|
| Story | Story milestones and story bosses, routes A to D |
| Endings | Endings A to Z |
| Side quests | Finishing each of the 71 side quests |
| Weapons | Weapons from chests, quests and shops |
| Pod programs | Pod programs |
| Access points | Activating each access point |
| Storage, modules | Chip storage upgrades bought in shops, modules |
| Levels | Reaching level 5, 10, 15… 50 |
| Fishing | First catch of each of the 41 species |

Some locations are not verified in game yet: they still exist, but they only hold filler items so they can
never block anyone.

## Options

See `NieR Automata.yaml` for an example.

| Option | Values | What it does |
|---|---|---|
| `goal` | `ending_a` (default), `ending_b`, `ending_c`, `ending_d`, `ending_e`, `prologue_engels` | The ending that completes your game. Only the checks you can do before it are in the seed (see below) |
| `chapter_shuffle` | `true` / `false` | Chapters are items, played in a random order (see below). Goal `ending_a` or `ending_b` only for now |
| `quest_progression` | `true` / `false` | Let side quests hold progression items (only quests verified in a real save) |
| `death_link` | `true` / `false` | DeathLink |

## Known issues

- Pre-beta: the route C and D story milestones and several rare endings are not tested in a real run yet.
- The in-game overlay and notifications are in French for now.
- Some leveled plug-in chips may show a wrong name in notifications.
- If a check doesn't fire, the host can send it from the server console with `/send_location`.
- Sending you back to the title screen when you enter a locked route is not tested in a real run yet.
- Chapter shuffle is new and not tested in a real run yet: starting a chapter from the Chapter Select on a brand
  new save slot, and the chapter lock, still need to be checked in game. Routes C/D (chapters 11-17) come later.

## Uninstalling

Delete `dinput8.dll` from the game folder (`uninstall.ps1` does it for the default Steam path). The other
files can be deleted too.

## Building from source

Requirements: Visual Studio with the C++ build tools, Python 3. When run from the sources,
`Lancer_Pont_Archipelago.bat` uses your installed Python and installs `websockets` and `certifi`.
`tools/make_release.py` downloads the embeddable Python from python.org and bundles it in the zip.

```
git clone --recursive <repo url>      (or: git submodule update --init)
python download_imgui.py
build.bat
python tools/make_release.py 0.2.0-prebeta
```

`build.bat` calls `vcvars64.bat` from Visual Studio 2026 Community; adjust the path if yours differs.
`deploy.ps1` builds and copies the files to the default Steam folder.

After a game update, the hook's fixed addresses move. `tools/port_offsets.py <old exe> <new exe>` finds them in
the new build (`tools/port_verify.py` checks the small functions and return addresses); add the new values to
`ApplyGameBuildOffsets()` in `dllmain.cpp`, keyed by the exe's PE timestamp.

| Part | What it does |
|---|---|
| `dllmain.cpp`, `ArchipelagoUI.cpp` → `dinput8.dll` | Game hook: detects checks, gives received items, in-game overlay |
| `nier_archipelago_bridge.py` | Links the hook (local TCP) to the Archipelago server, watches the save files |
| `apworld/nierautomata/` | Archipelago world: items, locations, logic, options |
| `tools/` | Release script and research helpers |

## Feedback

Report bugs on the [Issues](../../issues) page, or on Discord. Please include `archipelago_events.log`
(in the game's `data` folder) and the bridge window's output.

## AI disclosure

This project was made with the help of AI, mainly [Claude](https://claude.ai) (Anthropic) through Claude Code.
To be clear about what that means:

- **Reverse engineering:** AI helped decompile and recompile the game with REA, to find the functions and
  memory addresses the hook relies on.
- **Code:** AI helped write and debug parts of the code: the DLL hook, the Python bridge, the apworld
  and the release tools. Commits made with AI help are marked `Co-Authored-By: Claude`.
- **Docs:** AI helped write this README.

I tested everything in game and I maintain the project myself: I understand how the code works and I
handle bug reports and support. No AI-generated art, audio or other game assets are included.
If you have questions about any part of it, ask on Discord or open an issue.

## Credits

- Item ids and save layout: [NieREdit](https://codeberg.org/mxNieR/NieREdit), NieRHook
- Quest names and story phases: [YoRHa Protocol](https://github.com/Vluurie/yp_launcher) (Vluurie)
- [MinHook](https://github.com/TsudaKageyu/minhook), [Dear ImGui](https://github.com/ocornut/imgui)

## License

[MIT](LICENSE). MinHook and Dear ImGui keep their own licenses.
