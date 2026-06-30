#include "base/error_handling.h"

#include "GW/quest/quest.h"

#include "GW/context/context.h"
#include "GW/context/world.h"
#include "GW/ui/ui.h"

#include <cwchar>

namespace GW::quest {

using RequestQuestInfoFn = void(__cdecl*)(uint32_t identifier);
using RequestQuestDataFn = void(__cdecl*)(uint32_t identifier, bool update_markers);
using DoActionFn = void(__cdecl*)(uint32_t identifier);

extern RequestQuestInfoFn g_request_quest_info_func;
extern RequestQuestDataFn g_request_quest_data_func;
extern DoActionFn g_set_active_quest_func;
extern DoActionFn g_abandon_quest_func;

bool SetActiveQuestId(GW::Constants::QuestID quest_id) {
    if (!(g_set_active_quest_func && GetQuest(quest_id))) {
        return false;
    }
    g_set_active_quest_func(static_cast<uint32_t>(quest_id));
    return true;
}

bool SetActiveQuest(Context::Quest* quest) {
    return quest && SetActiveQuestId(quest->quest_id);
}

bool AbandonQuest(Context::Quest* quest) {
    return quest && AbandonQuestId(quest->quest_id);
}

bool AbandonQuestId(GW::Constants::QuestID quest_id) {
    if (!(g_abandon_quest_func && GetQuest(quest_id))) {
        return false;
    }
    g_abandon_quest_func(static_cast<uint32_t>(quest_id));
    return true;
}

Context::Quest* GetActiveQuest() {
    return GetQuest(Context::GetActiveQuestId());
}

Context::Quest* GetQuest(GW::Constants::QuestID quest_id) {
    if (quest_id == static_cast<GW::Constants::QuestID>(0)) {
        return nullptr;
    }

    auto* quest_log = Context::GetQuestLog();
    if (!quest_log) {
        return nullptr;
    }

    for (auto& quest : *quest_log) {
        if (quest.quest_id == quest_id) {
            return &quest;
        }
    }
    return nullptr;
}

bool GetQuestEntryGroupName(GW::Constants::QuestID quest_id, wchar_t* out, size_t out_len) {
    const auto* quest = GetQuest(quest_id);
    if (!(quest && out && out_len)) {
        return false;
    }

    switch (quest->log_state & 0xF0U) {
    case 0x20:
        return std::swprintf(out, out_len, L"\x564") != -1;
    case 0x40:
        return quest->location && std::swprintf(out, out_len, L"\x8102\x1978\x10A%s\x1", quest->location) != -1;
    case 0x00:
        return quest->location && std::swprintf(out, out_len, L"\x565\x10A%s\x1", quest->location) != -1;
    case 0x10:
        break;
    default:
        break;
    }
    return false;
}

bool RequestQuestInfo(const Context::Quest* quest, bool update_markers) {
    return quest && RequestQuestInfoId(quest->quest_id, update_markers);
}

bool RequestQuestInfoId(GW::Constants::QuestID quest_id, bool update_markers) {
    if (!(g_request_quest_info_func && g_request_quest_data_func && GetQuest(quest_id))) {
        return false;
    }

    g_request_quest_info_func(static_cast<uint32_t>(quest_id));
    g_request_quest_data_func(static_cast<uint32_t>(quest_id), update_markers);
    return true;
}

void AsyncGetQuestName(const Context::Quest* quest, std::wstring& res) {
    if (quest && quest->name) {
        ui::AsyncDecodeStr(quest->name, &res);
    }
}

void AsyncDecodeAnyEncStr(const wchar_t* str, std::wstring& res) {
    if (str) {
        ui::AsyncDecodeStr(str, &res);
    }
}

void AsyncGetQuestDescription(const Context::Quest* quest, std::wstring& res) {
    if (quest && quest->description) {
        ui::AsyncDecodeStr(quest->description, &res);
    }
}

void AsyncGetQuestObjectives(const Context::Quest* quest, std::wstring& res) {
    if (quest && quest->objectives) {
        ui::AsyncDecodeStr(quest->objectives, &res);
    }
}

void AsyncGetQuestLocation(const Context::Quest* quest, std::wstring& res) {
    if (quest && quest->location) {
        ui::AsyncDecodeStr(quest->location, &res);
    }
}

void AsyncGetQuestNPC(const Context::Quest* quest, std::wstring& res) {
    if (quest && quest->npc) {
        ui::AsyncDecodeStr(quest->npc, &res);
    }
}

}  // namespace GW::quest
