#pragma once

#include "GW/common/game_pos.h"
#include "GW/context/agent.h"
#include "GW/context/npc.h"
#include "GW/context/player.h"

#include <cstdint>
#include <string>

namespace GW::agent {

    using Agent = Context::Agent;
    using AgentArray = Context::AgentArray;
    using AgentGadget = Context::AgentGadget;
    using AgentID = Context::AgentID;
    using AgentItem = Context::AgentItem;
    using AgentLiving = Context::AgentLiving;
    using MapAgent = Context::MapAgent;
    using MapAgentArray = Context::MapAgentArray;
    using NPC = Context::NPC;
    using NPCArray = Context::NPCArray;
    using Player = Context::Player;
    using PlayerArray = Context::PlayerArray;

    bool Initialize();
    void Shutdown();

    bool SendDialog(uint32_t dialog_id);
    bool GetIsAgentTargettable(const Agent* agent);

    uint32_t GetObservingId();
    uint32_t GetControlledCharacterId();
    uint32_t GetTargetId();

    Agent* GetAgentByID(uint32_t id);

    Agent* GetObservingAgent();

    Agent* GetTarget();

    Agent* GetPlayerByID(uint32_t player_id);
    AgentLiving* GetControlledCharacter();
    bool IsObserving();
    AgentLiving* GetTargetAsAgentLiving();

    uint32_t GetAmountOfPlayersInInstance();

    MapAgent* GetMapAgentByID(uint32_t agent_id);
    NPC* GetNPCByID(uint32_t npc_id);

    bool ChangeTarget(const Agent* agent);
    bool ChangeTarget(AgentID agent_id);

    bool Move(float x, float y, uint32_t zplane = 0);
    bool Move(GamePos pos);

    bool InteractAgent(const Agent* agent, bool call_target = false);
    bool CallTarget(uint32_t agent_id);

    wchar_t* GetPlayerNameByLoginNumber(uint32_t login_number);
    uint32_t GetAgentIdByLoginNumber(uint32_t login_number);
    AgentID GetHeroAgentID(uint32_t hero_index);

    wchar_t* GetAgentEncName(const Agent* agent);
    wchar_t* GetAgentEncName(uint32_t agent_id);

    bool AsyncGetAgentName(const Agent* agent, std::wstring& name);
    bool AsyncDecodeStr(const wchar_t* enc_str, std::wstring& res);

}  // namespace GW::agent

namespace GW {
namespace Agents = agent;
}
