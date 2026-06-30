#pragma once

#include "GW/common/constants/constants.h"
#include "GW/context/player.h"
#include "GW/context/title.h"
#include "GW/skillbar/skillbar.h"

#include <cstdint>
#include <vector>

namespace GW::player {

using PlayerNumber = uint32_t;

bool Initialize();
void Shutdown();

bool SetActiveTitle(GW::Constants::TitleID title_id);
bool RemoveActiveTitle();

uint32_t GetPlayerAgentId(uint32_t player_id);
uint32_t GetAmountOfPlayersInInstance();

PlayerNumber GetPlayerNumber();

Context::Player* GetPlayerByID(uint32_t player_id = 0);
wchar_t* GetPlayerName(uint32_t player_id = 0);
wchar_t* SetPlayerName(uint32_t player_id, const wchar_t* replace_name);

bool ChangeSecondProfession(GW::Constants::Profession profession, uint32_t hero_index = 0);

Context::Player* GetPlayerByName(const wchar_t* name);

Context::Title* GetTitleTrack(GW::Constants::TitleID title_id);
GW::Constants::TitleID GetActiveTitleId();
Context::Title* GetActiveTitle();
std::vector<int> GetTitleIDs();
Context::TitleClientData* GetTitleData(GW::Constants::TitleID title_id);

bool DepositFaction(uint32_t allegiance);

}  // namespace GW::player
