#include "base/error_handling.h"

#include "GW/player/player.h"

#include "GW/context/character.h"
#include "GW/context/context.h"
#include "GW/context/world.h"

#include <cwchar>
#include <cwctype>

namespace {

int wcsncasecmp(const wchar_t* s1, const wchar_t* s2, size_t n) {
    if (s1 == s2) {
        return 0;
    }
    if (s1 == nullptr) {
        return -static_cast<int>(*s2);
    }
    if (s2 == nullptr) {
        return static_cast<int>(*s1);
    }

    for (size_t i = 0; i < n; ++i) {
        const wint_t c1 = std::towlower(s1[i]);
        const wint_t c2 = std::towlower(s2[i]);
        if (c1 != c2 || s1[i] == 0) {
            return static_cast<int>(s1[i] - s2[i]);
        }
    }
    return 0;
}

}  // namespace

namespace GW::player {

using RemoveActiveTitleFn = void(__cdecl*)();
using SetActiveTitleFn = void(__cdecl*)(uint32_t identifier);
using DepositFactionFn = void(__cdecl*)(uint32_t always_0, uint32_t allegiance, uint32_t amount);

extern RemoveActiveTitleFn g_remove_active_title_func;
extern SetActiveTitleFn g_set_active_title_func;
extern DepositFactionFn g_deposit_faction_func;

bool SetActiveTitle(GW::Constants::TitleID title_id) {
    if (!g_set_active_title_func) {
        return false;
    }
    g_set_active_title_func(static_cast<uint32_t>(title_id));
    return true;
}

bool RemoveActiveTitle() {
    if (!g_remove_active_title_func) {
        return false;
    }
    g_remove_active_title_func();
    return true;
}

uint32_t GetPlayerAgentId(uint32_t player_id) {
    auto* player = GetPlayerByID(player_id);
    return player ? player->agent_id : 0;
}

uint32_t GetAmountOfPlayersInInstance() {
    auto* world = Context::GetWorldContext();
    return world && world->players.valid() ? world->players.size() - 1U : 0U;
}

PlayerNumber GetPlayerNumber() {
    auto* character = Context::GetCharContext();
    return character ? character->player_number : 0;
}

Context::Player* GetPlayerByID(uint32_t player_id) {
    if (!player_id) {
        player_id = GetPlayerNumber();
    }

    auto* players = Context::GetPlayerArray();
    return players && player_id < players->size() ? &players->at(player_id) : nullptr;
}

wchar_t* GetPlayerName(uint32_t player_id) {
    auto* player = GetPlayerByID(player_id);
    return player ? player->name : nullptr;
}

wchar_t* SetPlayerName(uint32_t player_id, const wchar_t* replace_name) {
    auto* player = GetPlayerByID(player_id);
    return player ? std::wcsncpy(player->name_enc + 2, replace_name, 20) : nullptr;
}

bool ChangeSecondProfession(GW::Constants::Profession profession, uint32_t hero_index) {
    return skillbar::ChangeSecondProfession(profession, hero_index);
}

Context::Player* GetPlayerByName(const wchar_t* name) {
    if (!name) {
        return nullptr;
    }

    auto* players = Context::GetPlayerArray();
    if (!players) {
        return nullptr;
    }

    for (auto& player : *players) {
        if (!player.name) {
            continue;
        }
        if (!wcsncasecmp(name, player.name, 32)) {
            return &player;
        }
    }
    return nullptr;
}

Context::Title* GetTitleTrack(GW::Constants::TitleID title_id) {
    auto* titles = Context::GetTitleArray();
    if (!(titles && titles->size() > static_cast<uint32_t>(title_id))) {
        return nullptr;
    }
    return &titles->at(static_cast<uint32_t>(title_id));
}

GW::Constants::TitleID GetActiveTitleId() {
    auto* player = GetPlayerByID();
    if (!(player && player->active_title_tier)) {
        return GW::Constants::TitleID::None;
    }

    auto* titles = Context::GetTitleArray();
    if (!titles) {
        return GW::Constants::TitleID::None;
    }

    for (size_t title_id = 0; title_id < titles->size(); ++title_id) {
        if ((*titles)[static_cast<uint32_t>(title_id)].current_title_tier_index == player->active_title_tier) {
            return static_cast<GW::Constants::TitleID>(title_id);
        }
    }
    return GW::Constants::TitleID::None;
}

Context::Title* GetActiveTitle() {
    return GetTitleTrack(GetActiveTitleId());
}

std::vector<int> GetTitleIDs() {
    std::vector<int> title_ids;
    auto* titles = Context::GetTitleArray();
    if (!titles) {
        return title_ids;
    }

    title_ids.reserve(titles->size());
    for (size_t i = 0; i < titles->size(); ++i) {
        title_ids.push_back(static_cast<int>(i));
    }
    return title_ids;
}

Context::TitleClientData* GetTitleData(GW::Constants::TitleID title_id) {
    auto* title_data = Context::GetTitleClientData();
    return title_data ? &title_data[static_cast<uint32_t>(title_id)] : nullptr;
}

bool DepositFaction(uint32_t allegiance) {
    if (!g_deposit_faction_func) {
        return false;
    }
    g_deposit_faction_func(0, allegiance, 5000);
    return true;
}

}  // namespace GW::player
