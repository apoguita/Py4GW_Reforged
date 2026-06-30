#pragma once

#include "GW/common/constants/constants.h"
#include "GW/context/quest.h"

#include <cstdint>
#include <string>

namespace GW::quest {

bool Initialize();
void Shutdown();

bool SetActiveQuestId(GW::Constants::QuestID quest_id);
bool SetActiveQuest(Context::Quest* quest);
bool AbandonQuest(Context::Quest* quest);
bool AbandonQuestId(GW::Constants::QuestID quest_id);

Context::Quest* GetActiveQuest();
Context::Quest* GetQuest(GW::Constants::QuestID quest_id);

bool GetQuestEntryGroupName(GW::Constants::QuestID quest_id, wchar_t* out, size_t out_len);

bool RequestQuestInfo(const Context::Quest* quest, bool update_markers = false);
bool RequestQuestInfoId(GW::Constants::QuestID quest_id, bool update_markers = false);

void AsyncGetQuestName(const Context::Quest* quest, std::wstring& res);
void AsyncGetQuestDescription(const Context::Quest* quest, std::wstring& res);
void AsyncGetQuestObjectives(const Context::Quest* quest, std::wstring& res);
void AsyncGetQuestLocation(const Context::Quest* quest, std::wstring& res);
void AsyncGetQuestNPC(const Context::Quest* quest, std::wstring& res);
void AsyncDecodeAnyEncStr(const wchar_t* str, std::wstring& res);

}  // namespace GW::quest
