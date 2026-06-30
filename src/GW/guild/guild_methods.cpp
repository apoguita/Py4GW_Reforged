#include "base/error_handling.h"

#include "GW/guild/guild.h"

#include "GW/context/context.h"
#include "GW/context/guild.h"
#include "GW/map/map.h"
#include "GW/ui/ui.h"

namespace GW::guild {

wchar_t* GetPlayerGuildAnnouncer() {
    auto* guild = Context::GetGuildContext();
    return guild ? guild->announcement_author : nullptr;
}

wchar_t* GetPlayerGuildAnnouncement() {
    auto* guild = Context::GetGuildContext();
    return guild ? guild->announcement : nullptr;
}

uint32_t GetPlayerGuildIndex() {
    auto* guild = Context::GetGuildContext();
    return guild ? guild->player_guild_index : 0;
}

Context::Guild* GetPlayerGuild() {
    return GetGuildInfo(GetPlayerGuildIndex());
}

Context::Guild* GetCurrentGH() {
    auto* map_info = map::GetCurrentMapInfo();
    if (!map_info || map_info->type != Constants::RegionType::GuildHall) {
        return nullptr;
    }

    auto* guilds = Context::GetGuildArray();
    if (!guilds) {
        return nullptr;
    }

    for (auto* guild : *guilds) {
        if (guild) {
            return guild;
        }
    }
    return nullptr;
}

Context::Guild* GetGuildInfo(uint32_t guild_id) {
    auto* guilds = Context::GetGuildArray();
    return guilds && guild_id < guilds->size() ? guilds->at(guild_id) : nullptr;
}

bool TravelGH() {
    auto* guild = Context::GetGuildContext();
    return guild ? TravelGH(guild->player_gh_key) : false;
}

bool TravelGH(Context::GHKey key) {
    return ui::SendUIMessage(ui::UIMessage::kGuildHall, &key);
}

bool LeaveGH() {
    return ui::SendUIMessage(ui::UIMessage::kLeaveGuildHall);
}

}  // namespace GW::guild
