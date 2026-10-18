#include "ArchipelagoUI.h"
#include "imgui/imgui.h"
#include "imgui/imgui_impl_win32.h"
#include "imgui/imgui_impl_dx11.h"
#include "minhook/include/MinHook.h"
#include <iostream>
#include <chrono>
#include <ctime>
#include <cstdarg>
#include <algorithm>

static void LogToFile(const char* fmt, ...)
{
    static FILE* s_fLog = nullptr;
    static bool s_bAttempted = false;
    if (!s_bAttempted)
    {
        fopen_s(&s_fLog, "archipelago_hook.log", "w");
        s_bAttempted = true;
    }
    if (s_fLog)
    {
        va_list args;
        va_start(args, fmt);
        vfprintf(s_fLog, fmt, args);
        va_end(args);
        fflush(s_fLog);
    }
}

// Function pointer typedef for IDXGISwapChain::Present
typedef HRESULT(__stdcall* PresentFn)(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags);
static PresentFn oPresent = nullptr;

// Function pointer typedef for IDXGISwapChain::ResizeBuffers
typedef HRESULT(__stdcall* ResizeBuffersFn)(IDXGISwapChain* pSwapChain, UINT BufferCount, UINT Width, UINT Height, DXGI_FORMAT NewFormat, UINT SwapChainFlags);
static ResizeBuffersFn oResizeBuffers = nullptr;

// Function pointer typedef for WNDPROC
static WNDPROC oWndProc = nullptr;

// DirectX 11 Objects
static ID3D11Device* g_pd3dDevice = nullptr;
static ID3D11DeviceContext* g_pd3dDeviceContext = nullptr;
static ID3D11RenderTargetView* g_mainRenderTargetView = nullptr;
static HWND g_hGameWindow = nullptr;
static bool g_bImGuiInitialized = false;
static bool g_bShowMenu = false; // Fermé par défaut au démarrage ! Appuyer sur F1 pour ouvrir.
static ImGuiContext* g_pImGuiContext = nullptr;

// Static Members of ArchipelagoUI
char ArchipelagoUI::s_szServer[128] = "archipelago.gg:38281";
char ArchipelagoUI::s_szSlot[64] = "Player1";
char ArchipelagoUI::s_szPassword[64] = "";
bool ArchipelagoUI::s_bAPConnected = false;
int ArchipelagoUI::s_iCheckedLocations = 0;
int ArchipelagoUI::s_iTotalLocations = 216;
std::string ArchipelagoUI::s_strCurrentSlot = "Player1";
int ArchipelagoUI::s_iActiveSlot = -1;
char ArchipelagoUI::s_szActivePlayer[64] = "Inconnu";
std::vector<APLogEntry> ArchipelagoUI::s_activityLog;
std::vector<APToast> ArchipelagoUI::s_toasts;
bool ArchipelagoUI::s_bShowToasts = true;
std::vector<APShopHint> ArchipelagoUI::s_shopHints;
bool ArchipelagoUI::s_bShowShopPanel = true;
bool ArchipelagoUI::s_bShopPanelPinned = false;
CRITICAL_SECTION ArchipelagoUI::s_csLog;

static const ULONGLONG TOAST_DURATION_MS = 6000;
static const ULONGLONG TOAST_FADE_MS     = 800;
static const size_t    TOAST_MAX_VISIBLE = 5;

extern void SendBridgeMessage(const char* msg);
extern bool GivePlayerItemDirect(int item_id, int count);
extern bool GivePlayerWeaponDirect(int weapon_id, int level);
extern bool GivePlayerPodProgramDirect(int program_id);
extern bool GivePlayerGoldDirect(int amount);
extern bool IsBridgeConnected();
extern void LaunchPythonBridge();
extern void QueueAPConnect(const char* server, const char* slot, const char* password);

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandlerEx(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam, ImGuiIO& io);

// -------------------------------------------------------------
// YoRHa Aesthetic Styling (Beige, Slate Charcoal, Warm Gold)
// -------------------------------------------------------------
static void ApplyYoRHaStyle()
{
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 0.0f; // Sharp edges (YoRHa UI aesthetic)
    style.ChildRounding = 0.0f;
    style.FrameRounding = 0.0f;
    style.GrabRounding = 0.0f;
    style.PopupRounding = 0.0f;
    style.ScrollbarRounding = 0.0f;
    style.WindowBorderSize = 2.0f;
    style.FrameBorderSize = 1.0f;
    style.WindowPadding = ImVec2(16.0f, 16.0f);
    style.FramePadding = ImVec2(8.0f, 6.0f);
    style.ItemSpacing = ImVec2(10.0f, 8.0f);

    ImVec4* colors = style.Colors;
    // Dark Charcoal / Slate Gray base
    colors[ImGuiCol_WindowBg]             = ImVec4(0.18f, 0.17f, 0.15f, 0.96f);
    colors[ImGuiCol_ChildBg]              = ImVec4(0.14f, 0.13f, 0.12f, 0.85f);
    colors[ImGuiCol_PopupBg]              = ImVec4(0.20f, 0.19f, 0.17f, 0.98f);
    colors[ImGuiCol_Border]               = ImVec4(0.75f, 0.72f, 0.62f, 0.80f); // YoRHa Muted Gold/Beige
    colors[ImGuiCol_BorderShadow]         = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);

    // Text & Headers
    colors[ImGuiCol_Text]                 = ImVec4(0.88f, 0.86f, 0.78f, 1.00f); // Off-White / Beige
    colors[ImGuiCol_TextDisabled]         = ImVec4(0.50f, 0.48f, 0.44f, 1.00f);
    colors[ImGuiCol_TitleBg]              = ImVec4(0.14f, 0.13f, 0.12f, 1.00f);
    colors[ImGuiCol_TitleBgActive]        = ImVec4(0.28f, 0.26f, 0.23f, 1.00f);
    colors[ImGuiCol_TitleBgCollapsed]     = ImVec4(0.10f, 0.10f, 0.10f, 0.75f);

    // Buttons
    colors[ImGuiCol_Button]               = ImVec4(0.26f, 0.25f, 0.22f, 1.00f);
    colors[ImGuiCol_ButtonHovered]        = ImVec4(0.42f, 0.39f, 0.32f, 1.00f);
    colors[ImGuiCol_ButtonActive]         = ImVec4(0.75f, 0.68f, 0.48f, 1.00f); // Warm Gold

    // Inputs & Frames
    colors[ImGuiCol_FrameBg]              = ImVec4(0.12f, 0.11f, 0.10f, 1.00f);
    colors[ImGuiCol_FrameBgHovered]       = ImVec4(0.22f, 0.20f, 0.18f, 1.00f);
    colors[ImGuiCol_FrameBgActive]        = ImVec4(0.30f, 0.28f, 0.24f, 1.00f);

    // Tabs
    colors[ImGuiCol_Tab]                  = ImVec4(0.20f, 0.19f, 0.17f, 1.00f);
    colors[ImGuiCol_TabHovered]           = ImVec4(0.45f, 0.42f, 0.34f, 1.00f);
    colors[ImGuiCol_TabActive]            = ImVec4(0.32f, 0.30f, 0.25f, 1.00f);
    colors[ImGuiCol_TabUnfocused]         = ImVec4(0.15f, 0.14f, 0.13f, 1.00f);
    colors[ImGuiCol_TabUnfocusedActive]  = ImVec4(0.24f, 0.22f, 0.19f, 1.00f);

    // Headers & Highlights
    colors[ImGuiCol_Header]               = ImVec4(0.30f, 0.28f, 0.24f, 1.00f);
    colors[ImGuiCol_HeaderHovered]        = ImVec4(0.42f, 0.38f, 0.30f, 1.00f);
    colors[ImGuiCol_HeaderActive]         = ImVec4(0.55f, 0.48f, 0.36f, 1.00f);

    // Scrollbars
    colors[ImGuiCol_ScrollbarBg]          = ImVec4(0.10f, 0.10f, 0.09f, 0.60f);
    colors[ImGuiCol_ScrollbarGrab]        = ImVec4(0.32f, 0.30f, 0.26f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.45f, 0.42f, 0.35f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabActive]  = ImVec4(0.65f, 0.58f, 0.45f, 1.00f);
}

// -------------------------------------------------------------
// Window Procedure Hook (Captures F1, Insert, Keyboard/Mouse)
// -------------------------------------------------------------
static LRESULT CALLBACK hkWndProc(HWND hWnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
    // Toggle Menu with F1 or INSERT (ignore auto-repeat keystrokes with bit 30)
    if (uMsg == WM_KEYDOWN && (wParam == VK_F1 || wParam == VK_INSERT))
    {
        bool isRepeat = (lParam & (1 << 30)) != 0;
        if (!isRepeat)
        {
            ArchipelagoUI::ToggleOpen();
        }
        return 0;
    }

    // F2: show / hide the shop checks panel anywhere
    if (uMsg == WM_KEYDOWN && wParam == VK_F2 && !(lParam & (1 << 30)))
    {
        ArchipelagoUI::s_bShopPanelPinned = !ArchipelagoUI::s_bShopPanelPinned;
        return 0;
    }

    if (g_bShowMenu && g_pImGuiContext)
    {
        ImGui::SetCurrentContext(g_pImGuiContext);
        ImGuiIO& io = ImGui::GetIO();
        ImGui_ImplWin32_WndProcHandlerEx(hWnd, uMsg, wParam, lParam, io);

        // When menu is open, block mouse attacks / pod firing in the game
        switch (uMsg)
        {
        case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK:
        case WM_RBUTTONDOWN: case WM_RBUTTONUP: case WM_RBUTTONDBLCLK:
        case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MBUTTONDBLCLK:
        case WM_MOUSEWHEEL:  case WM_MOUSEHWHEEL:
            return 0;

        case WM_KEYDOWN: case WM_KEYUP:
        case WM_CHAR:    case WM_DEADCHAR:
        case WM_SYSKEYDOWN: case WM_SYSKEYUP:
            if (io.WantTextInput || io.WantCaptureKeyboard)
                return 0;
            break;
        }
    }

    if (oWndProc)
    {
        if (IsWindowUnicode(hWnd))
            return CallWindowProcW(oWndProc, hWnd, uMsg, wParam, lParam);
        else
            return CallWindowProcA(oWndProc, hWnd, uMsg, wParam, lParam);
    }

    return DefWindowProc(hWnd, uMsg, wParam, lParam);
}

// -------------------------------------------------------------
// Render the YoRHa Archipelago In-Game Menu
// -------------------------------------------------------------
static void RenderArchipelagoMenu()
{
    if (!g_bShowMenu)
        return;

    ImGui::SetNextWindowSize(ImVec2(740.0f, 560.0f), ImGuiCond_FirstUseEver);

    // Pass nullptr so ImGui never closes the menu window on its own
    if (ImGui::Begin("[YoRHa] ARCHIPELAGO MULTIWORLD RANDOMIZER (NieR: Automata)", nullptr, ImGuiWindowFlags_NoCollapse))
    {
        ImGui::TextColored(ImVec4(0.75f, 0.72f, 0.62f, 1.0f), "SYSTEM // MULTIWORLD CONNECTION GATEWAY");
        ImGui::SameLine(ImGui::GetWindowWidth() - 170.0f);
        if (ImGui::Button("[X] Fermer [F1]", ImVec2(150.0f, 24.0f)))
        {
            ArchipelagoUI::SetOpen(false);
        }

        ImGui::TextDisabled("Appuyez sur [F1] ou [INSERT] pour afficher/masquer ce menu.");
        ImGui::Spacing();

        if (ImGui::BeginTabBar("YoRHaTabs"))
        {
            // TAB 1: CONNECTION
            if (ImGui::BeginTabItem(" [+] Connexion MultiWorld "))
            {
                ImGui::Spacing();

                // Status Banner
                if (ArchipelagoUI::s_bAPConnected)
                {
                    ImGui::TextColored(ImVec4(0.35f, 0.90f, 0.35f, 1.0f), "[CONNECTED] STATUT : CONNECTE AU SERVEUR ARCHIPELAGO");
                    ImGui::Text("  Slot Actif : %s | Checks : %d / %d",
                                ArchipelagoUI::s_strCurrentSlot.c_str(),
                                ArchipelagoUI::s_iCheckedLocations,
                                ArchipelagoUI::s_iTotalLocations);
                }
                else
                {
                    ImGui::TextColored(ImVec4(0.90f, 0.35f, 0.35f, 1.0f), "[-] STATUT : DECONNECTE DU MULTIWORLD");
                    if (IsBridgeConnected())
                    {
                        ImGui::TextColored(ImVec4(0.40f, 0.85f, 0.40f, 1.0f), "  [OK] Pont local actif (Pret pour connexion)");
                    }
                    else
                    {
                        ImGui::TextColored(ImVec4(1.0f, 0.80f, 0.30f, 1.0f), "  [*] Demarrage automatique du pont local en cours...");
                    }
                }

                ImGui::Spacing();
                ImGui::Separator();
                ImGui::Spacing();

                ImGui::Text("Parametres de connexion :");
                ImGui::InputText("Serveur (Hote:Port)", ArchipelagoUI::s_szServer, sizeof(ArchipelagoUI::s_szServer));
                ImGui::InputText("Nom du Slot / Pseudo", ArchipelagoUI::s_szSlot, sizeof(ArchipelagoUI::s_szSlot));
                ImGui::InputText("Mot de passe (Optionnel)", ArchipelagoUI::s_szPassword, sizeof(ArchipelagoUI::s_szPassword), ImGuiInputTextFlags_Password);

                ImGui::Spacing();

                if (!ArchipelagoUI::s_bAPConnected)
                {
                    if (ImGui::Button(" >>> SE CONNECTER A ARCHIPELAGO <<< ", ImVec2(340.0f, 38.0f)))
                    {
                        if (!IsBridgeConnected())
                        {
                            LaunchPythonBridge();
                        }

                        // Queue and send connection request to bridge
                        QueueAPConnect(ArchipelagoUI::s_szServer, ArchipelagoUI::s_szSlot, ArchipelagoUI::s_szPassword);
                    }
                }
                else
                {
                    if (ImGui::Button(" [X] SE DECONNECTER ", ImVec2(240.0f, 38.0f)))
                    {
                        SendBridgeMessage("{\"cmd\":\"ap_disconnect_request\"}");
                        ArchipelagoUI::s_bAPConnected = false;
                    }

                    ImGui::Spacing();
                    if (ImGui::Button(" [S] Synchroniser Sauvegarde (Endings, Terminaux, Armes, Quetes) ", ImVec2(480.0f, 32.0f)))
                    {
                        SendBridgeMessage("{\"cmd\":\"sync_save_checks\"}");
                    }
                    ImGui::TextDisabled("Valide instantanement sur Archipelago les fins (ex: Ending U), terminaux et armes de votre sauvegarde.");

                    ImGui::Spacing();
                    if (ImGui::Button(" [R] Recevoir / Forcer TOUTES les Recompenses (Puces, Armes, Objets) ", ImVec2(480.0f, 32.0f)))
                    {
                        ForceResyncAllArchipelagoGrants();
                        SendBridgeMessage("{\"cmd\":\"resync_items\",\"include_all\":true}");
                    }
                    ImGui::TextDisabled("Injecte dans votre inventaire et liste de puces/armes TOUTES les recompenses recues du MultiWorld.");

                    ImGui::Spacing();
                    if (ImGui::Button(" [NOUVELLE PARTIE / RESET RUN] Reinitialiser & Re-injecter les Objets ", ImVec2(480.0f, 34.0f)))
                    {
                        ResetAllRunState(false);
                        SendBridgeMessage("{\"cmd\":\"reset_run\"}");
                    }
                    ImGui::TextDisabled("A utiliser apres avoir lance une nouvelle partie ou apres un reset : efface les caches et re-donne tous vos items.");
                }

                ImGui::Spacing();
                ImGui::Separator();
                ImGui::Spacing();

                // Gameplay & Intercept Toggles
                ImGui::Text("Regles et Options de Gameplay :");
                if (ImGui::Checkbox("Interception des Coffres & Armes (MultiWorld)", &g_bInterceptMode))
                {
                    char cmd[128];
                    sprintf_s(cmd, "{\"cmd\":\"set_intercept\",\"enabled\":%s}", g_bInterceptMode ? "true" : "false");
                    SendBridgeMessage(cmd);
                }
                ImGui::Checkbox("Bloquer le loot au sol & drops de monstres", &g_bBlockGroundLoot);
                ImGui::TextDisabled("  -> Conserve toujours les objets de quete, objets cles et materiaux.");
                ImGui::Checkbox("Combat a mains nues au depart (Bare Fists)", &g_bEnforceBareFists);
                ImGui::Checkbox("ATH minimaliste (Puces HUD a debloquer via checks)", &g_bEnforceBareHUD);
                ImGui::Checkbox("Stockage de puces progressif (achats = checks)", &g_bProgressiveChipStorage);
                ImGui::Checkbox("Notifications en jeu (items recus / checks envoyes)", &ArchipelagoUI::s_bShowToasts);
                ImGui::Checkbox("Panneau des checks de boutique au camp (F2 = partout)", &ArchipelagoUI::s_bShowShopPanel);

                ImGui::Spacing();
                ImGui::Separator();
                ImGui::Spacing();

                ImGui::Text("Partie et Sauvegarde Active :");
                if (ArchipelagoUI::s_iActiveSlot >= 0)
                {
                    ImGui::TextColored(ImVec4(0.4f, 1.0f, 0.4f, 1.0f), "  -> En cours : Slot %d (Joueur : '%s')", ArchipelagoUI::s_iActiveSlot + 1, ArchipelagoUI::s_szActivePlayer);
                }
                else
                {
                    ImGui::TextDisabled("  -> En attente : lancez ou chargez une partie pour la detection automatique.");
                }

                ImGui::Spacing();
                ImGui::Text("Changer le slot surveille par le pont :");
                if (ImGui::Button(" Slot 1 ", ImVec2(80, 26))) { SendBridgeMessage("{\"cmd\":\"set_slot\",\"target\":1}"); }
                ImGui::SameLine();
                if (ImGui::Button(" Slot 2 ", ImVec2(80, 26))) { SendBridgeMessage("{\"cmd\":\"set_slot\",\"target\":2}"); }
                ImGui::SameLine();
                if (ImGui::Button(" Slot 3 ", ImVec2(80, 26))) { SendBridgeMessage("{\"cmd\":\"set_slot\",\"target\":3}"); }
                ImGui::SameLine();
                if (ImGui::Button(" Mode Auto ", ImVec2(95, 26))) { SendBridgeMessage("{\"cmd\":\"set_slot\",\"target\":\"auto\"}"); }

                ImGui::Spacing();
                ImGui::Separator();
                ImGui::Spacing();

                ImGui::TextDisabled("Selection de chapitre : menu titre du jeu (chapitres deja atteints dans cette seed).");

                ImGui::EndTabItem();
            }

            // TAB 2: MULTIWORLD ACTIVITY LOG
            if (ImGui::BeginTabItem(" [=] Journal des Objets & Checks "))
            {
                ImGui::Spacing();
                ImGui::Text("Derniers evenements recus et envoyes en direct :");
                ImGui::Spacing();

                ImGui::BeginChild("LogRegion", ImVec2(0, 0), true);
                EnterCriticalSection(&ArchipelagoUI::s_csLog);
                if (ArchipelagoUI::s_activityLog.empty())
                {
                    ImGui::TextDisabled("Aucun evenement pour l'instant. Les coffres ouverts apparaitront ici.");
                }
                else
                {
                    for (int i = (int)ArchipelagoUI::s_activityLog.size() - 1; i >= 0; --i)
                    {
                        const auto& entry = ArchipelagoUI::s_activityLog[i];
                        if (entry.isItem)
                        {
                            ImGui::TextColored(ImVec4(0.40f, 0.85f, 1.0f, 1.0f), "[RECU] %s", entry.text.c_str());
                        }
                        else if (entry.isCheck)
                        {
                            ImGui::TextColored(ImVec4(1.0f, 0.85f, 0.40f, 1.0f), "[CHECK] %s", entry.text.c_str());
                        }
                        else
                        {
                            ImGui::Text(" * %s", entry.text.c_str());
                        }
                    }
                }
                LeaveCriticalSection(&ArchipelagoUI::s_csLog);
                ImGui::EndChild();

                ImGui::EndTabItem();
            }

            // TAB 3: LOCAL TESTING & CHEATS
            if (ImGui::BeginTabItem(" [*] Tests & Injection Manuelle "))
            {
                ImGui::Spacing();
                ImGui::Text("Tester l'injection d'objets en direct dans la RAM :");
                ImGui::Spacing();

                if (ImGui::Button("Injecter Potion Soin (Petite)", ImVec2(240, 30)))
                {
                    GivePlayerItemDirect(0, 5);
                }
                ImGui::SameLine();
                if (ImGui::Button("Injecter Minerai de Fer x10", ImVec2(240, 30)))
                {
                    GivePlayerItemDirect(601, 10);
                }

                if (ImGui::Button("Injecter Rusted Clump x5", ImVec2(240, 30)))
                {
                    GivePlayerItemDirect(530, 5);
                }
                ImGui::SameLine();
                if (ImGui::Button("Ajouter +5,000 G (Gold)", ImVec2(240, 30)))
                {
                    GivePlayerGoldDirect(5000);
                }

                ImGui::Spacing();
                ImGui::Text("Tester l'injection de Programmes de Pod :");
                if (ImGui::Button("[Pod] Mirage A090", ImVec2(240, 30)))
                {
                    GivePlayerPodProgramDirect(2001);
                }
                ImGui::SameLine();
                if (ImGui::Button("[Pod] Laser A080", ImVec2(240, 30)))
                {
                    GivePlayerPodProgramDirect(2000);
                }

                ImGui::Spacing();
                ImGui::Text("Tester l'injection d'armes du Randomizer :");
                if (ImGui::Button("[Epee] Virtuous Contract (Lv.1)", ImVec2(240, 30)))
                {
                    GivePlayerWeaponDirect(1070, 1);
                }
                ImGui::SameLine();
                if (ImGui::Button("[Epee] Iron Pipe (Lv.1)", ImVec2(240, 30)))
                {
                    GivePlayerWeaponDirect(1013, 1);
                }

                if (ImGui::Button("[Epee Lourde] Beastlord (Lv.4)", ImVec2(240, 30)))
                {
                    GivePlayerWeaponDirect(1220, 4);
                }
                ImGui::SameLine();
                if (ImGui::Button("[Combat] Poings Type-4O (Lv.1)", ImVec2(240, 30)))
                {
                    GivePlayerWeaponDirect(1610, 1);
                }

                ImGui::Spacing();
                ImGui::Text("Tester l'injection de Puces d'amelioration (Plug-in Chips) :");
                if (ImGui::Button("[Puce] Auto-Heal +2", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3102);
                }
                ImGui::SameLine();
                if (ImGui::Button("[Puce] Attaque Arme +3", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3004);
                }

                if (ImGui::Button("[Puce] PV Max +3", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3076);
                }
                ImGui::SameLine();
                if (ImGui::Button("[Puce] Overclock +3", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3193);
                }

                if (ImGui::Button("[HUD] Mini-carte", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3335);
                }
                ImGui::SameLine();
                if (ImGui::Button("[HUD] Jauge de PV", ImVec2(240, 30)))
                {
                    GivePlayerChipDirect(3345);
                }

                ImGui::EndTabItem();
            }

            ImGui::EndTabBar();
        }
    }
    ImGui::End();
}

// -------------------------------------------------------------
// In-game notifications (received items / sent checks), bottom-right corner
// -------------------------------------------------------------
static bool HasActiveToasts()
{
    EnterCriticalSection(&ArchipelagoUI::s_csLog);
    ULONGLONG now = GetTickCount64();
    auto& toasts = ArchipelagoUI::s_toasts;
    toasts.erase(std::remove_if(toasts.begin(), toasts.end(),
                                [now](const APToast& t) { return now - t.startTick >= TOAST_DURATION_MS; }),
                 toasts.end());
    bool active = !toasts.empty();
    LeaveCriticalSection(&ArchipelagoUI::s_csLog);
    return active;
}

static void RenderToasts()
{
    EnterCriticalSection(&ArchipelagoUI::s_csLog);
    const ImGuiViewport* vp = ImGui::GetMainViewport();
    ULONGLONG now = GetTickCount64();
    float y = vp->WorkPos.y + vp->WorkSize.y - 40.0f;

    // Newest at the bottom, older ones stacked above it
    int shown = 0;
    for (int i = (int)ArchipelagoUI::s_toasts.size() - 1; i >= 0 && shown < (int)TOAST_MAX_VISIBLE; --i, ++shown)
    {
        const APToast& t = ArchipelagoUI::s_toasts[i];
        ULONGLONG age = now - t.startTick;
        float alpha = 1.0f;
        if (age > TOAST_DURATION_MS - TOAST_FADE_MS)
            alpha = (float)(TOAST_DURATION_MS - age) / (float)TOAST_FADE_MS;
        if (alpha <= 0.0f) continue;

        ImVec4 accent = t.isItem ? ImVec4(0.40f, 0.85f, 1.0f, 1.0f) : ImVec4(1.0f, 0.85f, 0.40f, 1.0f);

        char winId[32];
        sprintf_s(winId, "##aptoast%d", shown);
        ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x - 30.0f, y), ImGuiCond_Always, ImVec2(1.0f, 1.0f));
        ImGui::SetNextWindowBgAlpha(0.85f * alpha);
        ImGui::PushStyleVar(ImGuiStyleVar_Alpha, alpha);
        ImGui::PushStyleColor(ImGuiCol_Border, accent);
        ImGui::Begin(winId, nullptr,
                     ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoInputs |
                     ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoSavedSettings |
                     ImGuiWindowFlags_NoMove);
        ImGui::SetWindowFontScale(1.3f);
        ImGui::TextColored(accent, "%s", t.title.c_str());
        ImGui::TextUnformatted(t.text.c_str());
        y -= ImGui::GetWindowSize().y + 8.0f;
        ImGui::End();
        ImGui::PopStyleColor();
        ImGui::PopStyleVar();
    }
    LeaveCriticalSection(&ArchipelagoUI::s_csLog);
}

// -------------------------------------------------------------
// Shop overlay: what the remaining shop purchases contain (top-right corner)
// -------------------------------------------------------------
static bool IsShopPanelVisible()
{
    if (!ArchipelagoUI::s_bShopPanelPinned && !(ArchipelagoUI::s_bShowShopPanel && IsPlayerInCampShopArea()))
        return false;
    EnterCriticalSection(&ArchipelagoUI::s_csLog);
    bool any = !ArchipelagoUI::s_shopHints.empty();
    LeaveCriticalSection(&ArchipelagoUI::s_csLog);
    return any;
}

static void RenderShopPanel()
{
    const ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x - 30.0f, vp->WorkPos.y + 90.0f), ImGuiCond_Always, ImVec2(1.0f, 0.0f));
    ImGui::SetNextWindowBgAlpha(0.85f);
    ImGui::Begin("##apshop", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoInputs |
                 ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoSavedSettings |
                 ImGuiWindowFlags_NoMove);
    ImGui::SetWindowFontScale(1.15f);
    ImGui::TextColored(ImVec4(0.75f, 0.72f, 0.62f, 1.0f), "BOUTIQUE // CHECKS ARCHIPELAGO  (F2)");
    ImGui::Separator();

    EnterCriticalSection(&ArchipelagoUI::s_csLog);
    for (const APShopHint& h : ArchipelagoUI::s_shopHints)
    {
        ImVec4 color = ImVec4(0.70f, 0.70f, 0.66f, 1.0f);                   // filler
        if (h.flags & 4)      color = ImVec4(1.0f, 0.40f, 0.40f, 1.0f);    // trap
        else if (h.flags & 1) color = ImVec4(0.80f, 0.60f, 1.0f, 1.0f);    // progression
        else if (h.flags & 2) color = ImVec4(0.40f, 0.85f, 1.0f, 1.0f);    // useful

        ImGui::TextUnformatted(h.location.c_str());
        ImGui::SameLine();
        ImGui::TextDisabled("->");
        ImGui::SameLine();
        ImGui::TextColored(color, "%s", h.item.c_str());
        ImGui::SameLine();
        ImGui::TextDisabled("(%s)", h.player.c_str());
    }
    LeaveCriticalSection(&ArchipelagoUI::s_csLog);
    ImGui::End();
}

static void PushToast(const std::string& title, const std::string& text, bool isItem)
{
    if (!ArchipelagoUI::s_bShowToasts) return;
    APToast toast;
    toast.title = title;
    toast.text = text;
    toast.isItem = isItem;
    toast.startTick = GetTickCount64();
    ArchipelagoUI::s_toasts.push_back(toast);
    if (ArchipelagoUI::s_toasts.size() > 20)
        ArchipelagoUI::s_toasts.erase(ArchipelagoUI::s_toasts.begin());
}

// -------------------------------------------------------------
// Hooked IDXGISwapChain::ResizeBuffers (Slot 13)
// -------------------------------------------------------------
static HRESULT __stdcall hkResizeBuffers(IDXGISwapChain* pSwapChain, UINT BufferCount, UINT Width, UINT Height, DXGI_FORMAT NewFormat, UINT SwapChainFlags)
{
    LogToFile("[ResizeBuffers] Resizing backbuffers to %ux%u (Format: %d, Count: %u)\n", Width, Height, NewFormat, BufferCount);

    // Must release all RenderTargetView references and clear D3D11 pipeline state
    if (g_mainRenderTargetView)
    {
        if (g_pd3dDeviceContext)
        {
            g_pd3dDeviceContext->OMSetRenderTargets(0, NULL, NULL);
            g_pd3dDeviceContext->ClearState();
            g_pd3dDeviceContext->Flush();
        }
        g_mainRenderTargetView->Release();
        g_mainRenderTargetView = nullptr;
    }

    HRESULT hr = oResizeBuffers(pSwapChain, BufferCount, Width, Height, NewFormat, SwapChainFlags);
    LogToFile("[ResizeBuffers] oResizeBuffers returned: 0x%08X\n", (unsigned int)hr);

    return hr;
}

// -------------------------------------------------------------
// Hooked IDXGISwapChain::Present (Slot 8)
// -------------------------------------------------------------
static HRESULT __stdcall hkPresent(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags)
{
    ProcessPendingArchipelagoGrants();

    if (!g_bImGuiInitialized && pSwapChain)
    {
        if (SUCCEEDED(pSwapChain->GetDevice(__uuidof(ID3D11Device), (void**)&g_pd3dDevice)))
        {
            g_pd3dDevice->GetImmediateContext(&g_pd3dDeviceContext);

            DXGI_SWAP_CHAIN_DESC desc;
            pSwapChain->GetDesc(&desc);
            g_hGameWindow = desc.OutputWindow;

            // Hook window messages for input handling
            if (IsWindowUnicode(g_hGameWindow))
                oWndProc = (WNDPROC)SetWindowLongPtrW(g_hGameWindow, GWLP_WNDPROC, (LONG_PTR)hkWndProc);
            else
                oWndProc = (WNDPROC)SetWindowLongPtrA(g_hGameWindow, GWLP_WNDPROC, (LONG_PTR)hkWndProc);

            // Initialize Dear ImGui
            IMGUI_CHECKVERSION();
            g_pImGuiContext = ImGui::CreateContext();
            ImGuiIO& io = ImGui::GetIO();
            io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;

            ApplyYoRHaStyle();

            ImGui_ImplWin32_Init(g_hGameWindow);
            ImGui_ImplDX11_Init(g_pd3dDevice, g_pd3dDeviceContext);

            // NOTE: We deliberately do NOT create g_mainRenderTargetView here!
            // Keeping backbuffer references at boot breaks NieR's initial ResizeBuffers.
            // g_mainRenderTargetView is created strictly on-demand when the menu opens.

            g_bImGuiInitialized = true;
            LogToFile("[Present] ImGui Initialized successfully on HWND 0x%p\n", g_hGameWindow);
            std::cout << "[+] [DirectX 11] Dear ImGui YoRHa Overlay INITIALIZED!\n";
            std::cout << "[+] Press [F1] or [INSERT] in-game to toggle the Archipelago Menu.\n";
        }
    }

    // Fallback hotkey check via GetAsyncKeyState ONLY if WndProc was not hooked
    if (!oWndProc)
    {
        static bool s_bF1Held = false;
        bool f1Now = (GetAsyncKeyState(VK_F1) & 0x8000) != 0 || (GetAsyncKeyState(VK_INSERT) & 0x8000) != 0;
        if (f1Now && !s_bF1Held)
        {
            ArchipelagoUI::ToggleOpen();
        }
        s_bF1Held = f1Now;
    }

    // ONLY render ImGui when the menu is OPEN or a notification / the shop panel is on screen
    bool toastsActive = g_bImGuiInitialized && HasActiveToasts();
    bool shopPanelActive = g_bImGuiInitialized && IsShopPanelVisible();
    if (g_bImGuiInitialized && (g_bShowMenu || toastsActive || shopPanelActive))
    {
        // Create Render Target View strictly on-demand
        if (!g_mainRenderTargetView && pSwapChain && g_pd3dDevice)
        {
            ID3D11Texture2D* pBackBuffer = nullptr;
            if (SUCCEEDED(pSwapChain->GetBuffer(0, __uuidof(ID3D11Texture2D), (LPVOID*)&pBackBuffer)))
            {
                g_pd3dDevice->CreateRenderTargetView(pBackBuffer, NULL, &g_mainRenderTargetView);
                pBackBuffer->Release();
            }
        }

        if (g_mainRenderTargetView)
        {
            ImGui::SetCurrentContext(g_pImGuiContext);
            ImGuiIO& io = ImGui::GetIO();
            io.MouseDrawCursor = g_bShowMenu;
            // Never let ImGui touch the OS cursor while only notifications are drawn (game hides it)
            if (g_bShowMenu) io.ConfigFlags &= ~ImGuiConfigFlags_NoMouseCursorChange;
            else             io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange;

            // Mouse is only fed (and the cursor freed) while the menu is open: toasts never take input
            if (g_bShowMenu)
            {
                ClipCursor(NULL);

                // Feed hardware mouse position directly
                POINT pt;
                if (GetCursorPos(&pt) && g_hGameWindow)
                {
                    ScreenToClient(g_hGameWindow, &pt);
                    io.AddMousePosEvent((float)pt.x, (float)pt.y);
                }

                // Edge-triggered hardware mouse clicks
                static bool s_bLeftDown = false;
                bool leftNow = (GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0;
                if (leftNow != s_bLeftDown)
                {
                    s_bLeftDown = leftNow;
                    io.AddMouseButtonEvent(0, leftNow);
                }

                static bool s_bRightDown = false;
                bool rightNow = (GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0;
                if (rightNow != s_bRightDown)
                {
                    s_bRightDown = rightNow;
                    io.AddMouseButtonEvent(1, rightNow);
                }
            }

            ImGui_ImplDX11_NewFrame();
            ImGui_ImplWin32_NewFrame();
            ImGui::NewFrame();

            RenderArchipelagoMenu();
            if (shopPanelActive) RenderShopPanel();
            if (toastsActive) RenderToasts();

            ImGui::Render();

            g_pd3dDeviceContext->OMSetRenderTargets(1, &g_mainRenderTargetView, NULL);
            ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());

            // Unbind render target after rendering so game pipeline is clean
            g_pd3dDeviceContext->OMSetRenderTargets(0, NULL, NULL);
        }
    }
    else if (g_mainRenderTargetView)
    {
        // Menu closed and no notification left: release backbuffer reference and flush D3D11 state
        if (g_pd3dDeviceContext)
        {
            g_pd3dDeviceContext->OMSetRenderTargets(0, NULL, NULL);
            g_pd3dDeviceContext->ClearState();
            g_pd3dDeviceContext->Flush();
        }
        g_mainRenderTargetView->Release();
        g_mainRenderTargetView = nullptr;
    }

    return oPresent(pSwapChain, SyncInterval, Flags);
}

// -------------------------------------------------------------
// Public ArchipelagoUI API
// -------------------------------------------------------------
bool ArchipelagoUI::Initialize()
{
    InitializeCriticalSection(&s_csLog);

    // Create dummy window to retrieve IDXGISwapChain Present & ResizeBuffers VTable
    WNDCLASSEX wc = { sizeof(WNDCLASSEX), CS_CLASSDC, DefWindowProc, 0L, 0L, GetModuleHandle(NULL), NULL, NULL, NULL, NULL, "DummyDX11Archipelago", NULL };
    RegisterClassEx(&wc);
    HWND hWnd = CreateWindow(wc.lpszClassName, "", WS_OVERLAPPEDWINDOW, 0, 0, 100, 100, NULL, NULL, wc.hInstance, NULL);

    D3D_FEATURE_LEVEL featureLevel;
    const D3D_FEATURE_LEVEL featureLevels[] = { D3D_FEATURE_LEVEL_11_0, D3D_FEATURE_LEVEL_10_0 };

    DXGI_SWAP_CHAIN_DESC sd;
    ZeroMemory(&sd, sizeof(sd));
    sd.BufferCount = 1;
    sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.OutputWindow = hWnd;
    sd.SampleDesc.Count = 1;
    sd.Windowed = TRUE;

    IDXGISwapChain* pDummySwapChain = nullptr;
    ID3D11Device* pDummyDevice = nullptr;
    ID3D11DeviceContext* pDummyContext = nullptr;

    HRESULT hr = D3D11CreateDeviceAndSwapChain(
        NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, featureLevels, 2,
        D3D11_SDK_VERSION, &sd, &pDummySwapChain, &pDummyDevice, &featureLevel, &pDummyContext);

    if (SUCCEEDED(hr) && pDummySwapChain)
    {
        void** pVTable = *(void***)pDummySwapChain;
        void* pPresent = pVTable[8];        // Present is index 8
        void* pResizeBuffers = pVTable[13]; // ResizeBuffers is index 13

        MH_CreateHook(pPresent, (LPVOID)&hkPresent, (LPVOID*)&oPresent);
        MH_EnableHook(pPresent);

        MH_CreateHook(pResizeBuffers, (LPVOID)&hkResizeBuffers, (LPVOID*)&oResizeBuffers);
        MH_EnableHook(pResizeBuffers);

        pDummySwapChain->Release();
        pDummyDevice->Release();
        pDummyContext->Release();
        DestroyWindow(hWnd);
        UnregisterClass(wc.lpszClassName, wc.hInstance);

        std::cout << "[+] [DirectX 11] Present (slot 8) & ResizeBuffers (slot 13) HOOKED successfully!\n";
        return true;
    }

    if (hWnd) DestroyWindow(hWnd);
    UnregisterClass(wc.lpszClassName, wc.hInstance);
    std::cerr << "[-] [DirectX 11] Failed to create dummy swapchain (HRESULT: 0x" << std::hex << hr << std::dec << ")\n";
    return false;
}

void ArchipelagoUI::Shutdown()
{
    if (g_bImGuiInitialized)
    {
        ImGui_ImplDX11_Shutdown();
        ImGui_ImplWin32_Shutdown();
        if (g_pImGuiContext)
        {
            ImGui::DestroyContext(g_pImGuiContext);
            g_pImGuiContext = nullptr;
        }
        g_bImGuiInitialized = false;
    }
    if (g_mainRenderTargetView)
    {
        g_mainRenderTargetView->Release();
        g_mainRenderTargetView = nullptr;
    }
    DeleteCriticalSection(&s_csLog);
}

bool ArchipelagoUI::IsOpen() { return g_bShowMenu; }
void ArchipelagoUI::SetOpen(bool open)
{
    g_bShowMenu = open;
    if (g_bShowMenu)
    {
        ReleaseCapture();
        ClipCursor(NULL);
    }
}

void ArchipelagoUI::ToggleOpen()
{
    static auto s_lastToggle = std::chrono::steady_clock::now();
    auto now = std::chrono::steady_clock::now();
    auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(now - s_lastToggle).count();
    if (elapsedMs < 350)
        return;
    s_lastToggle = now;

    SetOpen(!g_bShowMenu);
    std::cout << "[UI] Menu YoRHa : " << (g_bShowMenu ? "OUVERT" : "FERME") << "\n";
}

void ArchipelagoUI::AddReceivedItem(const char* item, const char* sender)
{
    EnterCriticalSection(&s_csLog);
    std::string text = std::string(item) + " (de: " + std::string(sender) + ")";
    if (!s_activityLog.empty() && s_activityLog.back().text == text)
    {
        LeaveCriticalSection(&s_csLog);
        return;
    }
    APLogEntry entry;
    entry.text = text;
    entry.isItem = true;
    entry.isCheck = false;
    s_activityLog.push_back(entry);
    PushToast("ITEM RECU", std::string(item) + "  (de " + std::string(sender) + ")", true);
    if (s_activityLog.size() > 100)
        s_activityLog.erase(s_activityLog.begin());
    LeaveCriticalSection(&s_csLog);
}

void ArchipelagoUI::AddSentCheck(const char* location, const char* item)
{
    EnterCriticalSection(&s_csLog);
    APLogEntry entry;
    if (item && strlen(item) > 0 && strcmp(item, "CHEST") != 0 && strcmp(item, "WEAPON_CHEST") != 0)
    {
        entry.text = std::string(location) + " (" + std::string(item) + ")";
    }
    else
    {
        entry.text = std::string(location ? location : "Location Check");
    }
    entry.isItem = false;
    entry.isCheck = true;
    s_activityLog.push_back(entry);
    PushToast("CHECK ENVOYE", std::string(location ? location : "Location Check"), false);
    if (s_activityLog.size() > 100)
        s_activityLog.erase(s_activityLog.begin());
    LeaveCriticalSection(&s_csLog);
}

void ArchipelagoUI::SetAPStatus(bool connected, const char* slot, int checkedCount, int totalCount)
{
    s_bAPConnected = connected;
    s_strCurrentSlot = slot;
    s_iCheckedLocations = checkedCount;
    s_iTotalLocations = totalCount;
}

void ArchipelagoUI::AddNotification(const char* title, const char* text)
{
    EnterCriticalSection(&s_csLog);
    PushToast(title, text, false);
    LeaveCriticalSection(&s_csLog);
}

void ArchipelagoUI::ClearShopHints()
{
    EnterCriticalSection(&s_csLog);
    s_shopHints.clear();
    LeaveCriticalSection(&s_csLog);
}

void ArchipelagoUI::AddShopHint(const char* location, const char* item, const char* player, int flags)
{
    EnterCriticalSection(&s_csLog);
    s_shopHints.push_back({ location, item, player, flags });
    LeaveCriticalSection(&s_csLog);
}

void ArchipelagoUI::ClearLog()
{
    EnterCriticalSection(&s_csLog);
    s_activityLog.clear();
    LeaveCriticalSection(&s_csLog);
}
