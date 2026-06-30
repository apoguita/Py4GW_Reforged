#include "base/error_handling.h"

#include "GW/agent/agent.h"

#include "GW/context/agent.h"
#include "GW/context/context.h"
#include "GW/context/game.h"
#include "GW/context/gadget.h"
#include "GW/context/item.h"
#include "GW/context/world.h"
#include "GW/item/item.h"
#include "GW/map/map.h"
#include "GW/player/player.h"
#include "GW/ui/ui.h"

namespace GW::agent {
    using SendDialogFn = void(__cdecl*)(uint32_t dialog_id);
    using ChangeTargetFn = void(__cdecl*)(uint32_t agent_id, uint32_t auto_target_id);
    using CallTargetFn = void(__cdecl*)(Constants::CallTargetType type, uint32_t agent_id);
    using MoveToFn = void(__cdecl*)(float* pos);
    using DoWorldActionFn = void(__cdecl*)(Constants::WorldActionId action_id, uint32_t agent_id, bool suppress_call_target);

    extern MoveToFn g_move_to_func;
    extern uint32_t g_dialog_agent_id;
    extern uint32_t g_current_target_id;

    bool SendDialog(uint32_t dialog_id) {
        const auto* agent = GetAgentByID(g_dialog_agent_id);
        if (!agent) {
            return false;
        }
        if (agent->GetIsGadgetType()) {
            return ui::SendUIMessage(ui::UIMessage::kSendGadgetDialog, reinterpret_cast<void*>(static_cast<uintptr_t>(dialog_id)));
        }
        return ui::SendUIMessage(ui::UIMessage::kSendAgentDialog, reinterpret_cast<void*>(static_cast<uintptr_t>(dialog_id)));
    }

    bool GetIsAgentTargettable(const Agent* agent) {
        if (!agent) {
            return false;
        }
        if (const auto* living = agent->GetAsAgentLiving()) {
            if (living->IsPlayer()) {
                return true;
            }
            const auto* npc = GetNPCByID(living->player_number);
            return npc && (npc->npc_flags & 0x10000) == 0;
        }
        if (const auto* gadget = agent->GetAsAgentGadget()) {
            return GetAgentEncName(gadget) != nullptr;
        }
        return false;
    }

    uint32_t GetObservingId() {
        return Context::GetObservingId();
    }

    uint32_t GetControlledCharacterId() {
        auto* world = Context::GetWorldContext();
        return world && world->playerControlledChar ? world->playerControlledChar->agent_id : 0;
    }

    uint32_t GetTargetId() {
        return g_current_target_id;
    }

    AgentArray* GetAgentArray() {
        return Context::GetAgentArray();
    }

    Agent* GetAgentByID(uint32_t agent_id) {
        auto* agents = agent_id ? GetAgentArray() : nullptr;
        Agent* agent = agents && agent_id < agents->size() ? agents->at(agent_id) : nullptr;
        if (!agent) {
            return nullptr;
        }

        const auto* agent_context = Context::GetAgentContext();
        if (!(agent_context &&
            agent_context->agent_movement.size() > agent->agent_id &&
            agent_context->agent_movement[agent->agent_id])) {
            return nullptr;
        }

        return agent;
    }

    Agent* GetObservingAgent() {
        return GetAgentByID(GetObservingId());
    }

    Agent* GetTarget() {
        return GetAgentByID(GetTargetId());
    }

    Agent* GetPlayerByID(uint32_t player_id) {
        return GetAgentByID(player::GetPlayerAgentId(player_id));
    }

    AgentLiving* GetControlledCharacter() {
        const auto* agent = GetAgentByID(GetControlledCharacterId());
        return const_cast<AgentLiving*>(agent ? agent->GetAsAgentLiving() : nullptr);
    }

    bool IsObserving() {
        return !map::GetIsObserving() && GetControlledCharacterId() != GetObservingId();
    }

    AgentLiving* GetTargetAsAgentLiving() {
        auto* agent = GetTarget();
        return const_cast<AgentLiving*>(agent ? agent->GetAsAgentLiving() : nullptr);
    }

    uint32_t GetAmountOfPlayersInInstance() {
        auto* world = Context::GetWorldContext();
        return world && world->players.valid() ? world->players.size() - 1U : 0U;
    }

    MapAgent* GetMapAgentByID(uint32_t agent_id) {
        auto* agents = agent_id ? Context::GetMapAgentArray() : nullptr;
        return agents && agent_id < agents->size() ? &agents->at(agent_id) : nullptr;
    }

    NPC* GetNPCByID(uint32_t npc_id) {
        auto* npcs = Context::GetNPCArray();
        return npcs && npc_id < npcs->size() ? &npcs->at(npc_id) : nullptr;
    }


    bool ChangeTarget(AgentID agent_id) {
        ui::packet::kSendChangeTarget packet{ agent_id, 0 };
        return ui::SendUIMessage(ui::UIMessage::kSendChangeTarget, &packet);
    }

    bool ChangeTarget(const Agent* agent) {
        return agent ? ChangeTarget(agent->agent_id) : false;
    }

    bool Move(float x, float y, uint32_t zplane) {
        return Move(GamePos(x, y, zplane));
    }

    bool Move(GamePos pos) {
        if (!g_move_to_func) {
            return false;
        }
        float arg[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
        arg[0] = pos.x;
        arg[1] = pos.y;
        arg[2] = static_cast<float>(pos.zplane);
        g_move_to_func(arg);
        return true;
    }

    bool InteractAgent(const Agent* agent, bool call_target) {
        if (!agent) {
            return false;
        }

        if (call_target) {
            CallTarget(agent->agent_id);
        }

        ui::packet::kSendWorldAction packet{ Constants::WorldActionId::InteractEnemy, agent->agent_id, call_target };
        if (agent->GetIsItemType()) {
            packet.action_id = Constants::WorldActionId::InteractItem;
            return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
        }
        if (agent->GetIsGadgetType()) {
            packet.action_id = Constants::WorldActionId::InteractGadget;
            return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
        }
        const auto* living = agent->GetAsAgentLiving();
        if (!living) {
            return false;
        }
        if (living->allegiance == Constants::Allegiance::Enemy) {
            packet.action_id = Constants::WorldActionId::InteractEnemy;
            return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
        }
        if (living->allegiance == Constants::Allegiance::Npc_Minipet) {
            packet.action_id = Constants::WorldActionId::InteractNPC;
            return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
        }
        packet.action_id = Constants::WorldActionId::InteractPlayerOrOther;
        return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
    }

    bool CallTarget(uint32_t agent_id) {
        const auto* agent = GetAgentByID(agent_id);
        const auto* living = agent ? agent->GetAsAgentLiving() : nullptr;
        if (!living) {
            return false;
        }

        if (living->allegiance == Constants::Allegiance::Enemy) {
            const auto* target = GetTarget();
            if (!target) {
                return false;
            }

            ui::packet::kSendCallTarget packet{
                Constants::CallTargetType::AttackingOrTargetting,
                target->agent_id
            };
            return ui::SendUIMessage(ui::UIMessage::kSendCallTarget, &packet);
        }

        ui::packet::kSendWorldAction packet{
            Constants::WorldActionId::InteractPlayerOrOther,
            living->agent_id,
            true
        };
        return ui::SendUIMessage(ui::UIMessage::kSendWorldAction, &packet);
    }

    wchar_t* GetPlayerNameByLoginNumber(uint32_t login_number) {
        return player::GetPlayerName(login_number);
    }

    uint32_t GetAgentIdByLoginNumber(uint32_t login_number) {
        auto* player_entry = player::GetPlayerByID(login_number);
        return player_entry ? player_entry->agent_id : 0;
    }

    AgentID GetHeroAgentID(uint32_t hero_index) {
        auto* world = Context::GetWorldContext();
        auto* hero_flags = world && world->hero_flags.valid() ? &world->hero_flags : nullptr;
        return hero_flags && hero_index < hero_flags->size() ? hero_flags->at(hero_index).agent_id : 0;
    }

    wchar_t* GetAgentEncName(uint32_t agent_id) {
        const auto* agent = GetAgentByID(agent_id);
        if (agent) {
            return GetAgentEncName(agent);
        }

        auto* world = Context::GetWorldContext();
        auto* agent_infos = world && world->agent_infos.valid() ? &world->agent_infos : nullptr;
        if (!(agent_infos && agent_id < agent_infos->size())) {
            return nullptr;
        }
        return agent_infos->at(agent_id).name_enc;
    }

    wchar_t* GetAgentEncName(const Agent* agent) {
        if (!agent) {
            return nullptr;
        }

        if (agent->GetIsLivingType()) {
            const auto* ag = agent->GetAsAgentLiving();
            if (ag->login_number) {
                auto* players = Context::GetPlayerArray();
                if (players && ag->login_number < players->size()) {
                    return players->at(ag->login_number).name_enc;
                }
                return nullptr;
            }

            auto* world = Context::GetWorldContext();
            auto* agent_infos = world && world->agent_infos.valid() ? &world->agent_infos : nullptr;
            if (!(agent_infos && ag->agent_id < agent_infos->size())) {
                return nullptr;
            }
            if (agent_infos->at(ag->agent_id).name_enc) {
                return agent_infos->at(ag->agent_id).name_enc;
            }
            auto* npc = GetNPCByID(ag->player_number);
            return npc ? npc->name_enc : nullptr;
        }

        if (agent->GetIsGadgetType()) {
            auto* agent_context = Context::GetAgentContext();
            auto* game_context = Context::GetGameContext();
            auto* gadget_context = game_context ? game_context->gadget : nullptr;
            if (!(agent_context && gadget_context && agent_context->agent_summary_info.valid() && agent->agent_id < agent_context->agent_summary_info.size())) {
                return nullptr;
            }

            auto* gadget_ids = agent_context->agent_summary_info[agent->agent_id].extra_info_sub;
            if (!gadget_ids) {
                return nullptr;
            }
            if (gadget_ids->gadget_name_enc) {
                return gadget_ids->gadget_name_enc;
            }
            const size_t id = gadget_ids->gadget_id;
            return gadget_context->gadget_info.size() > id ? gadget_context->gadget_info[id].name_enc : nullptr;
        }

        if (agent->GetIsItemType()) {
            const auto* ag = agent->GetAsAgentItem();
            auto* item = item::GetItemById(ag->item_id);
            return item ? item->name_enc : nullptr;
        }

        return nullptr;
    }

    bool AsyncGetAgentName(const Agent* agent, std::wstring& name) {
        wchar_t* str = GetAgentEncName(agent);
        if (!str) {
            return false;
        }
        ui::AsyncDecodeStr(str, &name);
        return true;
    }

    bool AsyncDecodeStr(const wchar_t* enc_str, std::wstring& res) {
        if (!enc_str) {
            return false;
        }
        ui::AsyncDecodeStr(enc_str, &res);
        return true;
    }

}  // namespace GW::agent
