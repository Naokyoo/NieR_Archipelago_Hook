#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <iostream>
#include <vector>
#include <set>
#include <map>
#include <cstdint>
#include <string>
#include <sstream>
#include <intrin.h>
#include <share.h>
#include "minhook/include/MinHook.h"
#include "ArchipelagoUI.h"

#pragma comment(lib, "user32.lib")
#pragma comment(lib, "ws2_32.lib")

// -------------------------------------------------------------
// DirectInput 8 Proxying
// -------------------------------------------------------------
typedef HRESULT(WINAPI* DirectInput8Create_t)(
    HINSTANCE hinst,
    DWORD dwVersion,
    REFIID riidltf,
    LPVOID* ppvOut,
    LPUNKNOWN punkOuter
);

static HMODULE g_hRealDInput8 = nullptr;
static DirectInput8Create_t g_pfnDirectInput8Create = nullptr;

static void LoadRealDInput8()
{
    if (g_hRealDInput8) return;

    wchar_t systemPath[MAX_PATH];
    GetSystemDirectoryW(systemPath, MAX_PATH);
    wcscat_s(systemPath, L"\\dinput8.dll");

    g_hRealDInput8 = LoadLibraryW(systemPath);
    if (g_hRealDInput8)
    {
        g_pfnDirectInput8Create = (DirectInput8Create_t)GetProcAddress(g_hRealDInput8, "DirectInput8Create");
    }
}

extern "C" __declspec(dllexport) HRESULT WINAPI DirectInput8Create(
    HINSTANCE hinst,
    DWORD dwVersion,
    REFIID riidltf,
    LPVOID* ppvOut,
    LPUNKNOWN punkOuter
)
{
    if (!g_pfnDirectInput8Create)
    {
        LoadRealDInput8();
    }

    if (g_pfnDirectInput8Create)
    {
        return g_pfnDirectInput8Create(hinst, dwVersion, riidltf, ppvOut, punkOuter);
    }

    return E_FAIL;
}

// -------------------------------------------------------------
// Pattern Scanner (IDA-style Signature Matcher)
// -------------------------------------------------------------
static uintptr_t FindPattern(const char* pattern)
{
    static uintptr_t moduleBase = 0;
    static size_t moduleSize = 0;
    if (!moduleBase)
    {
        moduleBase = (uintptr_t)GetModuleHandle(NULL);
        PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)moduleBase;
        PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)(moduleBase + dos->e_lfanew);
        moduleSize = nt->OptionalHeader.SizeOfImage;
    }

    std::vector<int> bytes;
    const char* cur = pattern;
    while (*cur)
    {
        if (*cur == ' ') { cur++; continue; }
        if (*cur == '?')
        {
            bytes.push_back(-1);
            cur++;
            if (*cur == '?') cur++;
        }
        else
        {
            bytes.push_back((int)strtoul(cur, (char**)&cur, 16));
        }
    }

    size_t len = bytes.size();
    unsigned char* scan = (unsigned char*)moduleBase;
    for (size_t i = 0; i < moduleSize - len; ++i)
    {
        bool match = true;
        for (size_t j = 0; j < len; ++j)
        {
            if (bytes[j] != -1 && scan[i + j] != (unsigned char)bytes[j])
            {
                match = false;
                break;
            }
        }
        if (match) return (uintptr_t)&scan[i];
    }
    return 0;
}

static uintptr_t FindPatternPtr(const char* pattern, int offset = 3)
{
    uintptr_t address = FindPattern(pattern);
    if (!address) return 0;
    int32_t relOffset = *(int32_t*)(address + offset);
    return address + offset + 4 + relOffset;
}

// -------------------------------------------------------------
// NieR: Automata Game Functions & Structures
// -------------------------------------------------------------
typedef bool (*CItemManager_AddItemFn)(void* pThis, int item_id, int iQuantity);

static int32_t* g_piMoney = nullptr;
static int32_t* g_piExperience = nullptr;
static void* g_pItemManager = nullptr;
static void* g_pInventoryManager = nullptr;
static CItemManager_AddItemFn ItemManager_AddItem = nullptr;
static CItemManager_AddItemFn oItemManager_AddItem = nullptr;

// Archipelago State
bool g_bInterceptMode = true;
static bool g_bIsGivingArchipelagoItem = false;
static int g_totalInterceptedChecks = 0;

// Bridge Networking (Port 52140)
static SOCKET g_serverSocket = INVALID_SOCKET;
static SOCKET g_clientSocket = INVALID_SOCKET;
static CRITICAL_SECTION g_csSocket;
static bool g_bBridgeConnected = false;
static bool g_bPendingConnect = false;
static char g_szPendingServer[128] = "";
static char g_szPendingSlot[64] = "";
static char g_szPendingPassword[64] = "";

bool IsBridgeConnected()
{
    return g_bBridgeConnected;
}

void LaunchPythonBridge()
{
    char moduleDir[MAX_PATH];
    GetModuleFileNameA(GetModuleHandleA("dinput8.dll"), moduleDir, MAX_PATH);
    char* lastSlash = strrchr(moduleDir, '\\');
    if (lastSlash) *(lastSlash + 1) = '\0';

    char scriptPath[MAX_PATH];
    sprintf_s(scriptPath, "%snier_archipelago_bridge.py", moduleDir);

    char cmdLine[MAX_PATH * 2];
    sprintf_s(cmdLine, "cmd.exe /c start /b \"\" \"C:\\Python314\\python.exe\" \"%s\"", scriptPath);

    STARTUPINFOA si{};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    if (CreateProcessA(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, moduleDir, &si, &pi))
    {
        if (pi.hProcess) CloseHandle(pi.hProcess);
        if (pi.hThread) CloseHandle(pi.hThread);
        std::cout << "[+] [Bridge Server] Spawned local Python bridge: " << scriptPath << "\n";
    }
    else
    {
        // Fallback with system python
        sprintf_s(cmdLine, "cmd.exe /c start /b python \"%s\"", scriptPath);
        CreateProcessA(NULL, cmdLine, NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, moduleDir, &si, &pi);
        if (pi.hProcess) CloseHandle(pi.hProcess);
        if (pi.hThread) CloseHandle(pi.hThread);
    }
}

void SendBridgeMessage(const char* msg)
{
    EnterCriticalSection(&g_csSocket);
    if (g_clientSocket != INVALID_SOCKET)
    {
        send(g_clientSocket, msg, (int)strlen(msg), 0);
        send(g_clientSocket, "\n", 1, 0);
    }
    LeaveCriticalSection(&g_csSocket);
}

void QueueAPConnect(const char* server, const char* slot, const char* password)
{
    EnterCriticalSection(&g_csSocket);
    strcpy_s(g_szPendingServer, server);
    strcpy_s(g_szPendingSlot, slot);
    strcpy_s(g_szPendingPassword, password);
    g_bPendingConnect = true;

    if (g_clientSocket != INVALID_SOCKET)
    {
        char cmd[512];
        sprintf_s(cmd, "{\"cmd\":\"ap_connect_request\",\"server\":\"%s\",\"slot\":\"%s\",\"password\":\"%s\"}",
                  g_szPendingServer, g_szPendingSlot, g_szPendingPassword);
        send(g_clientSocket, cmd, (int)strlen(cmd), 0);
        send(g_clientSocket, "\n", 1, 0);
        g_bPendingConnect = false;
    }
    LeaveCriticalSection(&g_csSocket);
}

#pragma pack(push, 1)
struct NieRItemSlot
{
    uint32_t id;
    uint32_t flags; // 0x00070000 for valid inventory item
    uint32_t quantity;
};

struct NieRWeaponSlot
{
    uint32_t id;
    uint32_t level;
    uint32_t unk1;
    uint32_t unk2;
    uint32_t unk3;
};

struct NieRPodProgramSlot
{
    uint32_t one;         // 1 for a used or empty slot
    uint32_t id;          // Program id (2001..2024), 0xFFFFFFFF = empty
};

struct NieRChipSlot
{
    uint32_t base_code;   // Per chip type code (+ level for leveled chips), NOT a unique id
    uint32_t item_id;     // Item ID (3000..3400)
    uint32_t kind;        // Chip category
    uint32_t level;       // Level (0..8)
    uint32_t cost;        // Storage cost (diamond mark min size)
    uint32_t equipped_A;  // Slot in set A (or 0xFFFFFFFF)
    uint32_t equipped_B;  // Slot in set B (or 0xFFFFFFFF)
    uint32_t equipped_C;  // Slot in set C (or 0xFFFFFFFF)
    uint32_t unk1;        // 0xFFFFFFFF
    uint32_t unk2;        // 0xFFFFFFFF
    uint32_t unk3;        // 0xFFFFFFFF
    uint32_t unk4;        // 0
};
#pragma pack(pop)

// Active Save Data in memory starts at moduleBase + 0x145BF58
static const uintptr_t SAVE_DATA_BASE_RVA         = 0x145BF58;
// Tables below: RAM offset = SlotData_*.dat file offset - 4 (NieRHook sheet + NieREdit, checked on a real save)
static const uintptr_t MONEY_RVA                  = 0x148C4C0; // saveBase + 0x30568 (file 0x3056C)
static const uintptr_t INVENTORY_TABLE_START      = 0x148C4C4; // saveBase + 0x3056C (file 0x30570), 256 x 12 bytes
static const uintptr_t INVENTORY_TABLE_END        = INVENTORY_TABLE_START + 256 * 12;
static const uintptr_t WEAPONS_OFFSET_START       = 0x148DCC4; // saveBase + 0x31D6C (file 0x31D70), 80 x 20 bytes
static const uintptr_t WEAPONS_OFFSET_END         = WEAPONS_OFFSET_START + 80 * 20;
static const uintptr_t POD_PROGRAMS_OFFSET_START  = 0x148E304; // saveBase + 0x323AC (file 0x323B0), 32 x 8 bytes
static const uintptr_t POD_PROGRAMS_OFFSET_END    = POD_PROGRAMS_OFFSET_START + 32 * 8;
static const uintptr_t CHIP_TABLE_OFFSET_START    = 0x148E410; // Exact RVA (saveBase + 0x324B8), verified with dump_chips.py: slot starts at base_code
static const uintptr_t CHIP_TABLE_OFFSET_END      = CHIP_TABLE_OFFSET_START + 300 * 48; // 300 chip slots, other save data follows

bool g_bBlockGroundLoot   = true;  // Blocks vanilla ground pickups & mob drops from filling inventory
bool g_bEnforceBareFists  = true;  // Removes starter weapons until granted by Archipelago
bool g_bEnforceBareHUD    = true;  // Strips starter HUD chips until granted by Archipelago
bool g_bProgressiveChipStorage = true; // "Storage +8" purchases send checks, capacity comes from AP items

// Number of "Storage +8" upgrades bought (file offset 0x324B8 -> RAM saveBase + 0x324B4).
// The chip capacity is derived from this counter only.
static const uintptr_t STORAGE_UPGRADES_SAVE_OFFSET = 0x324B4;
static const int       MAX_STORAGE_UPGRADES         = 6;
static const int       PROGRESSIVE_CHIP_CAPACITY_ID = 4100;
static int g_targetStorageUpgrades = -1; // "Progressive Chip Capacity" received, -1 = not known yet

// Continuous Reconciliation State (Like Luigi's Mansion MultiWorld)
struct TargetWeapon
{
    int id;
    int level;
    std::string name;
    bool notificationShown;
    bool granted;
};

struct TargetPodProgram
{
    int id;
    std::string name;
    bool notificationShown;
    bool granted;
};

struct TargetItem
{
    int id;
    int targetQuantity;
    std::string name;
    bool notificationShown;
    bool granted;
    int totalCount; // All-time received quantity
};

static CRITICAL_SECTION g_csReconciliation;
static std::map<int, TargetWeapon> g_targetWeapons;
static std::map<int, TargetPodProgram> g_targetPodPrograms;
// Set by the bridge ("items_synced") once every item already received from Archipelago was handed to the hook:
// before that, an Archipelago weapon in the save would look like a weapon obtained outside Archipelago.
static volatile bool g_bArchipelagoItemsSynced = false;
static std::map<int, TargetItem> g_targetItems;
static std::set<uint32_t> g_knownPlayerWeapons;
static std::set<int> s_sentStartingChecks;
static int g_targetGoldTotal = 0;
static int g_creditedGoldTotal = 0;
static bool s_buzzsawSent = false;
static bool s_engelsSent = false;
static bool s_wasInPrologue = false;
static std::map<int, int> s_regrantAttempts;

// Every consumable / material / gold grant is stamped with the in-game playtime (seconds).
// When the game reloads its last save (death, ending...) everything granted AFTER that save
// was written is wiped by the engine, so it has to be granted again (see ReplayLostGrants).
// itemId == 0 means gold.
struct GrantRecord { int itemId; int qty; uint32_t playtime; };
static std::vector<GrantRecord> g_grantLog;

// Forward declarations (defined further below)
bool GivePlayerItemDirect(int item_id, int count);
bool GivePlayerWeaponDirect(int weapon_id, int level);
bool GivePlayerPodProgramDirect(int program_id);
bool GivePlayerChipDirect(int item_id);
bool IsPlayerInGame();
static void LogEventToFile(const char* fmt, ...);
int GetPlayerItemCount(int item_id);
int GetPlayerChipCount(int item_id);
bool PlayerOwnsWeapon(int wId);
static bool IsWeaponId(int id);
static bool IsPodProgramId(int id);
static const int HACKING_MODULE_ID = 2100; // logic-only AP item
bool PlayerOwnsPodProgram(int pId);

// True only once hkItemManager_AddItem has seen the REAL player inventory 'this' pointer
// coming from the engine. The pattern-scanned pointer is NOT trusted for granting: calling the
// engine with a wrong 'this' silently loses the item while we would mark it as granted.
static bool g_bInventoryCaptured = false;

// Delivery acknowledgement (bridge persists its 'received index' only after we confirm).
static volatile LONG g_iCommitMarker = -1;
static volatile LONG g_bCommitDirty = 0;

// Grants through the engine when its inventory pointer is trusted, otherwise (or on failure)
// writes straight into the in-RAM save structure.
static bool GrantItemSafe(int itemId, int qty)
{
    // Plug-in Chips (3000..3400) live in the dedicated 48-byte chip table, not the consumables table
    if (itemId >= 3000 && itemId < 3400)
    {
        bool allOk = true;
        for (int q = 0; q < qty; ++q)
        {
            if (!GivePlayerChipDirect(itemId)) allOk = false;
        }
        return allOk;
    }

    if (g_bInventoryCaptured && g_pInventoryManager && oItemManager_AddItem)
    {
        __try
        {
            g_bIsGivingArchipelagoItem = true;
            oItemManager_AddItem(g_pInventoryManager, itemId, qty);
            g_bIsGivingArchipelagoItem = false;
            return true;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            g_bIsGivingArchipelagoItem = false;
        }
    }
    return GivePlayerItemDirect(itemId, qty);
}

static bool GrantWeaponSafe(int wId, int level)
{
    if (g_bInventoryCaptured && g_pInventoryManager && oItemManager_AddItem)
    {
        __try
        {
            g_bIsGivingArchipelagoItem = true;
            oItemManager_AddItem(g_pInventoryManager, wId, 1);
            g_bIsGivingArchipelagoItem = false;
            return true;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            g_bIsGivingArchipelagoItem = false;
        }
    }
    return GivePlayerWeaponDirect(wId, level);
}

static bool GrantPodProgramSafe(int pId)
{
    if (g_bInventoryCaptured && g_pInventoryManager && oItemManager_AddItem)
    {
        __try
        {
            g_bIsGivingArchipelagoItem = true;
            oItemManager_AddItem(g_pInventoryManager, pId, 1);
            g_bIsGivingArchipelagoItem = false;
            return true;
        }
        __except (EXCEPTION_EXECUTE_HANDLER)
        {
            g_bIsGivingArchipelagoItem = false;
        }
    }
    return GivePlayerPodProgramDirect(pId);
}

static bool HasPendingArchipelagoGrants()
{
    bool pending = false;
    EnterCriticalSection(&g_csReconciliation);
    for (auto& p : g_targetPodPrograms) if (!p.second.granted) pending = true;
    for (auto& p : g_targetWeapons) if (!p.second.granted) pending = true;
    for (auto& p : g_targetItems) if (!p.second.granted && p.second.targetQuantity > 0) pending = true;
    if (g_targetGoldTotal > g_creditedGoldTotal) pending = true;
    LeaveCriticalSection(&g_csReconciliation);
    return pending;
}

// Playtime (seconds) of the save currently loaded in RAM (saveBase + 0x20, file offset 0x24).
static uint32_t GetCurrentPlaytime()
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    uint32_t pt = 0;
    __try
    {
        uint32_t* p = (uint32_t*)(moduleBase + SAVE_DATA_BASE_RVA + 0x20);
        if (!IsBadReadPtr(p, sizeof(uint32_t))) pt = *p;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    return pt;
}

static void LogGrant(int itemId, int qty)
{
    g_grantLog.push_back({ itemId, qty, GetCurrentPlaytime() });
    if (g_grantLog.size() > 500) g_grantLog.erase(g_grantLog.begin());
}

void FlushPendingArchipelagoGrants()
{
    // Never touch the save structure while no save is loaded (it would be overwritten by the load).
    if (!IsPlayerInGame()) return;

    EnterCriticalSection(&g_csReconciliation);

    // 1. Pod Programs (2001..2024)
    for (auto& pair : g_targetPodPrograms)
    {
        if (!pair.second.granted)
        {
            int pId = pair.first;
            if (GrantPodProgramSafe(pId))
            {
                pair.second.granted = true;
                std::cout << "[+] [AP Grant] Pod Program: " << pair.second.name << " (ID " << pId << ")\n";
            }
            else
            {
                std::cerr << "[-] [AP Grant] Failed to grant Pod Program ID " << pId << " (will retry)\n";
            }
        }
    }

    // 2. Weapons (real in-game ids, see GetWeaponName)
    for (auto& pair : g_targetWeapons)
    {
        if (!pair.second.granted)
        {
            int wId = pair.first;
            if (GrantWeaponSafe(wId, pair.second.level))
            {
                pair.second.granted = true;
                std::cout << "[+] [AP Grant] Weapon: " << pair.second.name << " (ID " << wId << ")\n";
            }
            else
            {
                std::cerr << "[-] [AP Grant] Failed to grant Weapon ID " << wId << " (will retry)\n";
            }
        }
    }

    // 3. Items (Materials, Consumables, Chips). targetQuantity is a PENDING amount (additive).
    for (auto& pair : g_targetItems)
    {
        if (!pair.second.granted && pair.second.targetQuantity > 0)
        {
            int itemId = pair.first;
            int qty = pair.second.targetQuantity;
            if (GrantItemSafe(itemId, qty))
            {
                pair.second.granted = true;
                pair.second.targetQuantity = 0;
                if (!(itemId >= 3000 && itemId < 3400)) LogGrant(itemId, qty); // chips are re-verified separately
                std::cout << "[+] [AP Grant] Item: " << pair.second.name << " (ID " << itemId << " x" << qty << ")\n";
            }
            else
            {
                std::cerr << "[-] [AP Grant] Failed to grant Item ID " << itemId << " (will retry)\n";
            }
        }
    }

    // 4. Gold (4001..4004)
    if (g_targetGoldTotal > g_creditedGoldTotal)
    {
        int delta = g_targetGoldTotal - g_creditedGoldTotal;
        uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
        int32_t* pMoney = (int32_t*)(moduleBase + MONEY_RVA);
        if (pMoney && !IsBadWritePtr(pMoney, sizeof(int32_t)))
        {
            *pMoney += delta;
            if (*pMoney > 9999999) *pMoney = 9999999;
            g_creditedGoldTotal = g_targetGoldTotal;
            LogGrant(0, delta);
            std::cout << "[+] [AP Grant] Gold: +" << delta << " G (Total: " << *pMoney << " G)\n";
        }
    }

    LeaveCriticalSection(&g_csReconciliation);
}

// includeConsumables=false: only permanent things (weapons, pod programs, chips) are checked.
// Consumables / materials / gold are NEVER topped up on a plain respawn, otherwise whatever the
// player legitimately used or spent would be given back again.
void ForceResyncAllArchipelagoGrants(bool includeConsumables)
{
    if (!IsPlayerInGame()) return;

    EnterCriticalSection(&g_csReconciliation);
    s_regrantAttempts.clear();

    // 1. Weapons: mark ungranted if player doesn't have it
    for (auto& pair : g_targetWeapons)
    {
        if (!PlayerOwnsWeapon(pair.first))
        {
            pair.second.granted = false;
        }
    }

    // 2. Pod Programs: mark ungranted if player doesn't have it
    for (auto& pair : g_targetPodPrograms)
    {
        if (!PlayerOwnsPodProgram(pair.first))
        {
            pair.second.granted = false;
        }
    }

    // 3. Items & Chips: calculate missing delta based on totalCount and current in-game inventory
    for (auto& pair : g_targetItems)
    {
        int itemId = pair.first;
        bool isChip = (itemId >= 3000 && itemId < 3400);
        if (!isChip && !includeConsumables) continue;

        int total = pair.second.totalCount;
        if (total <= 0) total = (pair.second.targetQuantity > 0) ? pair.second.targetQuantity : 1;

        int curInGame = 0;
        if (itemId >= 3000 && itemId < 3400)
        {
            curInGame = GetPlayerChipCount(itemId);
        }
        else
        {
            curInGame = GetPlayerItemCount(itemId);
        }

        int needed = total - curInGame;
        if (needed > 0)
        {
            pair.second.targetQuantity = needed;
            pair.second.granted = false;
        }
        else
        {
            pair.second.targetQuantity = 0;
            pair.second.granted = true;
        }
    }

    // 4. Gold: if current money in RAM is less than target total, top it up
    if (includeConsumables && g_targetGoldTotal > 0)
    {
        uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
        int32_t* pMoney = (int32_t*)(moduleBase + MONEY_RVA);
        if (pMoney && !IsBadReadPtr(pMoney, sizeof(int32_t)))
        {
            if (*pMoney < g_targetGoldTotal)
            {
                g_creditedGoldTotal = *pMoney;
            }
        }
    }

    LeaveCriticalSection(&g_csReconciliation);
    FlushPendingArchipelagoGrants();
}

void ResetAllRunState(bool reGrantAllItems)
{
    EnterCriticalSection(&g_csReconciliation);
    s_sentStartingChecks.clear();
    g_totalInterceptedChecks = 0;
    InterlockedExchange(&g_bCommitDirty, 0);
    InterlockedExchange(&g_iCommitMarker, -1);
    s_wasInPrologue = false;
    s_buzzsawSent = false;
    s_engelsSent = false;
    s_regrantAttempts.clear();

    for (auto& pair : g_targetWeapons) pair.second.granted = false;
    for (auto& pair : g_targetPodPrograms) pair.second.granted = false;
    for (auto& pair : g_targetItems)
    {
        pair.second.granted = false;
        int qty = (pair.second.totalCount > 0) ? pair.second.totalCount : (pair.second.targetQuantity > 0 ? pair.second.targetQuantity : 1);
        pair.second.targetQuantity = qty;
    }
    g_creditedGoldTotal = 0;
    g_grantLog.clear();
    LeaveCriticalSection(&g_csReconciliation);

    std::cout << "\n🔄 [RESET RUN] Run state & starting check caches reset. Ready for clean new game.\n";
    ArchipelagoUI::ClearLog();
    if (reGrantAllItems)
    {
        FlushPendingArchipelagoGrants();
    }
}

// totalGold / creditedGold: cumulative gold received / gold already delivered in the save (bridge side).
// totalCountParam: cumulative amount of this item received so far (bridge side), makes re-sends idempotent.
// knownOnly: the bridge only tells us an item was ALREADY delivered in a previous run (nothing to grant).
void RegisterReceivedArchipelagoItem(int itemId, int targetQty, const std::string& name, const std::string& sender, bool showNotification = true, int totalGold = 0, int totalCountParam = 0, bool knownOnly = false, int creditedGold = 0)
{
    EnterCriticalSection(&g_csReconciliation);

    // 0. Progressive Chip Capacity (4100): applied by EnforceProgressiveChipStorage()
    if (itemId == PROGRESSIVE_CHIP_CAPACITY_ID)
    {
        int base = (g_targetStorageUpgrades < 0) ? 0 : g_targetStorageUpgrades;
        int total = (totalCountParam > 0) ? totalCountParam : (knownOnly ? base : base + targetQty);
        if (total < base) total = base;
        if (total > MAX_STORAGE_UPGRADES) total = MAX_STORAGE_UPGRADES;
        g_targetStorageUpgrades = total;
    }
    // 1. Gold Bundles (4001..4004)
    else if (itemId >= 4001 && itemId <= 4004)
    {
        if (totalGold > 0)
        {
            if (totalGold > g_targetGoldTotal) g_targetGoldTotal = totalGold;
            if (creditedGold > g_creditedGoldTotal) g_creditedGoldTotal = creditedGold;
        }
        else if (!knownOnly)
        {
            int goldAmount = 1000;
            if (itemId == 4002) goldAmount = 2500;
            else if (itemId == 4003) goldAmount = 5000;
            else if (itemId == 4004) goldAmount = 10000;
            g_targetGoldTotal += (goldAmount * targetQty);
        }
    }
    // 1b. Hacking Module (2100): logic-only AP item, nothing to give in game
    else if (itemId == HACKING_MODULE_ID)
    {
    }
    // 2. Pod Programs (2001..2024)
    else if (IsPodProgramId(itemId))
    {
        if (g_targetPodPrograms.find(itemId) == g_targetPodPrograms.end())
            g_targetPodPrograms[itemId] = { itemId, name, false, false };
    }
    // 3. Weapons (real in-game ids, see GetWeaponName)
    else if (IsWeaponId(itemId))
    {
        int wId = itemId;
        g_knownPlayerWeapons.insert(wId);
        if (g_targetWeapons.find(wId) == g_targetWeapons.end())
        {
            g_targetWeapons[wId] = { wId, 1, name, false, false };
        }
    }
    // 4. Consumables, Materials, Chips
    else
    {
        auto it = g_targetItems.find(itemId);
        if (it == g_targetItems.end())
        {
            int tot = (totalCountParam > 0) ? totalCountParam : targetQty;
            int pending = knownOnly ? 0 : targetQty;
            g_targetItems[itemId] = { itemId, pending, name, false, knownOnly, tot };
        }
        else
        {
            int pending = knownOnly ? 0 : targetQty;
            if (totalCountParam > 0)
            {
                // Only what the hook does not already know about is really new
                int delta = totalCountParam - it->second.totalCount;
                if (delta < 0) delta = 0;
                if (pending > delta) pending = delta;
                if (totalCountParam > it->second.totalCount) it->second.totalCount = totalCountParam;
            }
            else if (!knownOnly)
            {
                it->second.totalCount += targetQty;
            }
            if (pending > 0)
            {
                it->second.targetQuantity += pending;
                it->second.granted = false;
            }
        }
    }

    LeaveCriticalSection(&g_csReconciliation);

    if (showNotification && !knownOnly)
    {
        ArchipelagoUI::AddReceivedItem(name.c_str(), sender.c_str());
    }

    FlushPendingArchipelagoGrants();
}

// Called when the game reloaded a save (death, ending, load...): the engine restored the inventory
// as it was when the save was written, so everything we granted AFTER that moment is gone.
void ReplayLostGrants(uint32_t savedPlaytime)
{
    if (!IsPlayerInGame()) return;
    uint32_t now = GetCurrentPlaytime();

    EnterCriticalSection(&g_csReconciliation);
    for (auto& rec : g_grantLog)
    {
        if (rec.playtime < savedPlaytime) continue; // already part of the save

        if (rec.itemId == 0)
        {
            uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
            int32_t* pMoney = (int32_t*)(moduleBase + MONEY_RVA);
            if (pMoney && !IsBadWritePtr(pMoney, sizeof(int32_t)))
            {
                *pMoney += rec.qty;
                if (*pMoney > 9999999) *pMoney = 9999999;
                std::cout << "[*] [AP Replay] Gold +" << rec.qty << " G restored after save reload.\n";
            }
        }
        else
        {
            // Granted in the very same second the save was written: only replay if really missing
            if (rec.playtime == savedPlaytime && GetPlayerItemCount(rec.itemId) >= rec.qty)
            {
                rec.playtime = now;
                continue;
            }
            if (GrantItemSafe(rec.itemId, rec.qty))
                std::cout << "[*] [AP Replay] Item ID " << rec.itemId << " x" << rec.qty << " restored after save reload.\n";
        }
        rec.playtime = now;
    }
    LeaveCriticalSection(&g_csReconciliation);
}

void RegisterReceivedArchipelagoWeapon(int weaponId, int level, const std::string& name, const std::string& sender, bool showNotification = true)
{
    int wId = weaponId;
    EnterCriticalSection(&g_csReconciliation);
    g_knownPlayerWeapons.insert(wId);
    if (g_targetWeapons.find(wId) == g_targetWeapons.end())
    {
        g_targetWeapons[wId] = { wId, level, name, false, false };
    }
    else
    {
        if (level > g_targetWeapons[wId].level)
        {
            g_targetWeapons[wId].level = level;
            g_targetWeapons[wId].granted = false;
        }
    }
    LeaveCriticalSection(&g_csReconciliation);

    if (showNotification)
    {
        ArchipelagoUI::AddReceivedItem(name.c_str(), sender.c_str());
    }

    FlushPendingArchipelagoGrants();
}




static const char* const UNKNOWN_WEAPON_NAME = "NieR Weapon";

// Real in-game weapon IDs (NieRHook memory reference sheet; 1070 = Virtuous Contract and
// 1240 = Type-40 Blade confirmed in-game 2026-10-17). AP ids are AP_BASE_ID + these ids.
static const char* GetWeaponName(int id)
{
    switch (id)
    {
    case 1003: return "Faith";
    case 1013: return "Iron Pipe";
    case 1020: return "Beastbane";
    case 1030: return "Ancient Overlord";
    case 1040: return "Phoenix Dagger";
    case 1050: return "Type-4O Sword";
    case 1060: return "Type-3 Sword";
    case 1070: return "Virtuous Contract";
    case 1071: return "Cruel Oath";
    case 1080: return "YoRHa-issue Blade";
    case 1090: return "Machine Sword";
    case 1203: return "Iron Will";
    case 1213: return "Fang of the Twins";
    case 1220: return "Beastlord";
    case 1230: return "Phoenix Sword";
    case 1240: return "Type-4O Blade";
    case 1250: return "Type-3 Blade";
    case 1260: return "Virtuous Treaty";
    case 1261: return "Cruel Blood Oath";
    case 1270: return "Machine Axe";
    case 1400: return "Phoenix Lance";
    case 1420: return "Beastcurse";
    case 1430: return "Dragoon Lance";
    case 1440: return "Spear of the Usurper";
    case 1450: return "Type-4O Lance";
    case 1460: return "Type-3 Lance";
    case 1470: return "Virtuous Dignity";
    case 1471: return "Cruel Arrogance";
    case 1480: return "Machine Spear";
    case 1600: return "Type-3 Fists";
    case 1610: return "Type-4O Fists";
    case 1620: return "Virtuous Grief";
    case 1621: return "Cruel Lament";
    case 1630: return "Demon's Cry";
    case 1640: return "Angel's Folly";
    case 1650: return "Machine Heads";
    case 1875: return "Engine Blade";
    case 1876: return "Cypress Stick";
    case 1877: return "Emil Heads";
    default: return UNKNOWN_WEAPON_NAME;
    }
}

static bool IsWeaponId(int id)
{
    return GetWeaponName(id) != UNKNOWN_WEAPON_NAME;
}

// Real pod program ids (NieREdit PodProgramId): 2013/2014/2016-2018/2020/2023 are unused
static bool IsPodProgramId(int id)
{
    switch (id)
    {
    case 2001: case 2002: case 2003: case 2004: case 2005: case 2006: case 2007: case 2008:
    case 2009: case 2010: case 2011: case 2012: case 2015: case 2019: case 2021: case 2022: case 2024:
        return true;
    default:
        return false;
    }
}

// Inventory item ids from NieREdit (VanillaInventoryItemIds), pod programs from NieREdit (PodProgramId)
static const char* GetItemName(int id)
{
    switch (id)
    {
    case 0: return "Small Recovery";
    case 1: return "Medium Recovery";
    case 2: return "Large Recovery";
    case 3: return "Full Recovery";
    case 50: return "Volt-Proof Salve";
    case 60: return "Visual Cure";
    case 70: return "Aural Cure";
    case 75: return "Cure Manipulation";
    case 80: return "Cure All Status";
    case 90: return "Cure All+Heal All";
    case 100: return "Melee Attack Up (S)";
    case 102: return "Melee Attack Up (L)";
    case 110: return "Ranged Attack Up (S)";
    case 112: return "Ranged Attack Up (L)";
    case 120: return "Melee Defense Up (S)";
    case 122: return "Melee Defense Up (L)";
    case 130: return "Ranged Defense Up (S)";
    case 132: return "Ranged Defense Up (L)";
    case 140: return "Skill Salve (S)";
    case 142: return "Skill Salve (L)";
    case 150: return "Impact Bracer (S)";
    case 152: return "Impact Bracer (L)";
    case 160: return "Speed Salve (S)";
    case 162: return "Speed Salve (L)";
    case 170: return "Popola's Booze";
    case 300: return "Animal Bait";
    case 330: return "Small G Luck+";
    case 332: return "Large G Luck+";
    case 400: return "E-Drug";
    case 410: return "Forbidden Fruit";
    case 510: return "Beast Hide";
    case 515: return "Boar Meat";
    case 516: return "Moose Meat";
    case 517: return "W. Boar Meat";
    case 518: return "W. Moose Meat";
    case 520: return "Stripped Screw";
    case 521: return "Pristine Screw";
    case 525: return "Small Gear";
    case 526: return "Large Gear";
    case 530: return "Rusted Clump";
    case 531: return "Meteorite Shard";
    case 535: return "Titanium Alloy";
    case 536: return "Memory Alloy";
    case 540: return "Broken Key";
    case 545: return "Broken Battery";
    case 546: return "Large Battery";
    case 550: return "Severed Cable";
    case 551: return "Pristine Cable";
    case 555: return "New Bolt";
    case 560: return "Clean Nut";
    case 570: return "Machine Arm";
    case 571: return "Machine Leg";
    case 572: return "Machine Torso";
    case 573: return "Machine Head";
    case 580: return "Simple Gadget";
    case 581: return "Elaborate Gadget";
    case 582: return "Complex Gadget";
    case 583: return "Powerup Part S";
    case 584: return "Powerup Part M";
    case 585: return "Powerup Part L";
    case 600: return "Copper Ore";
    case 601: return "Iron Ore";
    case 602: return "Silver Ore";
    case 603: return "Gold Ore";
    case 610: return "Dented Plate";
    case 621: return "Plant Seed";
    case 622: return "Tree Sap";
    case 623: return "Pure Water";
    case 624: return "Tree Seed";
    case 625: return "Desert Rose";
    case 626: return "Mushroom";
    case 627: return "Torn Book";
    case 628: return "Machine Oil";
    case 629: return "Tanning Agent";
    case 630: return "Filler Metal";
    case 631: return "Dye";
    case 632: return "Pyrite";
    case 633: return "Amber";
    case 634: return "Natural Rubber";
    case 635: return "Rusty Bolt";
    case 636: return "Crushed Nut";
    case 637: return "Giant Egg";
    case 638: return "Eagle Eggs";
    case 639: return "Black Pearl";
    case 640: return "Shattered Earring";
    case 641: return "Drab Bracelet";
    case 642: return "Sturdy Socket";
    case 643: return "Warped Wire";
    case 644: return "Stretched Coil";
    case 645: return "Dented Socket";
    case 646: return "Broken Circuit";
    case 680: return "Crystal";
    case 681: return "Lovely Choker";
    case 682: return "Ancient Mask";
    case 683: return "Precious Earrings";
    case 684: return "Tech Manual";
    case 685: return "Thick Dictionary";
    case 686: return "Pearl";
    case 687: return "Moldavite";
    case 688: return "Meteorite";
    case 690: return "Machine Core";
    case 691: return "Pascal's Core";
    case 692: return "Children's Cores";
    case 693: return "Pascal's Book";
    case 700: return "Letter for Sartre";
    case 701: return "Beautiful Glass";
    case 702: return "Machine Fossil";
    case 703: return "Sartre's Letter";
    case 715: return "Memory Chip";
    case 716: return "Man's Journal";
    case 720: return "Data Chip A";
    case 721: return "Data Chip B";
    case 722: return "Data Chip C";
    case 723: return "Data Chip D";
    case 724: return "Data Chip E";
    case 739: return "Rusty Dog Tag";
    case 741: return "Dirty Dog Tag";
    case 742: return "Damaged Dog Tag";
    case 743: return "Bloody Dog Tag";
    case 750: return "Rusty Music Box";
    case 760: return "Desert Photo";
    case 761: return "Amusement Park Photo";
    case 762: return "Forest Photo";
    case 775: return "Package";
    case 780: return "Broken Toy";
    case 781: return "Accounting Book";
    case 782: return "Small Shoe";
    case 790: return "Tri-color Cable";
    case 791: return "Four-color Cable";
    case 792: return "Five-color Cable";
    case 793: return "Toothbrush";
    case 794: return "Cosmetics";
    case 795: return "Dietary Goods";
    case 796: return "Writing Implement";
    case 797: return "Medical Journal";
    case 820: return "Forest Access Key";
    case 821: return "Ocean Access Key";
    case 822: return "Park Access Key";
    case 832: return "Machine Part";
    case 833: return "Stamp";
    case 834: return "Stamp Card";
    case 835: return "Aged Stick";
    case 836: return "Commandment Slab";
    case 837: return "Filthy Mask";
    case 838: return "Statue of a Girl";
    case 839: return "Toy Material";
    case 840: return "Storage Element";
    case 841: return "Plug-in Chip";
    case 842: return "Rigid Tree Bark";
    case 843: return "Membership Card";
    case 844: return "Dirty Bag";
    case 845: return "Elevator Key";
    case 851: return "Fuel Filter";
    case 852: return "Viscous Oil";
    case 870: return "Valve: Head";
    case 871: return "Camouflage Goggles";
    case 872: return "A2 Wig";
    case 873: return "Pink Ribbon";
    case 874: return "Blue Ribbon";
    case 875: return "Proof of Oath";
    case 876: return "Masamune Mask";
    case 877: return "Matsuda Mask";
    case 878: return "Sato Mask";
    case 880: return "White Hair";
    case 881: return "Black Hair";
    case 882: return "Brown Hair";
    case 883: return "Red Hair";
    case 884: return "Blue Hair";
    case 885: return "Green Hair";
    case 886: return "Purple Hair";
    case 887: return "Ash Grey Hair";
    case 888: return "Golden Hair";
    case 889: return "Pastel Pink Hair";
    case 890: return "Light Blue Hair";
    case 891: return "Lime Green Hair";
    case 892: return "Light Purple Hair";
    case 893: return "Neon White Hair";
    case 894: return "Neon Yellow Hair";
    case 895: return "Neon Pink Hair";
    case 896: return "Neon Blue Hair";
    case 897: return "Neon Green Hair";
    case 898: return "Neon Purple Hair";
    case 920: return "Sachet";
    case 921: return "Quality Sachet";
    case 922: return "Choice Sachet";
    case 930: return "Sound Data 1";
    case 931: return "Sound Data 2";
    case 932: return "Sound Data 3";
    case 933: return "Sound Data 4";
    case 934: return "Sound Data 5";
    case 935: return "Record: 3C3C1D119440927";
    case 936: return "Record: CEO";
    case 950: return "Play System Pod";
    case 951: return "Grimoire Weiss";
    case 952: return "Cardboard Pod";
    case 953: return "Blue Stripes Pod";
    case 954: return "Retro Red Pod";
    case 955: return "Retro White Pod";
    case 956: return "Retro Black Pod";
    case 957: return "Retro Gray Pod";
    case 958: return "Retro Purple Pod";
    case 959: return "amazarashi Head";
    case 960: return "Emil Bullets";
    case 961: return "CEO Bullets";
    case 980: return "Dress Module";
    case 981: return "Heavy Armor A";
    case 982: return "Heavy Armor B";
    case 983: return "Revealing Outfit";
    case 984: return "Young Man's Outfit";
    case 985: return "Destroyer Outfit";
    case 990: return "Machine Mask";
    case 991: return "Emil's Head";
    case 992: return "Lunar Tear";
    case 993: return "Emil Mask";
    case 994: return "Sand Mask";
    case 995: return "Adam's Glasses";
    case 996: return "Alien Mask";
    case 997: return "Valve: Left Eye";
    case 998: return "Valve: Right Eye";
    case 999: return "Valve: Both Eyes";
    case 8001: return "Arowana";
    case 8002: return "Twinfish";
    case 8003: return "Killifish";
    case 8004: return "Carp";
    case 8005: return "Bloat Fish";
    case 8006: return "Koi Carp";
    case 8007: return "Fur Carp";
    case 8008: return "Freshwater Ray";
    case 8009: return "Arapaima";
    case 8010: return "Oil Sardine";
    case 8011: return "Water Flea";
    case 8012: return "Twoface";
    case 8013: return "Coelacanth";
    case 8014: return "Blowfish";
    case 8015: return "Swordfish";
    case 8016: return "Mackerel";
    case 8017: return "Horseshoe Crab";
    case 8018: return "Beetle Fish";
    case 8019: return "Starfish";
    case 8020: return "Bream";
    case 8021: return "Basking Shark";
    case 8022: return "Killifish Machine";
    case 8023: return "Koi Carp Machine";
    case 8024: return "Arapaima Machine";
    case 8025: return "Carp Machine";
    case 8026: return "Bloat Fish Machine";
    case 8027: return "Blowfish Machine";
    case 8028: return "Swordfish Machine";
    case 8029: return "Starfish Machine";
    case 8030: return "Bream Machine";
    case 8031: return "Coelacanth Machine";
    case 8032: return "Mackerel Machine";
    case 8033: return "Horseshoe Crab Machine";
    case 8034: return "Arowana Machine";
    case 8035: return "Basking Shark Machine";
    case 8036: return "Freshwater Ray MAchine";
    case 8037: return "Machine Lifeform Head";
    case 8038: return "Tire";
    case 8039: return "Gas Cylinder";
    case 8040: return "Battery";
    case 8041: return "Broken Firearm";

    // Pod Programs
    case 2001: return "Pod Program: Laser (R010)";
    case 2002: return "Pod Program: Mirage (R020)";
    case 2003: return "Pod Program: Hammer (R030)";
    case 2004: return "Pod Program: Blade (R040)";
    case 2005: return "Pod Program: Spear (R050)";
    case 2006: return "Pod Program: M Shield (R070)";
    case 2007: return "Pod Program: P Shield (A060)";
    case 2008: return "Pod Program: Wave (A080)";
    case 2009: return "Pod Program: Wire (A090)";
    case 2010: return "Pod Program: Decoy (A100)";
    case 2011: return "Pod Program: Slow (A110)";
    case 2012: return "Pod Program: Repair (A120)";
    case 2015: return "Pod Program: Bomb (A130)";
    case 2019: return "Pod Program: Gravity (A140)";
    case 2021: return "Pod Program: Volt (A150)";
    case 2022: return "Pod Program: Missile (A160)";
    case 2024: return "Pod Program: Scanner (A170)";

    // Logic-only AP item
    case 2100: return "Hacking Module (9S Ability)";

    // Plug-in Chips (Useful)
    case 3004: return "Plug-in Chip: Weapon Attack Up +3";
    case 3076: return "Plug-in Chip: Max HP Up +3";
    case 3102: return "Plug-in Chip: Auto-Heal +2";
    case 3193: return "Plug-in Chip: Overclock +3";
    case 3121: return "Plug-in Chip: Moving Speed Up +3";
    case 3148: return "Plug-in Chip: Shockwave +3";
    case 3130: return "Plug-in Chip: Drop Rate Up +3";

    // System / HUD Chips
    case 3335: return "HUD: HP Gauge";
    case 3336: return "HUD: Sound Waves";
    case 3337: return "HUD: Enemy Data";
    case 3338: return "OS Chip";
    case 3343: return "HUD: Skill Gauge";
    case 3344: return "HUD: Text Log";
    case 3345: return "HUD: Mini-map";
    case 3346: return "HUD: EXP Gauge";
    case 3347: return "HUD: Save Points";
    case 3348: return "HUD: Damage Values";
    case 3349: return "HUD: Objectives";
    case 3350: return "HUD: Control";

    // Gold Bundles
    case 4001: return "Gold Bundle (1000 G)";
    case 4002: return "Gold Bundle (2500 G)";
    case 4003: return "Gold Bundle (5000 G)";
    case 4004: return "Gold Bundle (10000 G)";
    case 4100: return "Progressive Chip Capacity";


    default: return IsWeaponId(id) ? GetWeaponName(id) : "NieR Item";
    }
}

static int GetPlayerItemCount(int item_id)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return 0;

    NieRItemSlot* slots = (NieRItemSlot*)(moduleBase + INVENTORY_TABLE_START);
    const int totalSlots = (int)((INVENTORY_TABLE_END - INVENTORY_TABLE_START) / sizeof(NieRItemSlot));

    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)item_id && slots[i].quantity > 0)
            {
                return (int)slots[i].quantity;
            }
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return 0;
}

static int GetPlayerChipCount(int item_id)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return 0;

    NieRChipSlot* chips = (NieRChipSlot*)(moduleBase + CHIP_TABLE_OFFSET_START);
    const int totalSlots = (int)((CHIP_TABLE_OFFSET_END - CHIP_TABLE_OFFSET_START) / sizeof(NieRChipSlot));
    int count = 0;
    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (chips[i].item_id != 0 && chips[i].item_id != 0xFFFFFFFF && chips[i].item_id == (uint32_t)item_id)
            {
                count++;
            }
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    return count;
}

bool GivePlayerItemDirect(int item_id, int count)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    NieRItemSlot* slots = (NieRItemSlot*)(moduleBase + INVENTORY_TABLE_START);
    const int totalSlots = (int)((INVENTORY_TABLE_END - INVENTORY_TABLE_START) / sizeof(NieRItemSlot));

    NieRItemSlot* emptySlot = nullptr;

    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)item_id && slots[i].quantity > 0)
            {
                slots[i].quantity += count;
                if (slots[i].quantity > 99) slots[i].quantity = 99;
                if (slots[i].flags == 0 || slots[i].flags == 0xFFFFFFFF)
                    slots[i].flags = 0x70000;
                return true;
            }
            if (emptySlot == nullptr)
            {
                if (slots[i].id == 0xFFFFFFFF || (slots[i].id == 0 && slots[i].quantity == 0))
                {
                    emptySlot = &slots[i];
                }
            }
        }

        if (emptySlot != nullptr)
        {
            emptySlot->id = (uint32_t)item_id;
            emptySlot->flags = 0x70000;
            emptySlot->quantity = (uint32_t)(count > 99 ? 99 : count);
            return true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

bool GivePlayerWeaponDirect(int weapon_id, int level)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    NieRWeaponSlot* slots = (NieRWeaponSlot*)(moduleBase + WEAPONS_OFFSET_START);
    const int totalSlots = (int)((WEAPONS_OFFSET_END - WEAPONS_OFFSET_START) / sizeof(NieRWeaponSlot));

    NieRWeaponSlot* emptySlot = nullptr;

    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)weapon_id)
            {
                uint32_t targetLevel = (uint32_t)(level < 1 ? 1 : (level > 4 ? 4 : level));
                if (targetLevel > slots[i].level) slots[i].level = targetLevel;
                return true;
            }
            if (emptySlot == nullptr && (slots[i].id == 0xFFFFFFFF || slots[i].id == 0))
            {
                emptySlot = &slots[i];
            }
        }

        if (emptySlot != nullptr)
        {
            emptySlot->id = (uint32_t)weapon_id;
            emptySlot->level = (uint32_t)(level < 1 ? 1 : (level > 4 ? 4 : level));
            emptySlot->unk1 = 0;
            emptySlot->unk2 = 1;
            emptySlot->unk3 = 0;
            return true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

bool GivePlayerPodProgramDirect(int program_id)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    NieRPodProgramSlot* slots = (NieRPodProgramSlot*)(moduleBase + POD_PROGRAMS_OFFSET_START);
    const int totalSlots = (int)((POD_PROGRAMS_OFFSET_END - POD_PROGRAMS_OFFSET_START) / sizeof(NieRPodProgramSlot));

    NieRPodProgramSlot* emptySlot = nullptr;

    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)program_id)
            {
                slots[i].one = 1;
                return true;
            }
            if (emptySlot == nullptr && (slots[i].id == 0xFFFFFFFF || slots[i].id == 0))
            {
                emptySlot = &slots[i];
            }
        }

        if (emptySlot != nullptr)
        {
            emptySlot->id = (uint32_t)program_id;
            emptySlot->one = 1;
            return true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

bool GivePlayerGoldDirect(int amount)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    int32_t* pMoney = (int32_t*)(moduleBase + MONEY_RVA);
    __try
    {
        if (pMoney && !IsBadWritePtr(pMoney, sizeof(int32_t)))
        {
            *pMoney += amount;
            if (*pMoney > 9999999) *pMoney = 9999999;
            return true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

// Chips without levels (NieREdit VanillaPluginChipIds): item id, type, base code, weight
struct SystemChipInfo { int itemId; uint32_t type; uint32_t baseCode; uint32_t weight; };
static const SystemChipInfo s_systemChips[] = {
    { 3208, 0x23, 0x0F5, 6 }, // Item Scan
    { 3334, 0x26, 0x121, 6 }, // Death Rattle
    { 3335, 0x27, 0x123, 2 }, // HUD: HP Gauge
    { 3336, 0x28, 0x12D, 3 }, // HUD: Sound Waves
    { 3337, 0x29, 0x126, 2 }, // HUD: Enemy Data
    { 3338, 0x2A, 0x122, 2 }, // OS Chip
    { 3339, 0x2C, 0x0F6, 6 }, // Evasive System
    { 3340, 0x2D, 0x048, 6 }, // Continuous Combo
    { 3341, 0x2E, 0x0F7, 6 }, // Bullet Detonation
    { 3342, 0x2F, 0x0F4, 6 }, // Auto-collect Items
    { 3343, 0x30, 0x125, 2 }, // HUD: Skill Gauge
    { 3344, 0x31, 0x129, 2 }, // HUD: Text Log
    { 3345, 0x32, 0x127, 2 }, // HUD: Mini-map
    { 3346, 0x33, 0x124, 1 }, // HUD: EXP Gauge
    { 3347, 0x34, 0x12A, 1 }, // HUD: Save Points
    { 3348, 0x35, 0x12C, 3 }, // HUD: Damage Values
    { 3349, 0x36, 0x128, 1 }, // HUD: Objectives
    { 3350, 0x37, 0x12E, 3 }, // HUD: Control
    { 3353, 0x3A, 0x12B, 3 }, // HUD: Fishing Spots
    { 3354, 0x3B, 0x0F8, 1 }, // Auto-attack
    { 3355, 0x3C, 0x0F9, 1 }, // Auto-fire
    { 3356, 0x3D, 0x0FA, 1 }, // Auto-evade
    { 3357, 0x3E, 0x0FB, 1 }, // Auto-program
    { 3358, 0x3F, 0x0FC, 1 }, // Auto-weapon Switch
};

static const SystemChipInfo* FindSystemChip(int item_id)
{
    for (const SystemChipInfo& c : s_systemChips)
        if (c.itemId == item_id) return &c;
    return nullptr;
}

static uint32_t GetChipKind(int item_id)
{
    if (item_id >= 3001 && item_id <= 3009) return 1;  // Weapon Attack Up
    if (item_id >= 3010 && item_id <= 3018) return 2;  // Down-Attack Up
    if (item_id >= 3019 && item_id <= 3027) return 3;  // Critical Up
    if (item_id >= 3028 && item_id <= 3036) return 4;  // Ranged Attack Up
    if (item_id >= 3037 && item_id <= 3045) return 5;  // Fast Cooldown
    if (item_id >= 3046 && item_id <= 3054) return 6;  // Melee Defence Up
    if (item_id >= 3055 && item_id <= 3063) return 7;  // Ranged Defence Up
    if (item_id >= 3064 && item_id <= 3072) return 8;  // Anti Chain Damage
    if (item_id >= 3073 && item_id <= 3081) return 9;  // Max HP Up
    if (item_id >= 3082 && item_id <= 3090) return 10; // Offensive Heal
    if (item_id >= 3091 && item_id <= 3099) return 11; // Deadly Heal
    if (item_id >= 3100 && item_id <= 3108) return 12; // Auto-Heal
    if (item_id >= 3109 && item_id <= 3117) return 13; // Evade Range Up
    if (item_id >= 3118 && item_id <= 3126) return 14; // Moving Speed Up
    if (item_id >= 3127 && item_id <= 3135) return 15; // Drop Rate Up
    if (item_id >= 3136 && item_id <= 3144) return 16; // EXP Gain Up
    if (item_id >= 3145 && item_id <= 3153) return 17; // Shock Wave
    if (item_id >= 3154 && item_id <= 3162) return 18; // Last Stand
    if (item_id >= 3163 && item_id <= 3171) return 19; // Damage Absorb
    if (item_id >= 3172 && item_id <= 3180) return 20; // Vengeance
    if (item_id >= 3181 && item_id <= 3189) return 21; // Reset
    if (item_id >= 3190 && item_id <= 3198) return 22; // Overclock
    if (item_id >= 3199 && item_id <= 3207) return 23; // Resilience
    if (item_id >= 3217 && item_id <= 3225) return 24; // Counter
    if (item_id >= 3226 && item_id <= 3234) return 25; // Taunt Up
    if (item_id >= 3235 && item_id <= 3243) return 26; // Charge Attack
    if (item_id >= 3244 && item_id <= 3252) return 27; // Auto-use Item
    if (item_id >= 3262 && item_id <= 3270) return 29; // Hijack Boost
    if (item_id >= 3289 && item_id <= 3297) return 30; // Stun
    if (item_id >= 3298 && item_id <= 3306) return 31; // Combust
    if (item_id >= 3325 && item_id <= 3333) return 34; // Heal Drops Up

    // System / HUD chips (no levels)
    if (const SystemChipInfo* sys = FindSystemChip(item_id)) return sys->type;

    return 1;
}

static uint32_t GetChipBaseId(int item_id)
{
    if (item_id >= 3001 && item_id <= 3009) return 3001;
    if (item_id >= 3010 && item_id <= 3018) return 3010;
    if (item_id >= 3019 && item_id <= 3027) return 3019;
    if (item_id >= 3028 && item_id <= 3036) return 3028;
    if (item_id >= 3037 && item_id <= 3045) return 3037;
    if (item_id >= 3046 && item_id <= 3054) return 3046;
    if (item_id >= 3055 && item_id <= 3063) return 3055;
    if (item_id >= 3064 && item_id <= 3072) return 3064;
    if (item_id >= 3073 && item_id <= 3081) return 3073;
    if (item_id >= 3082 && item_id <= 3090) return 3082;
    if (item_id >= 3091 && item_id <= 3099) return 3091;
    if (item_id >= 3100 && item_id <= 3108) return 3100;
    if (item_id >= 3109 && item_id <= 3117) return 3109;
    if (item_id >= 3118 && item_id <= 3126) return 3118;
    if (item_id >= 3127 && item_id <= 3135) return 3127;
    if (item_id >= 3136 && item_id <= 3144) return 3136;
    if (item_id >= 3145 && item_id <= 3153) return 3145;
    if (item_id >= 3154 && item_id <= 3162) return 3154;
    if (item_id >= 3163 && item_id <= 3171) return 3163;
    if (item_id >= 3172 && item_id <= 3180) return 3172;
    if (item_id >= 3181 && item_id <= 3189) return 3181;
    if (item_id >= 3190 && item_id <= 3198) return 3190;
    if (item_id >= 3199 && item_id <= 3207) return 3199;
    if (item_id >= 3217 && item_id <= 3225) return 3217;
    if (item_id >= 3226 && item_id <= 3234) return 3226;
    if (item_id >= 3235 && item_id <= 3243) return 3235;
    if (item_id >= 3244 && item_id <= 3252) return 3244;
    if (item_id >= 3262 && item_id <= 3270) return 3262;
    if (item_id >= 3289 && item_id <= 3297) return 3289;
    if (item_id >= 3298 && item_id <= 3306) return 3298;
    if (item_id >= 3325 && item_id <= 3333) return 3325;
    return (uint32_t)item_id;
}

// Leveled chips: base code of level +0 (NieREdit VanillaPluginChipIds), level is added on top
static uint32_t GetChipBaseCode(int item_id)
{
    if (const SystemChipInfo* sys = FindSystemChip(item_id)) return sys->baseCode;

    static const struct { uint32_t baseId; uint32_t baseCode; } s_families[] = {
        { 3001, 0x000 }, { 3010, 0x009 }, { 3019, 0x012 }, { 3028, 0x01B }, { 3037, 0x0A3 }, { 3046, 0x049 },
        { 3055, 0x052 }, { 3064, 0x05B }, { 3073, 0x06D }, { 3082, 0x076 }, { 3091, 0x07F }, { 3100, 0x088 },
        { 3109, 0x0AC }, { 3118, 0x0B5 }, { 3127, 0x0BE }, { 3136, 0x0C7 }, { 3145, 0x024 }, { 3154, 0x02D },
        { 3163, 0x091 }, { 3172, 0x0D0 }, { 3181, 0x09A }, { 3190, 0x0D9 }, { 3199, 0x064 }, { 3217, 0x036 },
        { 3226, 0x0E2 }, { 3235, 0x03F }, { 3244, 0x0EB }, { 3262, 0x0FD }, { 3289, 0x106 }, { 3298, 0x10F },
        { 3325, 0x118 },
    };
    uint32_t baseId = GetChipBaseId(item_id);
    for (const auto& f : s_families)
        if (f.baseId == baseId) return f.baseCode + ((uint32_t)item_id - baseId);
    return 0xFFFFFFFF;
}

static uint32_t GetChipLevel(int item_id)
{
    if (item_id >= 3335) return 0;
    uint32_t base = GetChipBaseId(item_id);
    return (uint32_t)(item_id - base);
}

static uint32_t GetChipDefaultCost(int item_id, uint32_t level)
{
    if (const SystemChipInfo* sys = FindSystemChip(item_id)) return sys->weight;

    static const uint32_t diamondCosts[9] = { 4, 5, 6, 7, 9, 11, 14, 17, 21 };
    if (level < 9) return diamondCosts[level];
    return 10;
}

bool GivePlayerChipDirect(int item_id)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    NieRChipSlot* chips = (NieRChipSlot*)(moduleBase + CHIP_TABLE_OFFSET_START);
    const int totalSlots = (int)((CHIP_TABLE_OFFSET_END - CHIP_TABLE_OFFSET_START) / sizeof(NieRChipSlot));

    __try
    {
        NieRChipSlot* emptySlot = nullptr;

        for (int i = 0; i < totalSlots; ++i)
        {
            if (chips[i].item_id == 0xFFFFFFFF || chips[i].item_id == 0)
            {
                emptySlot = &chips[i];
                break;
            }
        }

        if (emptySlot)
        {
            uint32_t kind = GetChipKind(item_id);
            uint32_t level = GetChipLevel(item_id);
            uint32_t cost = GetChipDefaultCost(item_id, level);

            emptySlot->base_code = GetChipBaseCode(item_id);
            emptySlot->item_id = (uint32_t)item_id;
            emptySlot->kind = kind;
            emptySlot->level = level;
            emptySlot->cost = cost;
            emptySlot->equipped_A = 0xFFFFFFFF;
            emptySlot->equipped_B = 0xFFFFFFFF;
            emptySlot->equipped_C = 0xFFFFFFFF;
            emptySlot->unk1 = 0xFFFFFFFF;
            emptySlot->unk2 = 0xFFFFFFFF;
            emptySlot->unk3 = 0xFFFFFFFF;
            emptySlot->unk4 = 0;
            return true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

void SanitizePlayerWeaponsAndHUD()
{
    if (!IsPlayerInGame()) return;
    static DWORD s_lastSanitizeTick = 0;
    DWORD now = GetTickCount();
    if (now - s_lastSanitizeTick < 600) return;
    s_lastSanitizeTick = now;

    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return;

    EnterCriticalSection(&g_csReconciliation);
    __try
    {
        // 1. WEAPONS SANITIZER (Removes starter weapons until Archipelago delivers them)
        if (g_bEnforceBareFists)
        {
            NieRWeaponSlot* wSlots = (NieRWeaponSlot*)(moduleBase + WEAPONS_OFFSET_START);
            const int totalWSlots = (int)((WEAPONS_OFFSET_END - WEAPONS_OFFSET_START) / sizeof(NieRWeaponSlot));

            for (int i = 0; i < totalWSlots; ++i)
            {
                uint32_t wId = wSlots[i].id;
                if (wId != 0 && wId != 0xFFFFFFFF)
                {
                    if (g_bArchipelagoItemsSynced && g_targetWeapons.find((int)wId) == g_targetWeapons.end())
                    {
                        if (s_sentStartingChecks.find((int)wId) == s_sentStartingChecks.end())
                        {
                            s_sentStartingChecks.insert((int)wId);
                            // Any weapon that shows up without coming from Archipelago is its weapon check: starter
                            // weapons (1070, 1071) and weapon shop purchases, which never go through the AddItem hook.
                            // 1260 (Virtuous Treaty) is stripped here without sending check,
                            // because its check is triggered when retrieved at the factory ruins after prologue!
                            if (wId != 1260)
                            {
                                char eventJson[512];
                                sprintf_s(eventJson,
                                          "{\"event\":\"check\",\"check_num\":%d,\"type\":\"WEAPON_CHEST\",\"item_id\":%d,\"quantity\":1,\"caller_rva\":\"0x0\",\"name\":\"%s\"}",
                                          ++g_totalInterceptedChecks, (int)wId, GetWeaponName((int)wId));
                                SendBridgeMessage(eventJson);
                                std::cout << "[*] [SANITY] Weapon obtained outside Archipelago -> check: " << GetWeaponName((int)wId) << " (ID " << wId << ")\n";
                                LogEventToFile("[CHECK_INTERCEPTED #%d] Type: WEAPON_OWNED | Item: %s (ID %d)\n",
                                               g_totalInterceptedChecks, GetWeaponName((int)wId), (int)wId);
                            }
                        }

                        // Taken away until Archipelago delivers it (the weapon shop remembers its own sales, so a
                        // bought weapon still shows as sold out).
                        wSlots[i].id = 0xFFFFFFFF;
                        wSlots[i].level = 0;
                        wSlots[i].unk1 = 0;
                        wSlots[i].unk2 = 0;
                        wSlots[i].unk3 = 0;
                    }
                }
            }

            // Equipped weapons: Set 1 Light, Heavy, Set 2 Light, Heavy (file 0x386F4 -> saveBase + 0x386F0).
            // Only these 4 values: the EXP counter follows shortly after and must never be touched.
            uint32_t* pEquipped = (uint32_t*)(moduleBase + SAVE_DATA_BASE_RVA + 0x386F0);
            for (int eqIdx = 0; eqIdx < 4; ++eqIdx)
            {
                uint32_t eqWId = pEquipped[eqIdx];
                if (g_bArchipelagoItemsSynced && eqWId >= 1000 && eqWId <= 1999 && g_targetWeapons.find((int)eqWId) == g_targetWeapons.end())
                {
                    pEquipped[eqIdx] = 0; // Bare fists!
                }
            }
        }

        // 1b. Starter pod program R010 Laser (prologue): its location is checked once owned, then the program
        // is taken away (and unequipped) until Archipelago delivers it, like the starter weapons.
        if (s_sentStartingChecks.find(2001) == s_sentStartingChecks.end() && PlayerOwnsPodProgram(2001))
        {
            s_sentStartingChecks.insert(2001);
            char eventJson[256];
            sprintf_s(eventJson,
                      "{\"event\":\"check\",\"check_num\":%d,\"type\":\"SHOP_PURCHASE\",\"item_id\":2001,\"quantity\":1,\"caller_rva\":\"0x0\",\"name\":\"%s\"}",
                      ++g_totalInterceptedChecks, GetItemName(2001));
            SendBridgeMessage(eventJson);
            std::cout << "[*] [SANITY] Starter pod program R010 Laser owned -> check sent.\n";
        }
        if (g_bEnforceBareFists && g_bArchipelagoItemsSynced && g_targetPodPrograms.find(2001) == g_targetPodPrograms.end() && PlayerOwnsPodProgram(2001))
        {
            NieRPodProgramSlot* pSlots = (NieRPodProgramSlot*)(moduleBase + POD_PROGRAMS_OFFSET_START);
            const int totalPSlots = (int)((POD_PROGRAMS_OFFSET_END - POD_PROGRAMS_OFFSET_START) / sizeof(NieRPodProgramSlot));
            for (int i = 0; i < totalPSlots; ++i)
            {
                if (pSlots[i].id == 2001) pSlots[i].id = 0xFFFFFFFF;
            }
            // Pod config (file 0x38728 -> saveBase + 0x38724): 3 pod levels, then the program equipped on each pod
            // as an index where program id = 2000 + index (0 = none).
            int32_t* pEquippedPrograms = (int32_t*)(moduleBase + SAVE_DATA_BASE_RVA + 0x38724 + 12);
            for (int pod = 0; pod < 3; ++pod)
            {
                if (pEquippedPrograms[pod] == 2001 - 2000) pEquippedPrograms[pod] = 0;
            }
            std::cout << "[*] [SANITY] Starter pod program R010 Laser removed until granted by Archipelago.\n";
        }

        // 2. HUD CHIPS SANITIZER (Strips starter HUD chips until Archipelago delivers them)
        if (g_bEnforceBareHUD)
        {
            NieRChipSlot* chips = (NieRChipSlot*)(moduleBase + CHIP_TABLE_OFFSET_START);
            const int totalCSlots = (int)((CHIP_TABLE_OFFSET_END - CHIP_TABLE_OFFSET_START) / sizeof(NieRChipSlot));

            // All HUD chips in NieR: Automata (excluding OS chip 3338 which must never be removed).
            // 2B starts with 9 of them: HP Gauge 3335, Enemy Data 3337, Skill Gauge 3343, Text Log 3344,
            // Mini-map 3345, Save Points 3347, Damage Values 3348, Objectives 3349, Control 3350.
            static const int s_hudChipIds[] = { 3335, 3336, 3337, 3343, 3344, 3345, 3346, 3347, 3348, 3349, 3350, 3353 };

            for (int i = 0; i < totalCSlots; ++i)
            {
                uint32_t cId = chips[i].item_id;
                if (cId != 0 && cId != 0xFFFFFFFF && cId != 3338) // Never touch OS chip!
                {
                    bool isHUD = false;
                    for (int hid : s_hudChipIds) { if (hid == (int)cId) { isHUD = true; break; } }

                    // Stripped without a check: the starting HUD chips are not locations
                    if (isHUD && g_targetItems.find((int)cId) == g_targetItems.end())
                    {
                        memset(&chips[i], 0xFF, sizeof(NieRChipSlot));
                        chips[i].unk4 = 0;
                    }
                }
            }
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    LeaveCriticalSection(&g_csReconciliation);
}

// Progressive Chip Capacity: a "Storage +8" bought in the shop raises the upgrade counter -> we send a
// STORAGE_UPGRADE check and put the counter back. The counter itself always equals the number of
// "Progressive Chip Capacity" items received (once the bridge told us that number).
void EnforceProgressiveChipStorage()
{
    static int s_lastSeen = -1; // counter value at the previous tick, -1 = baseline needed (load)
    if (!g_bProgressiveChipStorage) { s_lastSeen = -1; return; }
    if (!IsPlayerInGame()) { s_lastSeen = -1; return; }

    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return;

    EnterCriticalSection(&g_csReconciliation);
    __try
    {
        uint32_t* pCount = (uint32_t*)(moduleBase + SAVE_DATA_BASE_RVA + STORAGE_UPGRADES_SAVE_OFFSET);
        int cur = (int)*pCount;
        if (cur >= 0 && cur <= MAX_STORAGE_UPGRADES)
        {
            if (s_lastSeen >= 0 && cur > s_lastSeen)
            {
                char eventJson[256];
                sprintf_s(eventJson,
                          "{\"event\":\"check\",\"check_num\":%d,\"type\":\"STORAGE_UPGRADE\",\"item_id\":%d,\"quantity\":1,\"caller_rva\":\"0x0\",\"name\":\"Storage +8\"}",
                          ++g_totalInterceptedChecks, PROGRESSIVE_CHIP_CAPACITY_ID);
                SendBridgeMessage(eventJson);
                std::cout << "[*] [STORAGE] Storage +8 bought (" << s_lastSeen << " -> " << cur << ") -> check sent, purchase reverted.\n";
                cur = s_lastSeen;
                *pCount = (uint32_t)cur;
            }

            if (g_targetStorageUpgrades >= 0 && cur != g_targetStorageUpgrades)
            {
                std::cout << "[+] [STORAGE] Chip storage upgrades: " << cur << " -> " << g_targetStorageUpgrades << " (Progressive Chip Capacity)\n";
                cur = g_targetStorageUpgrades;
                *pCount = (uint32_t)cur;
            }
            s_lastSeen = cur;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    LeaveCriticalSection(&g_csReconciliation);
}

// Player level, computed like the engine lookup at 0x403380: the player entity holds its level table at
// +0x2078, rows of 0x1C bytes from +0x20 whose first dword is the EXP needed, row count at +0xAF4.
// Returns 0 when the table does not look valid (wrong entity, loading screen).
static int GetPlayerLevel(uintptr_t moduleBase, bool logTable)
{
    if (!g_piExperience) return 0;

    __try
    {
        uintptr_t* pPlayerEntityPtr = (uintptr_t*)(moduleBase + 0x1020948);
        if (!*pPlayerEntityPtr || IsBadReadPtr((void*)(*pPlayerEntityPtr + 0x2078), 0xAF8)) return 0;

        const uintptr_t table = *pPlayerEntityPtr + 0x2078;
        const int rows = *(const int*)(table + 0xAF4);
        if (rows < 2 || rows > 99) return 0;

        const int* need = (const int*)(table + 0x20);  // need[i * 7] = EXP for level i + 1
        if (need[0] < 0) return 0;
        for (int i = 1; i < rows; ++i)
            if (need[i * 7] <= need[(i - 1) * 7]) return 0;

        if (logTable)
        {
            char buf[1200] = "";
            for (int i = 0; i < rows; ++i)
            {
                char num[16];
                sprintf_s(num, "%s%d", i ? "," : "", need[i * 7]);
                strcat_s(buf, num);
            }
            LogEventToFile("[LEVEL_TABLE] %d rows: %s\n", rows, buf);
        }

        const int exp = *g_piExperience;
        int level = 1;
        for (int i = 1; i < rows && need[i * 7] <= exp; ++i)
            level = i + 1;
        return level;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return 0;
}

// Sends the player level to the bridge whenever it changes (level milestone checks)
static void CheckPlayerLevelProgress(uintptr_t moduleBase)
{
    static ULONGLONG s_lastTick = 0;
    static int s_lastLevel = 0;
    static bool s_tableLogged = false;

    const ULONGLONG now = GetTickCount64();
    if (now - s_lastTick < 1000) return;
    s_lastTick = now;
    if (!IsPlayerInGame()) return;

    const int level = GetPlayerLevel(moduleBase, !s_tableLogged);
    if (level <= 0) return;
    s_tableLogged = true;
    if (level == s_lastLevel) return;
    s_lastLevel = level;

    char eventJson[96];
    sprintf_s(eventJson, "{\"event\":\"level\",\"level\":%d,\"exp\":%d}", level, *g_piExperience);
    SendBridgeMessage(eventJson);
}

static void CheckPrologueBossProgress(uintptr_t moduleBase)
{
    if (!IsPlayerInGame()) return;

    __try
    {
        const char* pPhase = (const char*)(moduleBase + SAVE_DATA_BASE_RVA + 0x395F0);
        if (IsBadReadPtr(pPhase, 32)) return;

        // Detect if player is currently in the initial prologue room (before Buzzsaw)
        if (strstr(pPhase, "00_30_A_RobotM") || strstr(pPhase, "00_70_A_RobotM_Pro_ArmBoss_1st"))
        {
            s_wasInPrologue = true;
        }

        // 1. Goliath Buzzsaw Defeated (ArmBoss 1st defeated -> transitioning to ArmBoss 2nd or ProBoss or later area)
        if (s_wasInPrologue && !s_buzzsawSent)
        {
            if (strstr(pPhase, "ArmBoss_2nd") || strstr(pPhase, "ProBoss") || strstr(pPhase, "00_80_") || strstr(pPhase, "05_00") || strstr(pPhase, "05_10"))
            {
                s_buzzsawSent = true;
                char eventJson[512];
                sprintf_s(eventJson, "{\"event\":\"check\",\"check_num\":%d,\"type\":\"BOSS_DEFEAT\",\"item_id\":5,\"quantity\":1,\"caller_rva\":\"0x0\",\"name\":\"Factory: Goliath Buzzsaw Defeated\"}", ++g_totalInterceptedChecks);
                SendBridgeMessage(eventJson);
                std::cout << "[+] [PROLOGUE CHECK] Goliath Buzzsaw Defeated! Sent check 92000005 to Archipelago.\n";
            }
        }

        // 2. Engels Defeated (ProBoss completed -> woke up in Bunker or arrived on Earth)
        if (s_wasInPrologue && !s_engelsSent)
        {
            if (strstr(pPhase, "Bunker") || strstr(pPhase, "EarthArrival") || strstr(pPhase, "01_00") || strstr(pPhase, "02_01") || strstr(pPhase, "Resistance_Camp"))
            {
                s_engelsSent = true;
                char eventJson[512];
                sprintf_s(eventJson, "{\"event\":\"check\",\"check_num\":%d,\"type\":\"BOSS_DEFEAT\",\"item_id\":6,\"quantity\":1,\"caller_rva\":\"0x0\",\"name\":\"Factory: Engels Defeated (Prologue Complete)\"}", ++g_totalInterceptedChecks);
                SendBridgeMessage(eventJson);
                std::cout << "[+] [PROLOGUE CHECK] Engels Defeated (Prologue Complete)! Sent check 92000006 to Archipelago.\n";
            }
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
}

// DeathLink. The player has two HP fields: the real HP at entity + 0x10668 and a copy at entity + 0x858 that the
// player update (0x428B86) rewrites from it every frame; max HP is at entity + 0x85C (written by the level-up code
// at 0x4289FC from the level table row).
static const uintptr_t PLAYER_HP_OFFSET      = 0x10668;
static const uintptr_t PLAYER_HP_COPY_OFFSET = 0x858;
static const uintptr_t PLAYER_MAX_HP_OFFSET  = 0x85C;
static volatile ULONGLONG g_deathLinkKillTick = 0;  // when a received DeathLink killed the player

static bool ReadPlayerHp(uintptr_t moduleBase, uintptr_t* pEntity, int32_t* pHp, int32_t* pMaxHp)
{
    __try
    {
        const uintptr_t entity = *(uintptr_t*)(moduleBase + 0x1020948);
        if (!entity || IsBadReadPtr((void*)(entity + PLAYER_HP_OFFSET), 8)) return false;
        *pEntity = entity;
        *pHp = *(int32_t*)(entity + PLAYER_HP_OFFSET);
        *pMaxHp = *(int32_t*)(entity + PLAYER_MAX_HP_OFFSET);
        return *pMaxHp > 0 && *pMaxHp <= 1000000 && *pHp >= 0 && *pHp <= *pMaxHp;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    return false;
}

// Player death as the game does it (target of hap::PlayerDieAction, 0x7C6B70): with HP > 0 it zeroes the HP and
// switches the player to its "dead" state (vfunc +0x90, state 0x29). During scripted moments that forbid dying
// (flag 0x4000 at 0x10297F0) it only flags a pending death. Writing the HP alone does not kill: the game puts
// the player back at 1 HP (seen 2026-10-17).
static const uintptr_t PLAYER_DIE_FUNC_RVA = 0x4E62F0;
static volatile bool g_bDeathLinkKillPending = false;

// Called from the bridge thread: the kill itself runs in the hook loop (ProcessDeathLinkKill)
static void KillPlayerFromDeathLink()
{
    g_bDeathLinkKillPending = true;
}

static void ProcessDeathLinkKill(uintptr_t moduleBase)
{
    if (!g_bDeathLinkKillPending || !IsPlayerInGame()) return;
    g_bDeathLinkKillPending = false;

    uintptr_t entity = 0;
    int32_t hp = 0, maxHp = 0;
    if (!ReadPlayerHp(moduleBase, &entity, &hp, &maxHp) || hp <= 0) return;

    __try
    {
        g_deathLinkKillTick = GetTickCount64();
        typedef void(__fastcall* PlayerDie_t)(uintptr_t player);
        ((PlayerDie_t)(moduleBase + PLAYER_DIE_FUNC_RVA))(entity);
        LogEventToFile("[DEATHLINK] killed by a received DeathLink (HP was %d / %d)\n", hp, maxHp);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        LogEventToFile("[DEATHLINK] player die function crashed\n");
    }
}

// Reports the player's death (HP going from > 0 to 0) to the bridge, except deaths caused by a received DeathLink
static void CheckPlayerDeath(uintptr_t moduleBase)
{
    static bool s_wasAlive = false;
    static bool s_killTraced = true;
    if (!IsPlayerInGame())
    {
        s_wasAlive = false;
        return;
    }

    uintptr_t entity = 0;
    int32_t hp = 0, maxHp = 0;
    if (!ReadPlayerHp(moduleBase, &entity, &hp, &maxHp)) return;

    // Trace what the game did with a DeathLink kill (debugging: the player must really die)
    const ULONGLONG sinceKill = GetTickCount64() - g_deathLinkKillTick;
    if (g_deathLinkKillTick && sinceKill < 1500) s_killTraced = false;
    if (!s_killTraced && sinceKill >= 1500)
    {
        s_killTraced = true;
        LogEventToFile("[DEATHLINK] 1.5 s after the kill: HP %d / %d (copy %d)\n", hp, maxHp,
                       *(int32_t*)(entity + PLAYER_HP_COPY_OFFSET));
    }

    if (hp > 0)
    {
        s_wasAlive = true;
        return;
    }
    if (!s_wasAlive) return;
    s_wasAlive = false;

    if (sinceKill < 10000) return;  // our own DeathLink kill: never echo it
    LogEventToFile("[DEATHLINK] player died\n");
    SendBridgeMessage("{\"event\":\"death\"}");
}

// Live story sub-phase (e.g. "51_AB_MainDesert"): the phase manager global at 0xF64A90 holds the current phase
// id, followed by the current sub-phase name at +8 (getters 0x745D40 / 0x12F7A0, used by 0x7A7010). The copy in
// the save (saveBase + 0x395F0) is only refreshed at checkpoints, so it misses most story steps.
static const uintptr_t CURRENT_SUBPHASE_NAME_RVA = 0xF64A98;

// Route keys (Archipelago items): routes B, C and D stay locked until their key is received. The route is the
// first non-numeric token of the live sub-phase ("00_00_B_..." = B, "20_CD_..." = C/D, "340_D_..." = D).
// Entering a locked route sends the player back to the title screen the way the game does it: phase jump
// (0x7610D0) of the phase manager (0x102A020) to phase 0xF00 "START".
static volatile LONG g_routeKeys = 0;  // bit 0 = route B (item "9S"), bits 1-2 = routes C and D (item "A2")
static const uintptr_t PHASE_MANAGER_RVA     = 0x102A020;
static const uintptr_t PHASE_JUMP_FUNC_RVA   = 0x7610D0;  // (manager, phase id, phase name)
static const uintptr_t TITLE_PHASE_NAME_RVA  = 0xCAC904;  // "START"
static const int       TITLE_PHASE_ID        = 0xF00;

// -------------------------------------------------------------
// Chapter Select limited to the chapters reached in this Archipelago run
// -------------------------------------------------------------
// The list comes from ChapterData.cha (pointer at 0x11EA848: +8 = records offset, +0x10 = count; 93 records of 0x50
// bytes in story order: +1 chapter, +2 sub-chapter, +3 variant, +4 route (0 A, 1 B, 2 AB, 3 CD), +0xC phase id,
// +0xE start sub-phase name). Its two accessors are only used by UIChapterSelectLayout when it fills its list
// (0x9126F0), so filtering them filters the menu.
static const uintptr_t CHAPTER_DATA_PTR_RVA     = 0x11EA848;
static const uintptr_t CHAPTER_COUNT_FUNC_RVA   = 0x7DE510;
static const uintptr_t CHAPTER_GET_FUNC_RVA     = 0x7DCF10;
static const uintptr_t TEST_GAME_FLAG_FUNC_RVA  = 0x9CA510;  // flag array at save 0x39514, MSB-first
static const uintptr_t TITLE_MENU_FLAG_RET_RVA  = 0x9B3D4D;  // title menu shows Chapter Select when flag 5 is set
static const int       CHAPTER_RECORD_SIZE      = 0x50;
static const int       CHAPTER_NAME_OFFSET      = 0x0E;
static const int       CHAPTER_NAME_LEN         = 0x20;
enum { CHAPTER_ROUTE_A = 0, CHAPTER_ROUTE_B = 1, CHAPTER_ROUTE_AB = 2, CHAPTER_ROUTE_CD = 3 };

// Reached sub-phases: "<phase id>:<name>" (the same name exists in several phases, e.g. both Pascal village visits),
// or just "<name>" for phases logged before the phase id was recorded
static CRITICAL_SECTION g_csChapters;
static std::set<std::string> g_reachedPhases;
static std::vector<int> g_visibleChapters;  // record indices shown by the menu

typedef int(__fastcall* ChapterCount_t)();
typedef const uint8_t*(__fastcall* ChapterGet_t)(int index);
typedef int(__fastcall* TestGameFlag_t)(int id);
static ChapterCount_t oChapterCount = nullptr;
static ChapterGet_t oChapterGet = nullptr;
static TestGameFlag_t oTestGameFlag = nullptr;

static std::string ChapterRecordName(const uint8_t* rec)
{
    const char* name = (const char*)(rec + CHAPTER_NAME_OFFSET);
    return std::string(name, strnlen(name, CHAPTER_NAME_LEN));
}

static void AddReachedPhase(int phaseId, const char* phase)
{
    char key[96];
    sprintf_s(key, "%d:%s", phaseId, phase);
    EnterCriticalSection(&g_csChapters);
    g_reachedPhases.insert(key);
    LeaveCriticalSection(&g_csChapters);
}

static int __fastcall hkChapterCount()
{
    const int total = oChapterCount();

    // Furthest chapter record reached on each route. AB records count for route A unless only route B was played.
    std::vector<int> reachedRecords;
    std::set<std::string> namesSeen;
    bool playedA = false, playedB = false;
    EnterCriticalSection(&g_csChapters);
    for (int i = 0; i < total; ++i)
    {
        const uint8_t* rec = oChapterGet(i);
        if (!rec) continue;
        const std::string name = ChapterRecordName(rec);
        char key[96];
        sprintf_s(key, "%d:%s", *(const int16_t*)(rec + 0xC), name.c_str());
        // A legacy entry (no phase id) only stands for the first record with that name
        const bool firstWithName = namesSeen.insert(name).second;
        if (g_reachedPhases.count(key) || (firstWithName && g_reachedPhases.count(name)))
        {
            reachedRecords.push_back(i);
            if (rec[4] == CHAPTER_ROUTE_A) playedA = true;
            if (rec[4] == CHAPTER_ROUTE_B) playedB = true;
        }
    }
    const int reachedPhases = (int)g_reachedPhases.size();

    int furthestA = -1, furthestB = -1, furthestCD = -1;
    for (int i : reachedRecords)
    {
        const uint8_t route = oChapterGet(i)[4];
        if (route == CHAPTER_ROUTE_A || (route == CHAPTER_ROUTE_AB && (playedA || !playedB))) furthestA = max(furthestA, i);
        if (route == CHAPTER_ROUTE_B || (route == CHAPTER_ROUTE_AB && playedB)) furthestB = max(furthestB, i);
        if (route == CHAPTER_ROUTE_CD) furthestCD = max(furthestCD, i);
    }

    // Every chapter up to the furthest one reached on its route; the first chapter is always there
    g_visibleChapters.clear();
    for (int i = 0; i < total; ++i)
    {
        const uint8_t* rec = oChapterGet(i);
        if (!rec) continue;
        const uint8_t route = rec[4];
        const bool shown = i == 0
            || (route == CHAPTER_ROUTE_A && i <= furthestA)
            || (route == CHAPTER_ROUTE_B && i <= furthestB)
            || (route == CHAPTER_ROUTE_AB && i <= max(furthestA, furthestB))
            || (route == CHAPTER_ROUTE_CD && i <= furthestCD);
        if (shown) g_visibleChapters.push_back(i);
    }
    const int shownCount = (int)g_visibleChapters.size();
    LeaveCriticalSection(&g_csChapters);

    LogEventToFile("[CHAPTER_SELECT] %d/%d chapters shown (%d phases reached, furthest A %d, B %d, CD %d)\n",
                   shownCount, total, reachedPhases, furthestA, furthestB, furthestCD);
    return shownCount;
}

static const uint8_t* __fastcall hkChapterGet(int index)
{
    EnterCriticalSection(&g_csChapters);
    const int record = (index >= 0 && index < (int)g_visibleChapters.size()) ? g_visibleChapters[index] : index;
    LeaveCriticalSection(&g_csChapters);
    return oChapterGet(record);
}

// The menu draws 11 rows (9 visible) and wraps around the list: with fewer chapters, rows past the end showed
// the first chapters again. 0x95CF80(layout, top) refreshes row k with entry (top - 1 + k) modulo the count; the rows
// that wrapped are hidden (bit 31 of +0x24 = visible, on every UI part of the row) and the list stays at the top.
static const uintptr_t CHAPTER_ROWS_REFRESH_RVA = 0x95CF80;
static const int       CHAPTER_ROWS             = 11;
static const int       CHAPTER_VISIBLE_ROWS     = 9;
static const int       CHAPTER_ROW_MAX_PARTS    = 256;

typedef void(__fastcall* ChapterRowsRefresh_t)(uint8_t* layout, int top);
static ChapterRowsRefresh_t oChapterRowsRefresh = nullptr;
static uint8_t* s_rowsLayout = nullptr;
static bool s_rowHidden[CHAPTER_ROWS];
static int s_rowPartCount[CHAPTER_ROWS];
static uint8_t s_rowPartVisible[CHAPTER_ROWS][CHAPTER_ROW_MAX_PARTS];

// UI parts of row k (layout +0xA0 + k * 0xF0; its UI instance at +0x40 points to the parts: +0xA0 array, +0xB0 count)
static uint8_t* ChapterRowParts(uint8_t* layout, int row, int* count)
{
    uint8_t* instance = *(uint8_t**)(layout + 0xA0 + row * 0xF0 + 0x40 + 8);
    if (!instance || *(int*)(instance + 0x80) != 1) return nullptr;
    *count = (int)min(*(int64_t*)(instance + 0xB0), (int64_t)CHAPTER_ROW_MAX_PARTS);
    return *(uint8_t**)(instance + 0xA0);
}

static void SetChapterRowHidden(uint8_t* layout, int row, bool hide)
{
    if (s_rowHidden[row] == hide) return;
    int count = 0;
    uint8_t* parts = ChapterRowParts(layout, row, &count);
    if (!parts) return;
    if (hide)
    {
        for (int j = 0; j < count; ++j)
        {
            uint32_t* flags = (uint32_t*)(parts + j * 0x4F0 + 0x24);
            s_rowPartVisible[row][j] = (*flags & 0x80000000) ? 1 : 0;
            *flags &= ~0x80000000;
        }
        s_rowPartCount[row] = count;
    }
    else
    {
        for (int j = 0; j < min(count, s_rowPartCount[row]); ++j)
            if (s_rowPartVisible[row][j]) *(uint32_t*)(parts + j * 0x4F0 + 0x24) |= 0x80000000;
    }
    s_rowHidden[row] = hide;
}

static void __fastcall hkChapterRowsRefresh(uint8_t* layout, int top)
{
    __try
    {
        if (layout != s_rowsLayout)  // menu (re)opened: new rows, nothing hidden yet
        {
            s_rowsLayout = layout;
            memset(s_rowHidden, 0, sizeof(s_rowHidden));
        }
        for (int k = 0; k < CHAPTER_ROWS; ++k) SetChapterRowHidden(layout, k, false);

        const int count = *(int*)(layout + 0x6038);
        if (count > 0 && count <= CHAPTER_VISIBLE_ROWS)
        {
            // Everything fits: keep the list at the top, cursor on the same entry
            int* pTop = (int*)(layout + 0x6020);
            int* pCursorRow = (int*)(layout + 0x602C);
            const int selected = ((*pTop + *pCursorRow) % count + count) % count;
            *pTop = 0;
            *pCursorRow = selected;
            top = 0;
        }
        oChapterRowsRefresh(layout, top);

        if (count > 0 && count < CHAPTER_ROWS)
            for (int k = 0; k < CHAPTER_ROWS; ++k)
            {
                const int entry = top - 1 + k;
                if (entry < 0 || entry >= count) SetChapterRowHidden(layout, k, true);
            }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
}

// Character played in the selected chapter (0x8A2B00(layout): 0 = 2B, 1 = 9S, 2 = A2, -2 = still choosing), from
// the record's character mask (+8: 1 = 2B, 2 = 9S, 4 = A2) and the 2B/9S picker. 9S is an Archipelago unlock: until
// it is received (or while offline), a route A/B chapter picked with 9S starts with 2B (routes C/D are behind A2
// and need 9S).
static const uintptr_t CHAPTER_CHARACTER_FUNC_RVA = 0x8A2B00;
typedef int(__fastcall* ChapterCharacter_t)(uint8_t* layout);
static ChapterCharacter_t oChapterCharacter = nullptr;

static int __fastcall hkChapterCharacter(uint8_t* layout)
{
    const int character = oChapterCharacter(layout);
    if (character != 1) return character;
    // Offline (no Archipelago connection) 9S counts as not received, like the chapters past the run's progress
    if (g_routeKeys & 1)
    {
        LogEventToFile("[CHAPTER_SELECT] 9S picked: allowed (9S received)\n");
        return character;
    }
    __try
    {
        const int index = *(int*)(layout + 0x6020) + *(int*)(layout + 0x602C);
        const uint8_t* entry = *(uint8_t**)(layout + 0x3518) + index * 0x54;
        if (entry[4] == CHAPTER_ROUTE_CD || !(*(const uint32_t*)(entry + 8) & 1)) return character;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return character;
    }
    static ULONGLONG s_lastNotice = 0;
    if (GetTickCount64() - s_lastNotice > 3000)
    {
        s_lastNotice = GetTickCount64();
        ArchipelagoUI::AddNotification("9S VERROUILLE", "9S n'est pas encore debloque : le chapitre se lance avec 2B");
        LogEventToFile("[CHAPTER_SELECT] 9S picked without the 9S item -> 2B\n");
    }
    return 0;
}

// The title menu's Chapter Select is always there with the mod (the list itself is filtered above)
static int __fastcall hkTestGameFlag(int id)
{
    if (id == 5 && (uintptr_t)_ReturnAddress() == (uintptr_t)GetModuleHandle(NULL) + TITLE_MENU_FLAG_RET_RVA)
        return 1;
    return oTestGameFlag(id);
}

static void InstallChapterSelectHooks(uintptr_t moduleBase)
{
    InitializeCriticalSection(&g_csChapters);
    struct { uintptr_t rva; LPVOID detour; LPVOID* original; const char* name; } hooks[] = {
        { CHAPTER_COUNT_FUNC_RVA,  (LPVOID)&hkChapterCount, (LPVOID*)&oChapterCount, "ChapterData count" },
        { CHAPTER_GET_FUNC_RVA,    (LPVOID)&hkChapterGet,   (LPVOID*)&oChapterGet,   "ChapterData get" },
        { TEST_GAME_FLAG_FUNC_RVA, (LPVOID)&hkTestGameFlag, (LPVOID*)&oTestGameFlag, "game flag test" },
        { CHAPTER_ROWS_REFRESH_RVA, (LPVOID)&hkChapterRowsRefresh, (LPVOID*)&oChapterRowsRefresh, "Chapter Select rows" },
        { CHAPTER_CHARACTER_FUNC_RVA, (LPVOID)&hkChapterCharacter, (LPVOID*)&oChapterCharacter, "Chapter Select character" },
    };
    for (auto& h : hooks)
    {
        LPVOID target = (LPVOID)(moduleBase + h.rva);
        const MH_STATUS created = MH_CreateHook(target, h.detour, h.original);
        const MH_STATUS enabled = created == MH_OK ? MH_EnableHook(target) : created;
        LogEventToFile("[CHAPTER_SELECT] hook %s: %s\n", h.name, enabled == MH_OK ? "ok" : MH_StatusToString(enabled));
    }
}

static int RouteKeyBitForPhase(const char* phase)
{
    const char* p = phase;
    while (*p)
    {
        size_t len = 0;
        while (p[len] && p[len] != '_') ++len;
        bool numeric = len > 0;
        for (size_t i = 0; i < len; ++i)
            if (!isdigit((unsigned char)p[i])) numeric = false;
        if (!numeric)
        {
            if (len == 1 && p[0] == 'B') return 0;
            if ((len == 2 && p[0] == 'C' && p[1] == 'D') || (len == 1 && p[0] == 'C')) return 1;
            if (len == 1 && p[0] == 'D') return 2;
            return -1;
        }
        p += len;
        if (*p == '_') ++p;
    }
    return -1;
}

static void EnforceRouteKeys(uintptr_t moduleBase, const char* phase)
{
    static ULONGLONG s_lastBlock = 0;
    if (!g_bArchipelagoItemsSynced) return;  // keys not known yet
    const int bit = RouteKeyBitForPhase(phase);
    if (bit < 0 || (g_routeKeys & (1 << bit))) return;

    const ULONGLONG now = GetTickCount64();
    if (now - s_lastBlock < 15000) return;
    s_lastBlock = now;

    static const char* s_routeNames[] = { "B", "C", "D" };
    static const char* s_routeCharacters[] = { "9S", "A2", "A2" };  // the Archipelago item that unlocks the route
    char text[128];
    sprintf_s(text, "Route %s verrouillee : il faut debloquer %s via Archipelago", s_routeNames[bit], s_routeCharacters[bit]);
    ArchipelagoUI::AddNotification("ROUTE VERROUILLEE", text);
    LogEventToFile("[ROUTE_LOCK] %s blocked (no route %s key) -> back to title\n", phase, s_routeNames[bit]);

    __try
    {
        typedef void(__fastcall* PhaseJump_t)(uintptr_t manager, int phaseId, const char* phaseName);
        ((PhaseJump_t)(moduleBase + PHASE_JUMP_FUNC_RVA))(moduleBase + PHASE_MANAGER_RVA, TITLE_PHASE_ID,
                                                          (const char*)(moduleBase + TITLE_PHASE_NAME_RVA));
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        LogEventToFile("[ROUTE_LOCK] title phase jump crashed\n");
    }
}

// Story phase tracking: every change of the current sub-phase is logged and sent to the bridge.
// Phase names carry the route: "_A_", "_B_", "_AB_", "_CD_", "_D_".
static void CheckPhaseChange(uintptr_t moduleBase)
{
    static char s_lastPhase[64] = "";
    if (!IsPlayerInGame()) return;

    __try
    {
        const char* pPhase = (const char*)(moduleBase + CURRENT_SUBPHASE_NAME_RVA);
        if (IsBadReadPtr(pPhase, 64)) return;

        char phase[64];
        int n = 0;
        for (; n < 63 && pPhase[n]; ++n)
        {
            const char c = pPhase[n];
            if (!isalnum((unsigned char)c) && c != '_') return;  // not a phase name (yet)
            phase[n] = c;
        }
        phase[n] = '\0';
        if (n == 0) return;
        EnforceRouteKeys(moduleBase, phase);
        if (strcmp(phase, s_lastPhase) == 0) return;

        // Sub-phase numbers restart in every phase (block of the story), so the phase id tells them apart
        const int phaseId = *(const int*)(moduleBase + CURRENT_SUBPHASE_NAME_RVA - 8);
        LogEventToFile("[PHASE] %s -> %s (phase 0x%X)\n", s_lastPhase[0] ? s_lastPhase : "(start)", phase, phaseId);
        strcpy_s(s_lastPhase, phase);
        AddReachedPhase(phaseId, phase);

        char eventJson[160];
        sprintf_s(eventJson, "{\"event\":\"phase\",\"phase\":\"%s\",\"phase_id\":%d}", phase, phaseId);
        SendBridgeMessage(eventJson);
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
}

bool IsPlayerInGame()
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    __try
    {
        uintptr_t* pPlayerEntityPtr = (uintptr_t*)(moduleBase + 0x1020948);
        if (!pPlayerEntityPtr || !*pPlayerEntityPtr || IsBadReadPtr((void*)*pPlayerEntityPtr, 0x60))
        {
            return false;
        }

        uintptr_t playerEntity = *pPlayerEntityPtr;
        float pX = *(float*)(playerEntity + 0x50);
        float pY = *(float*)(playerEntity + 0x54);
        float pZ = *(float*)(playerEntity + 0x58);
        if (isnan(pX) || isnan(pY) || isnan(pZ))
        {
            return false;
        }

        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

// Resistance Camp shop area (same box as the shop pod purchase detection in hkItemManager_AddItem)
bool IsPlayerInCampShopArea()
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;

    __try
    {
        uintptr_t* pPlayerEntityPtr = (uintptr_t*)(moduleBase + 0x1020948);
        if (!pPlayerEntityPtr || !*pPlayerEntityPtr || IsBadReadPtr((void*)*pPlayerEntityPtr, 0x60))
            return false;

        uintptr_t playerEntity = *pPlayerEntityPtr;
        float pX = *(float*)(playerEntity + 0x50);
        float pY = *(float*)(playerEntity + 0x54);
        float pZ = *(float*)(playerEntity + 0x58);
        return pX >= 10.0f && pX <= 80.0f && pY <= -5.0f && pZ >= -160.0f && pZ <= -90.0f;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}

    return false;
}

void ProcessPendingArchipelagoGrants()
{
    if (!IsPlayerInGame()) return;
    FlushPendingArchipelagoGrants();
}

// -------------------------------------------------------------
// Persistence check: the game wipes the inventory at some story points (end of the prologue...).
// Weapons / pod programs are idempotent, so we simply re-grant the ones that disappeared.
// -------------------------------------------------------------
static bool PlayerOwnsWeapon(int wId)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return true; // unknown -> do not re-grant

    NieRWeaponSlot* slots = (NieRWeaponSlot*)(moduleBase + WEAPONS_OFFSET_START);
    const int totalSlots = (int)((WEAPONS_OFFSET_END - WEAPONS_OFFSET_START) / sizeof(NieRWeaponSlot));
    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)wId) return true;
        }
        return false;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    return true;
}

static bool PlayerOwnsPodProgram(int pId)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return true;

    NieRPodProgramSlot* slots = (NieRPodProgramSlot*)(moduleBase + POD_PROGRAMS_OFFSET_START);
    const int totalSlots = (int)((POD_PROGRAMS_OFFSET_END - POD_PROGRAMS_OFFSET_START) / sizeof(NieRPodProgramSlot));
    __try
    {
        for (int i = 0; i < totalSlots; ++i)
        {
            if (slots[i].id == (uint32_t)pId) return true;
        }
        return false;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {}
    return true;
}

void VerifyPersistentArchipelagoGrants()
{
    if (!IsPlayerInGame()) return;

    EnterCriticalSection(&g_csReconciliation);
    for (auto& pair : g_targetWeapons)
    {
        if (pair.second.granted && !PlayerOwnsWeapon(pair.first) && s_regrantAttempts[pair.first] < 3)
        {
            s_regrantAttempts[pair.first]++;
            pair.second.granted = false;
            std::cout << "[*] [AP Verify] Weapon " << pair.second.name << " (ID " << pair.first << ") missing from inventory -> re-granting.\n";
        }
    }
    for (auto& pair : g_targetPodPrograms)
    {
        int key = 100000 + pair.first;
        if (pair.second.granted && !PlayerOwnsPodProgram(pair.first) && s_regrantAttempts[key] < 3)
        {
            s_regrantAttempts[key]++;
            pair.second.granted = false;
            std::cout << "[*] [AP Verify] Pod Program " << pair.second.name << " (ID " << pair.first << ") missing -> re-granting.\n";
        }
    }
    for (auto& pair : g_targetItems)
    {
        int itemId = pair.first;
        if (itemId >= 3000 && itemId < 3400) // Chips
        {
            int curChips = GetPlayerChipCount(itemId);
            int targetChips = (pair.second.totalCount > 0) ? pair.second.totalCount : (pair.second.targetQuantity > 0 ? pair.second.targetQuantity : 1);
            if (curChips < targetChips && s_regrantAttempts[itemId] < 3)
            {
                s_regrantAttempts[itemId]++;
                pair.second.targetQuantity = targetChips - curChips;
                pair.second.granted = false;
                std::cout << "[*] [AP Verify] Chip " << pair.second.name << " (ID " << itemId << ") missing (" << curChips << "/" << targetChips << ") -> re-granting.\n";
            }
        }
    }
    LeaveCriticalSection(&g_csReconciliation);

    FlushPendingArchipelagoGrants();
}

// Tells the bridge that everything it sent us up to the last commit marker is really in the
// inventory (so it can persist its 'received items index' and never re-give consumables).
static void ReportGrantsIdleIfNeeded()
{
    if (!g_bCommitDirty) return;
    if (!IsPlayerInGame()) return;

    FlushPendingArchipelagoGrants();
    if (HasPendingArchipelagoGrants()) return;

    InterlockedExchange(&g_bCommitDirty, 0);
    LONG idx = g_iCommitMarker;
    if (HasPendingArchipelagoGrants())
    {
        InterlockedExchange(&g_bCommitDirty, 1);
        return;
    }

    char buf[96];
    sprintf_s(buf, "{\"event\":\"grants_idle\",\"index\":%ld}", (long)idx);
    SendBridgeMessage(buf);
}

// -------------------------------------------------------------
// Active Slot Tracking (Streamed via RAM snapshots & YoRHa UI)
// -------------------------------------------------------------
static int g_lastActiveSlot = -1;

// -------------------------------------------------------------
// Live save snapshot: the save structure lives in RAM (same layout as SlotData_*.dat, but the RAM copy
// starts 4 bytes later: file offset X == SAVE_DATA_BASE_RVA + X - 4, verified 2026-10-17).
// We stream its interesting parts to the bridge when they change so that checks which are
// derived from the save (quests, terminals, bosses, endings, storage) can be validated
// without the player having to save manually.
// -------------------------------------------------------------
static const size_t SAVE_HEAD_SIZE  = 0x7C;
static const size_t SAVE_TEXT_MAX   = 0x30000 - 0x7C;
static const size_t SAVE_CAP_OFFSET = 0x324B8; // file offset: number of "Storage +8" upgrades bought

static std::string Base64Encode(const unsigned char* data, size_t len)
{
    static const char* tbl = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve(((len + 2) / 3) * 4);
    for (size_t i = 0; i < len; i += 3)
    {
        uint32_t v = (uint32_t)data[i] << 16;
        if (i + 1 < len) v |= (uint32_t)data[i + 1] << 8;
        if (i + 2 < len) v |= (uint32_t)data[i + 2];
        out += tbl[(v >> 18) & 63];
        out += tbl[(v >> 12) & 63];
        out += (i + 1 < len) ? tbl[(v >> 6) & 63] : '=';
        out += (i + 2 < len) ? tbl[v & 63] : '=';
    }
    return out;
}

// No C++ objects with destructors here so that __try is allowed.
static bool CaptureSaveSnapshot(unsigned char* head, unsigned char* text, size_t& textLen, uint32_t& cap, uint64_t& hash)
{
    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    if (!moduleBase) return false;
    // -4 so that the snapshot uses SlotData_*.dat file offsets, which is what the bridge parses
    const unsigned char* p = (const unsigned char*)(moduleBase + SAVE_DATA_BASE_RVA - 4);

    __try
    {
        if (IsBadReadPtr(p, SAVE_CAP_OFFSET + 4)) return false;

        memcpy(head, p, SAVE_HEAD_SIZE);
        textLen = 0;
        while (textLen < SAVE_TEXT_MAX && p[SAVE_HEAD_SIZE + textLen] != 0) ++textLen;
        memcpy(text, p + SAVE_HEAD_SIZE, textLen);
        memcpy(&cap, p + SAVE_CAP_OFFSET, 4);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return false;
    }

    uint64_t h = 1469598103934665603ULL; // FNV-1a
    for (size_t i = 0; i < SAVE_HEAD_SIZE; ++i) { h ^= head[i]; h *= 1099511628211ULL; }
    for (size_t i = 0; i < textLen; ++i)        { h ^= text[i]; h *= 1099511628211ULL; }
    for (int i = 0; i < 4; ++i)                 { h ^= (unsigned char)((cap >> (8 * i)) & 0xFF); h *= 1099511628211ULL; }
    hash = h;
    return true;
}

static void PublishLiveSaveSnapshot()
{
    if (!IsBridgeConnected()) return;

    static unsigned char s_head[SAVE_HEAD_SIZE];
    static unsigned char s_text[SAVE_TEXT_MAX];
    static uint64_t s_lastHash = 0;

    size_t textLen = 0;
    uint32_t cap = 0;
    uint64_t hash = 0;
    if (!CaptureSaveSnapshot(s_head, s_text, textLen, cap, hash)) return;
    if (hash == s_lastHash) return;
    s_lastHash = hash;

    char szPlayerName[64] = { 0 };
    WideCharToMultiByte(CP_UTF8, 0, (LPCWCH)(s_head + 0x34), -1, szPlayerName, sizeof(szPlayerName) - 1, NULL, NULL);

    // If player name is empty, game has not loaded a save file yet
    if (szPlayerName[0] == '\0') return;

    strcpy_s(ArchipelagoUI::s_szActivePlayer, szPlayerName);
    ArchipelagoUI::s_iActiveSlot = g_lastActiveSlot;

    std::string msg = "{\"event\":\"save_snapshot\",\"active_slot\":";
    msg += std::to_string(g_lastActiveSlot);
    msg += ",\"player_name\":\"";
    msg += szPlayerName;
    msg += "\",\"head\":\"";
    msg += Base64Encode(s_head, SAVE_HEAD_SIZE);
    msg += "\",\"blob\":\"";
    msg += Base64Encode(s_text, textLen);
    msg += "\",\"cap\":";
    msg += std::to_string((unsigned long)cap);
    msg += "}";
    SendBridgeMessage(msg.c_str());
}



static void LogEventToFile(const char* fmt, ...)
{
    // Relative to the game's working directory (NieRAutomata\data)
    FILE* f = _fsopen("archipelago_events.log", "a", _SH_DENYNO);
    if (f)
    {
        va_list args;
        va_start(args, fmt);
        vfprintf(f, fmt, args);
        va_end(args);
        fclose(f);
    }
}

// NOTE: the former GPS-based "respawn blocker" (archipelago_collected_nodes.txt) was removed on
// purpose. Only reliable checks are tracked now (weapons, 9S hacking chests, shop one-timers and
// the save-backed checks), so there is no need to remember which world nodes were opened.

// -------------------------------------------------------------
// Known Chest GPS Database (Filters Chests vs Random Ground Clutter)
// -------------------------------------------------------------
struct ChestGPS
{
    float x;
    float y;
    float z;
    float radius;
    int id;
};

static const ChestGPS g_knownChests[] = {
    // Abandoned Factory (Usine Désaffectée)
    { 248.38f, 10.48f, 672.52f, 25.0f, 92000001 }, // Factory: Hidden Catwalk Chest (Type-4O Fists)
    { 215.0f, 25.0f, 630.0f, 30.0f, 92000002 },   // Factory: Silo Gantry Chest
    { 180.0f, 5.0f, 710.0f, 30.0f, 92000003 },    // Factory: Crane Area High Chest
    { 230.0f, 15.0f, 650.0f, 30.0f, 92000004 },   // Factory: Small Biped Ambush Chest
    { 260.0f, 30.0f, 600.0f, 30.0f, 92000007 },   // Factory: Rooftop Escape Route Chest
    { 210.0f, -10.0f, 580.0f, 30.0f, 92000008 },  // Factory: Furnace Catwalk Chest
    { 195.0f, -5.0f, 560.0f, 30.0f, 92000009 },   // Factory: Molten Metal Vat High Crate
    { 150.0f, -40.0f, 480.0f, 30.0f, 92000010 },  // Factory Underground: Conveyor Belt Chest
    { 130.0f, -50.0f, 450.0f, 30.0f, 92000011 },  // Factory Underground: Crusher Room Alcove
    { 110.0f, -60.0f, 400.0f, 30.0f, 92000012 },  // Factory Underground: Cult Sanctuary Altar
    { 140.0f, -45.0f, 430.0f, 30.0f, 92000014 },  // Factory Underground: Escape Hatch Crate
    { 270.0f, 20.0f, 520.0f, 30.0f, 92000015 },   // Factory: Secret Pipe Access Chest (Engine Blade)

    // City Ruins (Cité en Ruines)
    { -286.33f, 12.88f, -42.50f, 25.0f, 92000020 },  // City Ruins: Highway Overpass Chest
    { -110.0f, 45.0f, -85.0f, 35.0f, 92000021 },     // City Ruins: Building Rooftop Chest (Beastlord)
    { -368.50f, -29.03f, -93.82f, 30.0f, 92000022 }, // City Ruins: Giga Crater Rim Chest (Verified)
    { -417.57f, -1.20f, -208.47f, 30.0f, 92000023 }, // City Ruins: Desert Pipe Entrance Chest (Verified)
    { -320.0f, 10.0f, -150.0f, 30.0f, 92000025 },    // City Ruins: Sunken Building Balcony
    { -350.0f, 5.0f, -180.0f, 30.0f, 92000026 },     // City Ruins: Water Pipe Bridge Crate
    { -250.0f, -10.0f, -80.0f, 30.0f, 92000027 },    // City Ruins: Derelict Truck Cargo Chest
    { -382.45f, -22.14f, -121.33f, 30.0f, 92000032 },// City Ruins: Center Crater Deep Tunnel Chest (Verified)
    { -298.11f, -25.16f, -20.28f, 30.0f, 92000034 }, // City Ruins: Desert Trench Ledge Chest (Verified)
    { -180.0f, 15.0f, -350.0f, 30.0f, 92000035 },    // City Ruins: Shopping Mall Atrium Chest
    { -160.0f, 20.0f, -370.0f, 30.0f, 92000036 },    // City Ruins: Shopping Mall Broken Escalator Crate

    // Resistance Camp (Camp de la Résistance)
    { 35.0f, -15.0f, -120.0f, 35.0f, 92000050 },     // Resistance Camp: Anemone Supply Crate
    { 25.0f, -15.0f, -130.0f, 30.0f, 92000052 },     // Resistance Camp: Supply Trader Crate
    { 50.0f, -15.0f, -125.0f, 30.0f, 92000053 },     // Resistance Camp: Maintenance Shop Jukebox Chest
    { 60.0f, -15.0f, -140.0f, 30.0f, 92000054 },     // Resistance Camp: Back Alley Storage Crate
    { -314.65f, -24.92f, -33.42f, 30.0f, 92000055 }, // Resistance Camp: Storage Area High Ledge Chest (Verified)

    // Desert Zone (Zone du Désert) - In-game Z is positive (+180 to +650)
    { -554.86f, 35.80f,  277.31f, 35.0f, 92000060 }, // Desert: Oil Field Derelict Chest (Verified)
    { -573.32f, 22.45f,  374.11f, 35.0f, 92000071 }, // Desert: Oil Field Broken Crane Chest (Verified)
    { -458.03f, 60.15f,  179.89f, 35.0f, 92000072 }, // Desert: Sand River Rock Tunnel Chest (Verified)
    { -648.48f, 0.81f,   474.62f, 40.0f, 92000062 }, // Desert: Housing Complex Balcony Chest (Verified)
    { -750.0f,  -20.0f,  600.0f,  40.0f, 92000061 }, // Desert: Oasis Hidden Chest
    { -800.0f,  -5.0f,   480.0f,  40.0f, 92000064 }, // Desert: North Dunes Sandfall Chest
    { -700.0f,  -15.0f,  550.0f,  40.0f, 92000065 }, // Desert: Center Storm Rock Formation Chest
    { -740.0f,  -60.0f,  610.0f,  40.0f, 92000067 }, // Desert: Underground Cavern Deep Tomb Chest
    { -630.0f,  5.0f,    510.0f,  40.0f, 92000068 }, // Desert: Housing Complex Center Courtyard Crate
    { -620.0f,  30.0f,   500.0f,  40.0f, 92000069 }, // Desert: Housing Complex Rooftop Escape Chest
    { -640.0f,  10.0f,   515.0f,  40.0f, 92000070 }, // Desert: Housing Complex Secret Stairwell Chest
    { -710.0f,  -25.0f,  570.0f,  40.0f, 92000073 }, // Desert: Ancient Ruin Foundation Crate

    // Amusement Park (Parc d'Attractions)
    { 600.0f, 10.0f, 100.0f, 35.0f, 92000080 }, // Amusement Park: Entrance Courtyard Chest
    { 650.0f, 35.0f, 150.0f, 35.0f, 92000081 }, // Amusement Park: Rollercoaster Rails Chest
    { 720.0f, 15.0f, 220.0f, 35.0f, 92000082 }, // Amusement Park: Theater Backstage Chest
    { 620.0f, 12.0f, 120.0f, 35.0f, 92000084 }, // Amusement Park: Main Street Souvenir Shop Crate
    { 640.0f, 25.0f, 130.0f, 35.0f, 92000085 }, // Amusement Park: Rocket Ride Platform Chest
    { 680.0f, 15.0f, 180.0f, 35.0f, 92000086 }, // Amusement Park: Alleyway Behind Ferris Wheel Chest
    { 750.0f, 5.0f, 260.0f, 35.0f, 92000087 },  // Amusement Park: Castle Bridge Lower Arch Chest
    { 580.0f, -10.0f, 80.0f, 35.0f, 92000088 },  // Amusement Park: Underground Sewer Drain Crate
    { 710.0f, 15.0f, 210.0f, 35.0f, 92000089 }, // Amusement Park: Dressing Room Vanity Chest
    { 730.0f, 25.0f, 230.0f, 35.0f, 92000090 }, // Amusement Park: Theater Balcony Secret Chest

    // Pascal's Village (Village de Pascal)
    { 450.0f, 30.0f, -200.0f, 30.0f, 92000101 }, // Pascal's Village: High Hut Rooftop Chest
    { 480.0f, 15.0f, -180.0f, 30.0f, 92000102 }, // Pascal's Village: Forest Gate Chest
    { 460.0f, 10.0f, -190.0f, 30.0f, 92000104 }, // Pascal's Village: Storage Barrel Alcove Crate
    { 440.0f, 20.0f, -210.0f, 30.0f, 92000105 }, // Pascal's Village: Tree Branch Walkway Chest
    { 470.0f, 40.0f, -170.0f, 30.0f, 92000106 }, // Pascal's Village: High Platform Windmill Chest

    // Forest Kingdom (Royaume de la Forêt)
    { 800.0f, -20.0f, -400.0f, 35.0f, 92000120 }, // Forest: Waterfall Chasm Chest
    { 1050.0f, 45.0f, -600.0f, 35.0f, 92000121 }, // Forest: Castle Throne Room Chest
    { 830.0f, -15.0f, -420.0f, 35.0f, 92000123 }, // Forest: Riverbed Stone Pillars Chest
    { 870.0f, 5.0f, -450.0f, 35.0f, 92000124 },   // Forest: Animal Meadow Tree Trunk Crate
    { 850.0f, -30.0f, -430.0f, 35.0f, 92000125 }, // Forest: Sunken Ravine Ruined Bridge Chest
    { 920.0f, 20.0f, -500.0f, 35.0f, 92000127 },  // Forest: Castle Gate Drawbridge Ledge Chest
    { 960.0f, 25.0f, -530.0f, 35.0f, 92000128 },  // Forest: Castle 1F Courtyard Ramparts Chest
    { 990.0f, 35.0f, -550.0f, 35.0f, 92000129 },  // Forest: Castle 2F Royal Armory Crate
    { 1010.0f, 40.0f, -570.0f, 35.0f, 92000130 }, // Forest: Castle 3F Broken Window Alcove Chest
    { 1030.0f, 50.0f, -580.0f, 35.0f, 92000131 }, // Forest: Castle Library Top Shelf Chest
    { 1060.0f, 45.0f, -610.0f, 35.0f, 92000132 }, // Forest: Castle King's Cradle Secret Chest
    { 940.0f, 15.0f, -510.0f, 35.0f, 92000133 },  // Forest: Castle Exterior Cliffside Path Chest

    // Flooded City (Cité Submergée)
    { -100.0f, -20.0f, 400.0f, 35.0f, 92000150 }, // Flooded City: Submerged Highway Chest
    { -150.0f, -15.0f, 480.0f, 35.0f, 92000151 }, // Flooded City: Missile Launch Area Chest
    { -120.0f, 25.0f, 430.0f, 35.0f, 92000153 },  // Flooded City: Tilted High-Rise 1 Roof Chest
    { -130.0f, 15.0f, 450.0f, 35.0f, 92000154 },  // Flooded City: Tilted High-Rise 2 Balcony Chest
    { -180.0f, -25.0f, 510.0f, 35.0f, 92000155 }, // Flooded City: Sunken Pier Half-Submerged Crate
    { -80.0f, -15.0f, 380.0f, 35.0f, 92000157 },  // Flooded City: Pipe Drain Outfall Chest
    { -220.0f, -10.0f, 550.0f, 35.0f, 92000158 }, // Flooded City: Carrier Flight Deck Crate
    { -140.0f, 40.0f, 460.0f, 35.0f, 92000163 },  // Flooded City: High Crane Overlook Chest

    // Copied City & Emil (Cité Dupliquée & Émile)
    { 0.0f, -100.0f, -800.0f, 40.0f, 92000170 },   // Copied City: Monolith Plaza Entrance Chest
    { 20.0f, -100.0f, -830.0f, 40.0f, 92000171 },  // Copied City: Crystalline Pillar Alcove Crate
    { -20.0f, -90.0f, -850.0f, 40.0f, 92000173 },  // Copied City: White Marble Ledge Chest
    { -420.0f, -120.0f, -150.0f, 35.0f, 92000175 },// Emil's Grotto: Deep Cave Elevator Chest
    { -450.0f, -150.0f, -180.0f, 35.0f, 92000176 } // Emil's Residence: Mask Collection Chest
};

static bool IsNearChestLocation(float x, float y, float z)
{
    for (const auto& c : g_knownChests)
    {
        float dx = x - c.x;
        float dy = y - c.y;
        float dz = z - c.z;
        if ((dx * dx + dy * dy + dz * dz) <= (c.radius * c.radius))
            return true;
    }
    return false;
}

// -------------------------------------------------------------
// Weapon Inventory Tracker (Catches Weapon Chests & Hacking Chests)
// -------------------------------------------------------------
static bool g_bWeaponTrackerInitialized = false;

static void CheckWeaponInventoryChanges(uintptr_t moduleBase)
{
    // Deprecated: All weapon pickups, chests, and rewards are now intercepted
    // safely in real-time by hkItemManager_AddItem without polling or deleting memory.
}

// -------------------------------------------------------------
// Item Acquisition Hook (Detects Pickups, Chests, Quest Items)
// -------------------------------------------------------------
static bool hkItemManager_AddItem(void* pThis, int item_id, int iQuantity)
{
    __try
    {
        // Dynamically capture the engine's true Player Inventory pointer
        if (pThis)
        {
            g_bInventoryCaptured = true;
            if (pThis != g_pInventoryManager)
            {
                g_pInventoryManager = pThis;
                std::cout << "[+] Captured True Player Inventory Pointer: 0x"
                          << std::hex << (uintptr_t)g_pInventoryManager << std::dec << "\n";
                FlushPendingArchipelagoGrants();
            }
        }

        void* caller = _ReturnAddress();
        uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
        uintptr_t rva = (uintptr_t)caller - moduleBase;

        // 1. Ignore item consumption/removal/cleanup (negative or zero quantities)
        if (iQuantity <= 0)
        {
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }

        // 2. Ignore save file loading and internal inventory resets (+0x31df78, +0x150bed)
        bool isSaveLoadCaller = (rva == 0x31df78 || rva == 0x150bed || (rva >= 0x150a00 && rva <= 0x151200));
        if (isSaveLoadCaller)
        {
            SanitizePlayerWeaponsAndHUD();
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }

        // 3. If Archipelago is giving an item, grant it to inventory directly
        if (g_bIsGivingArchipelagoItem)
        {
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }

        // Capture Call Stack (up to 8 frames) to distinguish Chest vs Ground vs Enemy loot
        void* stackFrames[8] = { 0 };
        USHORT frameCount = RtlCaptureStackBackTrace(0, 8, stackFrames, NULL);

        // Capture Player Coordinates (GPS) safely
        float pX = 0.0f, pY = 0.0f, pZ = 0.0f;
        bool hasPos = false;
        uintptr_t* pPlayerEntityPtr = (uintptr_t*)(moduleBase + 0x1020948);
        if (pPlayerEntityPtr && *pPlayerEntityPtr && !IsBadReadPtr((void*)*pPlayerEntityPtr, 0x60))
        {
            uintptr_t playerEntity = *pPlayerEntityPtr;
            pX = *(float*)(playerEntity + 0x50);
            pY = *(float*)(playerEntity + 0x54);
            pZ = *(float*)(playerEntity + 0x58);
            hasPos = true;
        }

        // Determine source type of this acquisition
        bool isHackingChest = (rva == 0x800573 || (frameCount > 1 && ((uintptr_t)stackFrames[1] - moduleBase == 0x7ca45f)));
        bool isNormalChest  = (rva == 0x80032d);
        bool isMobDrop      = (rva == 0x7da8aa);
        bool isGroundPickup = (rva == 0x898b42);
        // Shop pod program purchases must occur when buying from the Resistance Camp merchant
        // Every pod program is a check wherever it comes from: 6 are sold (Camp / Bunker maintenance shops),
        // the others are quest rewards or found in dead pods. R010 Laser (prologue) is checked separately.
        bool isShopPodPurchase = IsPodProgramId(item_id) &&
                                 (rva != 0x328840) && // Exclude engine pod slot initialization
                                 (item_id != 2001);   // Exclude starter program R010 Laser

        bool isWeapon = (item_id >= 1000 && item_id <= 1999);
        // Dress Module (980) / Heavy Armor A-B (981, 982): send a check but the player keeps the item
        bool isKeyModule = (item_id >= 980 && item_id <= 982);
        bool isOneTimeShopItem = (isWeapon && hasPos && (pX >= 10.0f && pX <= 80.0f)) || // Camp Weaponsmith
                                 isShopPodPurchase ||
                                 isKeyModule;

        const char* name = isWeapon ? GetWeaponName(item_id) : GetItemName(item_id);

        // Fishing (8001..8041: fish, machine fish, junk): each species caught with the rod (fishing routine
        // 0x629000) is a check and the catch is replaced by the Archipelago item. Fish from other sources
        // (Jackass's mackerel for ending K, quest rewards) pass through untouched. While the bridge is not
        // connected the catch is kept, so the bridge can still send its check from the save inventory later.
        const bool isFishingCatch = (item_id >= 8001 && item_id <= 8041 && rva == 0x629000);
        if (item_id >= 8001 && item_id <= 8041 && !isFishingCatch)
        {
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }
        if (isFishingCatch)
        {
            g_totalInterceptedChecks++;
            LogEventToFile("[CHECK_INTERCEPTED #%d] Type: FISH | Item: %s (ID %d) x%d | RVA: +0x%llX | Stack1: +0x%llX | GPS: (%.2f, %.2f, %.2f)\n",
                           g_totalInterceptedChecks, name, item_id, iQuantity, (unsigned long long)rva,
                           (unsigned long long)(frameCount > 1 ? ((uintptr_t)stackFrames[1] - moduleBase) : 0),
                           pX, pY, pZ);
            char eventJson[256];
            sprintf_s(eventJson,
                      "{\"event\":\"check\",\"check_num\":%d,\"type\":\"FISH\",\"item_id\":%d,\"quantity\":%d,\"caller_rva\":\"0x%llx\",\"name\":\"%s\"}",
                      g_totalInterceptedChecks, item_id, iQuantity, (unsigned long long)rva, name);
            SendBridgeMessage(eventJson);
            if (g_bInterceptMode && g_bBridgeConnected)
                return true;  // the catch is replaced by the Archipelago item of this location
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }

        // 1. If it is NOT a hacking chest, NOT a one-time shop item, and NOT a weapon:
        if (!isHackingChest && !isOneTimeShopItem && !isWeapon)
        {
            // Quest Items (100..499), Crafting/Quest Materials (500..999), and Fish/Bait (50..99)
            // MUST ALWAYS BE ADDED TO INVENTORY so sidequests, story progression, and upgrades can be completed!
            bool isQuestOrProgressionItem = (item_id >= 50 && item_id < 1000);

            // Plug-in chips found in the world (enemy drops, which are picked up through 0x80032D like chest
            // contents, and chests) are blocked: chips come from Archipelago, granted straight into the chip table.
            if (g_bBlockGroundLoot && item_id >= 3000 && item_id < 3400 && (isNormalChest || isMobDrop || isGroundPickup))
            {
                LogEventToFile("[BLOCKED_WORLD_CHIP] %s (ID %d) at RVA +0x%llX (GPS: %.2f, %.2f, %.2f)\n",
                               name, item_id, (unsigned long long)rva, pX, pY, pZ);
                return true;
            }

            // Normal wooden chests (0x80032D) are placed throughout the world.
            // Their contents (materials, chips, potions) should pass through to the player.
            if (isQuestOrProgressionItem || isNormalChest)
            {
                LogEventToFile("[PASS_THROUGH] %s: %s (ID %d) x%d at RVA +0x%llX (GPS: %.2f, %.2f, %.2f)\n",
                               isNormalChest ? "NORMAL_CHEST" : (isGroundPickup ? "QUEST_GROUND_ITEM" : (isMobDrop ? "QUEST_MOB_DROP" : "GAME_REWARD")),
                               name, item_id, iQuantity, (unsigned long long)rva, pX, pY, pZ);
                return oItemManager_AddItem(pThis, item_id, iQuantity);
            }

            // Only block generic consumables (healing/buffs: IDs 0..49) and mob chip drops (IDs 3000..3399)
            // if the player specifically enabled "Bloquer le loot au sol & drops de monstres"
            if (g_bBlockGroundLoot && (isGroundPickup || isMobDrop))
            {
                LogEventToFile("[BLOCKED_GROUND_LOOT] %s (ID %d) at RVA +0x%llX (GPS: %.2f, %.2f, %.2f)\n",
                               name, item_id, (unsigned long long)rva, pX, pY, pZ);
                return true; // Drop generic consumable/mob chip clutter without adding to inventory
            }

            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }

        // 3. It's a REAL (reliable) CHECK: hacking chest, weapon, or one-time shop item.
        // No GPS-based "already opened" memory anymore: Archipelago itself ignores locations that
        // are already checked, and the bridge debounces duplicate events.

        // All world chests (normal chests 0x80032d & hacking chests 0x800573) and one-time shop purchases are Archipelago Checks!
        const char* typeStr = isWeapon ? "WEAPON_CHEST" : (isOneTimeShopItem ? "SHOP_PURCHASE" : (isHackingChest ? "HACKING_CHEST" : "CHEST"));
        g_totalInterceptedChecks++;


        LogEventToFile("[CHECK_INTERCEPTED #%d] Type: %s | Item: %s (ID %d) x%d | RVA: +0x%llX | Stack1: +0x%llX | GPS: (%.2f, %.2f, %.2f)\n",
                       g_totalInterceptedChecks, typeStr, name, item_id, iQuantity,
                       (unsigned long long)rva,
                       (unsigned long long)(frameCount > 1 ? ((uintptr_t)stackFrames[1] - moduleBase) : 0),
                       pX, pY, pZ);

        std::cout << "\n=========================================================\n";
        std::cout << " [EVENT DETECTED #" << g_totalInterceptedChecks << "] Item Acquired In-Game!\n";
        std::cout << "  Type: " << typeStr << "\n";
        std::cout << "  Item: " << name << " (ID: " << item_id << " / 0x" << std::hex << item_id << std::dec << ")\n";
        std::cout << "  Count: " << iQuantity << "\n";
        std::cout << "  Immediate Caller RVA: +0x" << std::hex << rva << std::dec << "\n";
        std::cout << "  Call Stack in NieRAutomata.exe:\n";

        char stackJson[256] = "[";
        bool firstFrame = true;
        for (USHORT i = 0; i < frameCount; ++i)
        {
            uintptr_t frameRva = (uintptr_t)stackFrames[i] - moduleBase;
            if (frameRva < 0x2000000) // Within main game executable
            {
                std::cout << "    Frame [" << i << "]: +0x" << std::hex << frameRva << std::dec;
                if (i == 0) std::cout << " (Immediate Caller)";
                else if (i == 1) std::cout << " (Parent Routine)";
                else if (i == 2) std::cout << " (Grandparent Routine)";
                std::cout << "\n";

                char frameBuf[32];
                sprintf_s(frameBuf, "%s\"0x%llx\"", firstFrame ? "" : ",", (unsigned long long)frameRva);
                strcat_s(stackJson, frameBuf);
                firstFrame = false;
            }
        }
        strcat_s(stackJson, "]");

        if (hasPos)
        {
            std::cout << "  Player GPS (X, Y, Z): (" << pX << ", " << pY << ", " << pZ << ")\n";
        }

        // Broadcast to Archipelago Python Client via TCP
        char eventJson[1024];
        if (hasPos)
        {
            sprintf_s(eventJson,
                      "{\"event\":\"check\",\"check_num\":%d,\"type\":\"%s\",\"item_id\":%d,\"quantity\":%d,\"caller_rva\":\"0x%llx\",\"name\":\"%s\",\"call_stack\":%s,\"pos\":{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f}}",
                      g_totalInterceptedChecks, typeStr, item_id, iQuantity, (unsigned long long)rva, name, stackJson, pX, pY, pZ);
        }
        else
        {
            sprintf_s(eventJson,
                      "{\"event\":\"check\",\"check_num\":%d,\"type\":\"%s\",\"item_id\":%d,\"quantity\":%d,\"caller_rva\":\"0x%llx\",\"name\":\"%s\",\"call_stack\":%s}",
                      g_totalInterceptedChecks, typeStr, item_id, iQuantity, (unsigned long long)rva, name, stackJson);
        }
        SendBridgeMessage(eventJson);

        if (g_bInterceptMode && !isKeyModule)
        {
            std::cout << "  -> Action: [ARCHIPELAGO MODE ACTIVE]\n";
            std::cout << "     * Chest Location Check Sent to MultiWorld!\n";
            std::cout << "     * Vanilla Chest Item BLOCKED (Will be granted via AP).\n";
            std::cout << "=========================================================\n\n";
            return true;
        }
        else
        {
            std::cout << "  -> Action: Normal Vanilla Pass-Through\n";
            std::cout << "=========================================================\n\n";
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        std::cerr << "[-] Exception prevented in hkItemManager_AddItem!\n";
        if (oItemManager_AddItem)
            return oItemManager_AddItem(pThis, item_id, iQuantity);
        return false;
    }
}

// -------------------------------------------------------------
// Archipelago TCP Server Thread (Listens on 127.0.0.1:52140)
// -------------------------------------------------------------
// Minimal JSON field readers for the one-line commands sent by the bridge (strings never contain
// escaped quotes: the bridge strips them). "key": "value" -> value, "key": 12 -> "12".
static std::string JsonStringField(const std::string& line, const char* key)
{
    std::string pattern = std::string("\"") + key + "\":";
    size_t pos = line.find(pattern);
    if (pos == std::string::npos) return "";
    size_t q1 = line.find('"', pos + pattern.size());
    size_t q2 = (q1 != std::string::npos) ? line.find('"', q1 + 1) : std::string::npos;
    if (q1 == std::string::npos || q2 == std::string::npos) return "";
    return line.substr(q1 + 1, q2 - q1 - 1);
}

static std::string JsonRawField(const std::string& line, const char* key)
{
    std::string pattern = std::string("\"") + key + "\":";
    size_t pos = line.find(pattern);
    if (pos == std::string::npos) return "";
    size_t start = line.find_first_not_of(' ', pos + pattern.size());
    if (start == std::string::npos) return "";
    size_t end = line.find_first_of(",}", start);
    return line.substr(start, (end == std::string::npos ? line.size() : end) - start);
}

static DWORD WINAPI BridgeServerThread(LPVOID lpParam)
{
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
    {
        std::cerr << "[-] [Bridge] WSAStartup failed.\n";
        return 1;
    }

    g_serverSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (g_serverSocket == INVALID_SOCKET)
    {
        std::cerr << "[-] [Bridge] Socket creation failed.\n";
        WSACleanup();
        return 1;
    }

    BOOL opt = TRUE;
    setsockopt(g_serverSocket, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));

    sockaddr_in serverAddr{};
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(52140);
    serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");

    if (bind(g_serverSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR)
    {
        std::cerr << "[-] [Bridge] Bind to 127.0.0.1:52140 failed.\n";
        closesocket(g_serverSocket);
        WSACleanup();
        return 1;
    }

    if (listen(g_serverSocket, 1) == SOCKET_ERROR)
    {
        std::cerr << "[-] [Bridge] Listen failed.\n";
        closesocket(g_serverSocket);
        WSACleanup();
        return 1;
    }

    std::cout << "[+] [Bridge Server] Listening on 127.0.0.1:52140 for Python Client...\n";
    LaunchPythonBridge();

    while (true)
    {
        sockaddr_in clientAddr{};
        int clientLen = sizeof(clientAddr);
        SOCKET newClient = accept(g_serverSocket, (sockaddr*)&clientAddr, &clientLen);
        if (newClient == INVALID_SOCKET)
        {
            Sleep(500);
            continue;
        }

        EnterCriticalSection(&g_csSocket);
        if (g_clientSocket != INVALID_SOCKET)
        {
            closesocket(g_clientSocket);
        }
        g_clientSocket = newClient;
        g_bBridgeConnected = true;
        LeaveCriticalSection(&g_csSocket);

        std::cout << "\n=========================================================\n";
        std::cout << " [+] [Bridge Server] Python Archipelago Client CONNECTED!\n";
        std::cout << "=========================================================\n\n";

        // Send handshake
        SendBridgeMessage("{\"event\":\"handshake\",\"game\":\"NieR:Automata\",\"version\":\"0.1.0-prebeta\"}");

        // If there was a pending connect request, send it immediately
        EnterCriticalSection(&g_csSocket);
        if (g_bPendingConnect)
        {
            char cmd[512];
            sprintf_s(cmd, "{\"cmd\":\"ap_connect_request\",\"server\":\"%s\",\"slot\":\"%s\",\"password\":\"%s\"}",
                      g_szPendingServer, g_szPendingSlot, g_szPendingPassword);
            send(g_clientSocket, cmd, (int)strlen(cmd), 0);
            send(g_clientSocket, "\n", 1, 0);
            g_bPendingConnect = false;
        }
        LeaveCriticalSection(&g_csSocket);

        char buffer[2048];
        std::string streamBuffer = "";

        while (true)
        {
            int bytesRead = recv(newClient, buffer, sizeof(buffer) - 1, 0);
            if (bytesRead <= 0)
            {
                EnterCriticalSection(&g_csSocket);
                g_bBridgeConnected = false;
                g_clientSocket = INVALID_SOCKET;
                LeaveCriticalSection(&g_csSocket);
                ArchipelagoUI::SetAPStatus(false, "2B", 0, 30);
                break; // Disconnected
            }
            buffer[bytesRead] = '\0';
            streamBuffer += buffer;

            size_t newlinePos = 0;
            while ((newlinePos = streamBuffer.find('\n')) != std::string::npos)
            {
                std::string line = streamBuffer.substr(0, newlinePos);
                streamBuffer.erase(0, newlinePos + 1);

                if (!line.empty() && line.back() == '\r') line.pop_back();
                if (line.empty()) continue;

                // 0. CHAPTERS: every story phase reached in this seed (replaces the list; Chapter Select filter)
                if (line.find("\"chapters\"") != std::string::npos && line.find("\"phases\"") != std::string::npos)
                {
                    const size_t open = line.find('[', line.find("\"phases\""));
                    const size_t close = line.find(']', open);
                    EnterCriticalSection(&g_csChapters);
                    g_reachedPhases.clear();
                    size_t p = open;
                    while (open != std::string::npos && close != std::string::npos)
                    {
                        const size_t a = line.find('"', p);
                        if (a == std::string::npos || a > close) break;
                        const size_t b = line.find('"', a + 1);
                        if (b == std::string::npos || b > close) break;
                        g_reachedPhases.insert(line.substr(a + 1, b - a - 1));
                        p = b + 1;
                    }
                    const size_t count = g_reachedPhases.size();
                    LeaveCriticalSection(&g_csChapters);
                    LogEventToFile("[CHAPTER_SELECT] %zu reached phases received from the bridge\n", count);
                }
                // 1. GIVE item (Consumable, Material, Pod Program, Gold)
                else if (line.rfind("GIVE", 0) == 0 || line.find("\"give\"") != std::string::npos)
                {
                    int itemId = 1;
                    int qty = 1;

                    if (line.rfind("GIVE", 0) == 0)
                    {
                        sscanf_s(line.c_str(), "GIVE %d %d", &itemId, &qty);
                        if (qty <= 0) qty = 1;
                    }
                    else
                    {
                        size_t idPos = line.find("\"item_id\":");
                        if (idPos != std::string::npos)
                        {
                            itemId = atoi(line.c_str() + idPos + 10);
                        }
                        size_t qtyPos = line.find("\"quantity\":");
                        if (qtyPos != std::string::npos)
                        {
                            qty = atoi(line.c_str() + qtyPos + 11);
                        }
                        if (qty <= 0) qty = 1;
                    }

                    std::string customName = "";
                    size_t nPos = line.find("\"name\":");
                    if (nPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", nPos + 7);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            customName = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }

                    std::string customSender = "Archipelago MultiWorld";
                    size_t sPos = line.find("\"sender\":");
                    if (sPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", sPos + 9);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            customSender = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }

                    const char* itemName = customName.empty() ? GetItemName(itemId) : customName.c_str();
                    bool showNotification = (line.find("\"notify\":false") == std::string::npos && line.find("\"notify\": false") == std::string::npos);
                    int totalGold = 0;
                    size_t tgPos = line.find("\"total_gold\":");
                    if (tgPos != std::string::npos) totalGold = atoi(line.c_str() + tgPos + 13);

                    size_t tcPos = line.find("\"total_count\":");
                    int totalCountParam = 0;
                    if (tcPos != std::string::npos) totalCountParam = atoi(line.c_str() + tcPos + 14);

                    bool knownOnly = (line.find("\"known_only\":true") != std::string::npos || line.find("\"known_only\": true") != std::string::npos);
                    int creditedGold = 0;
                    size_t cgPos = line.find("\"credited_gold\":");
                    if (cgPos != std::string::npos) creditedGold = atoi(line.c_str() + cgPos + 16);

                    RegisterReceivedArchipelagoItem(itemId, qty, itemName, customSender, showNotification, totalGold, totalCountParam, knownOnly, creditedGold);
                }
                // 1b. GIVE WEAPON
                else if (line.rfind("GIVE_WEAPON", 0) == 0 || line.find("\"give_weapon\"") != std::string::npos)
                {
                    int weaponId = 1000;
                    int level = 1;

                    if (line.rfind("GIVE_WEAPON", 0) == 0)
                    {
                        sscanf_s(line.c_str(), "GIVE_WEAPON %d %d", &weaponId, &level);
                    }
                    else
                    {
                        size_t idPos = line.find("\"weapon_id\":");
                        if (idPos != std::string::npos)
                        {
                            weaponId = atoi(line.c_str() + idPos + 12);
                        }
                        size_t lvlPos = line.find("\"level\":");
                        if (lvlPos != std::string::npos)
                        {
                            level = atoi(line.c_str() + lvlPos + 8);
                        }
                    }
                    if (level <= 0) level = 1;

                    std::string customWName = "";
                    size_t nPos = line.find("\"name\":");
                    if (nPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", nPos + 7);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            customWName = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }

                    std::string customSender = "Archipelago MultiWorld";
                    size_t sPos = line.find("\"sender\":");
                    if (sPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", sPos + 9);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            customSender = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }

                    const char* wName = customWName.empty() ? GetWeaponName(weaponId) : customWName.c_str();
                    bool showNotification = (line.find("\"notify\":false") == std::string::npos && line.find("\"notify\": false") == std::string::npos);
                    RegisterReceivedArchipelagoWeapon(weaponId, level, wName, customSender, showNotification);
                }
                // 1a-8. All items already received from Archipelago were handed over
                else if (line.find("\"items_synced\"") != std::string::npos)
                {
                    if (!g_bArchipelagoItemsSynced) LogEventToFile("[ARCHIPELAGO] items synced (route keys %ld)\n", g_routeKeys);
                    g_bArchipelagoItemsSynced = true;
                }
                // 1a-7. ROUTE KEY received from Archipelago ("route": "B" / "C" / "D")
                else if (line.find("\"route_key\"") != std::string::npos)
                {
                    const std::string route = JsonStringField(line, "route");
                    if (route == "B") InterlockedOr(&g_routeKeys, 1);
                    else if (route == "C") InterlockedOr(&g_routeKeys, 2);
                    else if (route == "D") InterlockedOr(&g_routeKeys, 4);
                }
                // 1a-9. DEATHLINK: another player died
                else if (line.find("\"cmd\": \"kill\"") != std::string::npos || line.find("\"cmd\":\"kill\"") != std::string::npos)
                {
                    KillPlayerFromDeathLink();
                }
                // 1b-0. GENERIC IN-GAME NOTIFICATION (e.g. quest finished)
                else if (line.find("\"cmd\": \"notify\"") != std::string::npos || line.find("\"cmd\":\"notify\"") != std::string::npos)
                {
                    ArchipelagoUI::AddNotification(JsonStringField(line, "title").c_str(), JsonStringField(line, "text").c_str());
                }
                // 1b-1. SHOP OVERLAY: contents of the shop locations (bridge sends clear + one line per hint)
                else if (line.find("\"shop_hint_clear\"") != std::string::npos)
                {
                    ArchipelagoUI::ClearShopHints();
                }
                else if (line.find("\"shop_hint\"") != std::string::npos)
                {
                    std::string flagsStr = JsonRawField(line, "flags");
                    ArchipelagoUI::AddShopHint(JsonStringField(line, "location").c_str(), JsonStringField(line, "item").c_str(),
                                               JsonStringField(line, "player").c_str(), flagsStr.empty() ? 0 : atoi(flagsStr.c_str()));
                }
                // 1b-2. SENT CHECK NOTIFICATION FROM BRIDGE
                else if (line.find("\"sent_check_notify\"") != std::string::npos)
                {
                    std::string locName = "Location Check";
                    std::string itemName = "";
                    size_t lPos = line.find("\"location\":");
                    if (lPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", lPos + 11);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            locName = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }
                    size_t iPos = line.find("\"item\":");
                    if (iPos != std::string::npos)
                    {
                        size_t q1 = line.find("\"", iPos + 7);
                        size_t q2 = (q1 != std::string::npos) ? line.find("\"", q1 + 1) : std::string::npos;
                        if (q1 != std::string::npos && q2 != std::string::npos)
                        {
                            itemName = line.substr(q1 + 1, q2 - q1 - 1);
                        }
                    }
                    ArchipelagoUI::AddSentCheck(locName.c_str(), itemName.c_str());
                }
                // 1c. GET / SYNC WEAPONS FROM SAVE INVENTORY
                else if (line.find("\"get_weapons\"") != std::string::npos || line.find("\"sync_weapons\"") != std::string::npos)
                {
                    uintptr_t base = (uintptr_t)GetModuleHandle(NULL);
                    uintptr_t addr = base + WEAPONS_OFFSET_START;
                    uintptr_t endAddr = base + WEAPONS_OFFSET_END;

                    std::string weaponListJson = "[";
                    bool firstW = true;
                    if (!IsBadReadPtr((void*)addr, (size_t)(endAddr - addr)))
                    {
                        uintptr_t curr = addr;
                        while (curr <= endAddr)
                        {
                            uint32_t wId = *(uint32_t*)curr;
                            if (wId != 0xFFFFFFFF && wId > 0 && wId < 3000)
                            {
                                char wBuf[32];
                                sprintf_s(wBuf, "%s%u", firstW ? "" : ",", wId);
                                weaponListJson += wBuf;
                                firstW = false;
                            }
                            curr += 0x14;
                        }
                    }
                    weaponListJson += "]";

                    char resp[1024];
                    sprintf_s(resp, "{\"event\":\"inventory_weapons\",\"weapons\":%s}", weaponListJson.c_str());
                    SendBridgeMessage(resp);
                    std::cout << "[Bridge] Responded to get_weapons request: " << weaponListJson << "\n";
                }
                // 1c-2. COMMIT MARKER (bridge asks us to confirm delivery once everything is in the inventory)
                else if (line.find("\"commit_marker\"") != std::string::npos)
                {
                    size_t mPos = line.find("\"index\":");
                    if (mPos != std::string::npos)
                    {
                        InterlockedExchange(&g_iCommitMarker, (LONG)atoi(line.c_str() + mPos + 8));
                        InterlockedExchange(&g_bCommitDirty, 1);
                    }
                }
                // 1d. RESYNC ALL ARCHIPELAGO ITEMS
                else if (line.find("\"resync_items\"") != std::string::npos)
                {
                    ForceResyncAllArchipelagoGrants();
                }
                // 1e. RESET RUN STATE (FOR NEW GAME)
                else if (line.find("\"reset_run_state\"") != std::string::npos || line.find("\"reset_run\"") != std::string::npos)
                {
                    ResetAllRunState(false);
                }
                // 2. SET INTERCEPT MODE
                else if (line.rfind("INTERCEPT", 0) == 0 || line.find("\"set_intercept\"") != std::string::npos)
                {
                    bool enable = false;
                    if (line.rfind("INTERCEPT", 0) == 0)
                    {
                        int v = 0;
                        sscanf_s(line.c_str(), "INTERCEPT %d", &v);
                        enable = (v != 0);
                    }
                    else
                    {
                        enable = (line.find("true") != std::string::npos || line.find("1") != std::string::npos);
                    }

                    g_bInterceptMode = enable;
                    std::cout << "[Bridge] Intercept mode set to: " << (g_bInterceptMode ? "ON" : "OFF") << "\n";

                    char resp[128];
                    sprintf_s(resp, "{\"event\":\"intercept_mode\",\"enabled\":%s}", g_bInterceptMode ? "true" : "false");
                    SendBridgeMessage(resp);
                }
                // 3. STATUS
                else if (line.rfind("STATUS", 0) == 0 || line.find("\"status\"") != std::string::npos)
                {
                    int money = g_piMoney ? *g_piMoney : 0;
                    int exp = g_piExperience ? *g_piExperience : 0;
                    int level = IsPlayerInGame() ? GetPlayerLevel((uintptr_t)GetModuleHandle(NULL), false) : 0;
                    char resp[256];
                    sprintf_s(resp, "{\"event\":\"status\",\"money\":%d,\"exp\":%d,\"level\":%d,\"checks\":%d,\"intercept\":%s}",
                              money, exp, level, g_totalInterceptedChecks, g_bInterceptMode ? "true" : "false");
                    SendBridgeMessage(resp);
                }
                // 4. PING
                else if (line.rfind("PING", 0) == 0 || line.find("\"ping\"") != std::string::npos)
                {
                    SendBridgeMessage("{\"event\":\"pong\"}");
                }
                // 5. AP STATUS SYNC FROM PYTHON
                else if (line.find("\"ap_status\"") != std::string::npos)
                {
                    bool connected = (line.find("\"connected\":true") != std::string::npos || line.find("\"connected\": true") != std::string::npos);
                    int checked = 0, total = 0;
                    size_t chkPos = line.find("\"checked\":");
                    if (chkPos != std::string::npos) checked = atoi(line.c_str() + chkPos + 10);
                    size_t totPos = line.find("\"total\":");
                    if (totPos != std::string::npos) total = atoi(line.c_str() + totPos + 8);

                    std::string slot = "2B";
                    size_t slotPos = line.find("\"slot\":\"");
                    if (slotPos != std::string::npos)
                    {
                        size_t endSlot = line.find("\"", slotPos + 8);
                        if (endSlot != std::string::npos)
                            slot = line.substr(slotPos + 8, endSlot - (slotPos + 8));
                    }

                    ArchipelagoUI::SetAPStatus(connected, slot.c_str(), checked, total);
                }
            }
        }

        EnterCriticalSection(&g_csSocket);
        closesocket(newClient);
        g_clientSocket = INVALID_SOCKET;
        g_bBridgeConnected = false;
        LeaveCriticalSection(&g_csSocket);

        std::cout << "[-] [Bridge Server] Python Client disconnected.\n";
    }

    return 0;
}

static void InitializeGameOffsets()
{
    std::cout << "[*] Initializing memory pointers and hooks for NieR: Automata...\n";

    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);

    // Direct verified Steam 2021 RVAs in .data section
    g_piMoney = (int32_t*)(moduleBase + MONEY_RVA);
    std::cout << "  [+] Money (G) Pointer: 0x" << std::hex << (uintptr_t)g_piMoney << std::dec << "\n";

    g_pItemManager = (void*)(moduleBase + 0x133B510);
    std::cout << "  [+] Item Catalog Instance: 0x" << std::hex << (uintptr_t)g_pItemManager << std::dec << "\n";

    g_piExperience = (int32_t*)FindPatternPtr("8B 15 ? ? ? ? 48 8D 8F ? ? ? ? E8 ? ? ? ? 8B 48 04", 2);
    if (g_piExperience)
        std::cout << "  [+] Experience Pointer: 0x" << std::hex << (uintptr_t)g_piExperience << std::dec << "\n";

    g_pInventoryManager = (void*)FindPatternPtr("7E CA 48 8D 15 ? ? ? ?", 5);
    if (g_pInventoryManager)
        std::cout << "  [+] Inventory Manager (Player): 0x" << std::hex << (uintptr_t)g_pInventoryManager << std::dec << "\n";
    else
        std::cout << "  [*] Inventory Manager will be captured automatically from engine.\n";


    ItemManager_AddItem = (CItemManager_AddItemFn)FindPattern("48 8B C4 57 41 54 41 55 41 56 41 57 48 81 EC ? ? ? ? 48 C7 44 24 ? ? ? ? ? 48 89 58 ? 48 89 68 ? 48 89 70 ? 45 8B F0");
    if (ItemManager_AddItem)
    {
        std::cout << "  [+] ItemManager_AddItem function: 0x" << std::hex << (uintptr_t)ItemManager_AddItem << std::dec << "\n";

        MH_STATUS status = MH_CreateHook((LPVOID)ItemManager_AddItem, (LPVOID)&hkItemManager_AddItem, (LPVOID*)&oItemManager_AddItem);
        if (status == MH_OK)
        {
            MH_EnableHook((LPVOID)ItemManager_AddItem);
            std::cout << "  [+] MinHook: ItemManager_AddItem DETOUR HOOK ACTIVATED!\n";
        }
        else
        {
            std::cerr << "  [-] MinHook: Failed to hook ItemManager_AddItem, status = " << status << "\n";
        }
    }
    else
    {
        std::cerr << "  [-] Could not locate ItemManager_AddItem.\n";
    }

    InstallChapterSelectHooks(moduleBase);


    std::cout << "[*] Memory pattern scan and hook initialization finished.\n\n";
}

// -------------------------------------------------------------
// Debug Console Setup
// -------------------------------------------------------------
static void OpenConsole()
{
    AllocConsole();
    SetConsoleTitleW(L"NieR: Automata - Archipelago Hook [Active]");

    FILE* fp = nullptr;
    freopen_s(&fp, "CONOUT$", "w", stdout);
    freopen_s(&fp, "CONOUT$", "w", stderr);
    freopen_s(&fp, "CONIN$", "r", stdin);

    std::ios::sync_with_stdio(true);
}

// -------------------------------------------------------------
// Main In-Game Mod Thread
// -------------------------------------------------------------
static DWORD WINAPI MainThread(LPVOID lpParam)
{
    Sleep(1500);

    OpenConsole();

    std::cout << "=========================================================\n";
    std::cout << "  NieR: Automata - Archipelago MultiWorld Hook v0.1.0-prebeta\n";
    std::cout << "  [Location Checks & TCP Bridge Server on Port 52140]    \n";
    std::cout << "=========================================================\n";

    uintptr_t moduleBase = (uintptr_t)GetModuleHandle(NULL);
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);

    std::cout << "[+] Injected into: " << exePath << "\n";
    std::cout << "[+] Module Base Address: 0x" << std::hex << moduleBase << std::dec << "\n";

    InitializeCriticalSection(&g_csSocket);
    InitializeCriticalSection(&g_csReconciliation);

    if (MH_Initialize() == MH_OK)
    {
        std::cout << "[+] MinHook initialized successfully!\n";
    }

    InitializeGameOffsets();

    // Initialize DirectX 11 ImGui YoRHa Overlay Menu
    ArchipelagoUI::Initialize();

    // Start background TCP bridge server on port 52140
    CreateThread(NULL, 0, BridgeServerThread, NULL, 0, NULL);

    std::cout << "[*] CONTROLS:\n";
    std::cout << "    [F1] / [INSERT] Open/Close YoRHa In-Game Menu\n";
    std::cout << "    [F2] Shop hints (what the shop locations contain)\n";
    std::cout << "    [F6] Check Player Money & Experience\n";
    std::cout << "=========================================================\n";
    std::cout << "[*] READY: Walk around in-game, open a chest or pick up any item.\n";
    std::cout << "    Events will be streamed live to the Python client!\n\n";

    static bool s_wasInGame = false;
    static uint32_t s_lastKnownPlaytime = 0;
    static uintptr_t s_lastEntity = 0;

    while (true)
    {
        Sleep(100);

        bool nowInGame = IsPlayerInGame();
        uint32_t curPt = 0;
        uintptr_t curEntity = 0;
        if (nowInGame)
        {
            curPt = GetCurrentPlaytime();
            __try
            {
                uintptr_t* pEnt = (uintptr_t*)(moduleBase + 0x1020948);
                if (pEnt && !IsBadReadPtr(pEnt, sizeof(uintptr_t))) curEntity = *pEnt;
            }
            __except (EXCEPTION_EXECUTE_HANDLER) {}
        }

        bool spawnEdge      = (!s_wasInGame && nowInGame);                        // loading screen -> 2B in the world
        bool playtimeRewound = (nowInGame && s_wasInGame && curPt + 3 < s_lastKnownPlaytime); // an older save was reloaded
        bool entityChanged  = (nowInGame && s_wasInGame && s_lastEntity != 0 && curEntity != 0 && curEntity != s_lastEntity);

        if (spawnEdge || playtimeRewound || entityChanged)
        {
            bool isNewRun = (spawnEdge || playtimeRewound) && curPt < 15 && (spawnEdge || s_lastKnownPlaytime > 30);
            if (isNewRun)
            {
                std::cout << "\n🔄 [AUTO RUN DETECTED] New game / fresh run detected (Playtime: " << curPt << "s)! Automatically resetting and re-granting items...\n";
                ResetAllRunState(true);
                char spawnJson[128];
                sprintf_s(spawnJson, "{\"event\":\"player_spawned\",\"new_run\":true,\"playtime\":%u}", curPt);
                SendBridgeMessage(spawnJson);
            }
            else
            {
                if (spawnEdge || playtimeRewound)
                    std::cout << "\n[*] [SPAWN] Save (re)loaded (Playtime: " << curPt << "s). Checking permanent items & replaying lost grants...\n";
                // Weapons / pod programs / chips only: never give back what the player used or spent
                ForceResyncAllArchipelagoGrants(false);
                // Everything granted after the reloaded save was written is gone from the inventory
                ReplayLostGrants(curPt);
                if (spawnEdge || playtimeRewound)
                {
                    char spawnJson[128];
                    sprintf_s(spawnJson, "{\"event\":\"player_spawned\",\"new_run\":false,\"playtime\":%u}", curPt);
                    SendBridgeMessage(spawnJson);
                }
            }
        }
        if (nowInGame)
        {
            s_lastKnownPlaytime = curPt;
            if (curEntity != 0) s_lastEntity = curEntity;
        }
        else
        {
            s_lastEntity = 0;
        }
        s_wasInGame = nowInGame;

        // Continuous Luigi's Mansion style reconciliation
        ProcessPendingArchipelagoGrants();
        ReportGrantsIdleIfNeeded();
        SanitizePlayerWeaponsAndHUD();
        EnforceProgressiveChipStorage();
        CheckPrologueBossProgress(moduleBase);
        CheckPlayerLevelProgress(moduleBase);
        CheckPhaseChange(moduleBase);
        ProcessDeathLinkKill(moduleBase);
        CheckPlayerDeath(moduleBase);

        {
            static ULONGLONG s_lastVerify = 0;
            static ULONGLONG s_lastSnapshot = 0;
            ULONGLONG nowTick = GetTickCount64();
            if (nowTick - s_lastVerify >= 5000)
            {
                s_lastVerify = nowTick;
                VerifyPersistentArchipelagoGrants();
            }
            static uint32_t s_lastEndingsMask = 0;
            uint32_t* pEndings = (uint32_t*)(moduleBase + SAVE_DATA_BASE_RVA + 0x2C); // file offset 0x30
            __try
            {
                if (pEndings && !IsBadReadPtr(pEndings, sizeof(uint32_t)))
                {
                    uint32_t curMask = *pEndings;
                    if (curMask != s_lastEndingsMask)
                    {
                        s_lastEndingsMask = curMask;
                        PublishLiveSaveSnapshot();
                    }
                }
            }
            __except (EXCEPTION_EXECUTE_HANDLER) {}

            if (nowTick - s_lastSnapshot >= 1000)
            {
                s_lastSnapshot = nowTick;
                PublishLiveSaveSnapshot();
            }
        }

        // Live check for newly acquired weapons in world / chests / hacking
        CheckWeaponInventoryChanges(moduleBase);

        // F6: Read current stats
        if (GetAsyncKeyState(VK_F6) & 1)
        {
            std::cout << "\n--- [F6 PRESSED: Current Status] ---\n";
            if (g_piMoney)
            {
                std::cout << "  Current Money (G): " << *g_piMoney << "\n";
            }
            if (g_piExperience)
            {
                std::cout << "  Current Experience: " << *g_piExperience << "\n";
            }
        }

    }

    return 0;
}

// -------------------------------------------------------------
// DLL Entry Point
// -------------------------------------------------------------
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    switch (ul_reason_for_call)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(hModule);
        LoadRealDInput8();
        CreateThread(NULL, 0, MainThread, hModule, 0, NULL);
        break;

    case DLL_PROCESS_DETACH:
        MH_Uninitialize();
        if (g_clientSocket != INVALID_SOCKET)
        {
            closesocket(g_clientSocket);
        }
        if (g_serverSocket != INVALID_SOCKET)
        {
            closesocket(g_serverSocket);
        }
        WSACleanup();
        if (g_hRealDInput8)
        {
            FreeLibrary(g_hRealDInput8);
            g_hRealDInput8 = nullptr;
        }
        break;
    }
    return TRUE;
}
