#pragma once
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <string>
#include <vector>

struct APLogEntry
{
    std::string text;
    bool isItem;
    bool isCheck;
};

// Short-lived in-game notification shown even when the menu is closed
struct APToast
{
    std::string title;
    std::string text;
    bool isItem;
    ULONGLONG startTick;
};

// What a not-yet-bought shop location contains (scouted by the bridge)
struct APShopHint
{
    std::string location;
    std::string item;
    std::string player;
    int flags; // AP item flags: 1 = progression, 2 = useful, 4 = trap
};

class ArchipelagoUI
{
public:
    static bool Initialize();
    static void Shutdown();

    static bool IsOpen();
    static void SetOpen(bool open);
    static void ToggleOpen();

    static void AddReceivedItem(const char* item, const char* sender);
    static void AddSentCheck(const char* location, const char* item);
    static void SetAPStatus(bool connected, const char* slot, int checkedCount, int totalCount);
    static void ClearLog();
    static void AddNotification(const char* title, const char* text);
    static void ClearShopHints();
    static void AddShopHint(const char* location, const char* item, const char* player, int flags);

    static char s_szServer[128];
    static char s_szSlot[64];
    static char s_szPassword[64];
    static bool s_bInterceptMode;
    static bool s_bAPConnected;
    static int s_iCheckedLocations;
    static int s_iTotalLocations;
    static std::string s_strCurrentSlot;
    static int s_iActiveSlot;
    static char s_szActivePlayer[64];

    static std::vector<APLogEntry> s_activityLog;
    static std::vector<APToast> s_toasts; // protected by s_csLog
    static bool s_bShowToasts;
    static std::vector<APShopHint> s_shopHints; // protected by s_csLog
    static bool s_bShowShopPanel;   // automatic display at the Resistance Camp shops
    static bool s_bShopPanelPinned; // F2: display anywhere
    static CRITICAL_SECTION s_csLog;
};

extern bool g_bBlockGroundLoot;
extern bool g_bEnforceBareFists;
extern bool g_bEnforceBareHUD;
extern bool g_bProgressiveChipStorage;
extern bool g_bInterceptMode;

void ProcessPendingArchipelagoGrants();
void FlushPendingArchipelagoGrants();
void ForceResyncAllArchipelagoGrants(bool includeConsumables = true);
void ResetAllRunState(bool reGrantAllItems = false);
void SanitizePlayerWeaponsAndHUD();
bool IsPlayerInCampShopArea();
bool GivePlayerChipDirect(int item_id);
