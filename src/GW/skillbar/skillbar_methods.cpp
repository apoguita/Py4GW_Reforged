#include "base/error_handling.h"

#include "GW/skillbar/skillbar.h"

#include "base/hook_types.h"
#include "base/logger.h"

#include "GW/context/account.h"
#include "GW/context/context.h"
#include "GW/context/world.h"
#include "GW/game_thread/game_thread.h"
#include "GW/map/map.h"
#include "GW/ui/ui.h"

#include "GW/context/game.h"
#include "GW/context/party.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unordered_map>
#include <vector>

namespace {

constexpr char kBase64ToValue[128] = {
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
    -1, 0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
    -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1,
};

constexpr unsigned char kBase64Table[65] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

int WriteBits(int val, char* buff, int count = 6) {
    for (int i = 0; i < count; i++) {
        buff[i] = ((val >> i) & 1);
    }
    return count;
}

int ReadBits(char** str, int n) {
    int val = 0;
    char* s = *str;
    for (int i = 0; i < n; i++) {
        val |= (*s++ << i);
    }
    *str = s;
    return val;
}

}  // namespace

namespace GW::skillbar {

using UseSkillFn = void(__cdecl*)(uint32_t, uint32_t, uint32_t, uint32_t);
using LoadSkillsFn = void(__cdecl*)(uint32_t agent_id, uint32_t skill_ids_count, uint32_t* skill_ids);
using LoadAttributesFn = void(__cdecl*)(uint32_t agent_id, uint32_t attribute_count, uint32_t* attribute_ids, uint32_t* attribute_values);
using ChangeSecondaryFn = void(__cdecl*)(uint32_t agent_id, uint32_t profession);

extern uint32_t g_attribute_array_count;
extern UseSkillFn g_use_skill_func;
extern LoadSkillsFn g_load_skills_func;
extern LoadAttributesFn g_load_attributes_func;
extern ChangeSecondaryFn g_change_secondary_func;
extern std::unordered_map<PY4GW::HookEntry*, UseSkillCallback> g_use_skill_callbacks;

Skill* GetSkillConstantData(Constants::SkillID skill_id) {
    Skill* arr = Context::GetSkillArray();
    return arr ? &arr[static_cast<uint32_t>(skill_id)] : nullptr;
}

AttributeInfo* GetAttributeConstantData(Constants::Attribute attribute_id) {
    auto* attribute_info = Context::GetAttributeInfoArray();
    if (!attribute_info || g_attribute_array_count <= static_cast<uint32_t>(attribute_id))
        return nullptr;
    return &attribute_info[static_cast<uint32_t>(attribute_id)];
}

bool ChangeSecondProfession(Constants::Profession profession, uint32_t hero_index) {
    if (!g_change_secondary_func)
        return false;
    uint32_t agent_id = agent::GetHeroAgentID(hero_index);
    g_change_secondary_func(agent_id, static_cast<uint32_t>(profession));
    return true;
}

bool LoadSkillbar(Constants::SkillID* skills, size_t n_skills, uint32_t hero_index) {
    if (!g_load_skills_func)
        return false;
    const size_t bytes = n_skills * sizeof(uint32_t);
    uint32_t* skill_ids = static_cast<uint32_t*>(malloc(bytes));
    if (skill_ids == 0)
        return false;
    memset(skill_ids, 0, bytes);
    memcpy(skill_ids, skills, bytes);
    uint32_t agent_id = agent::GetHeroAgentID(hero_index);
    game_thread::Enqueue([agent_id, n_skills, skill_ids] {
        g_load_skills_func(agent_id, static_cast<uint32_t>(n_skills), skill_ids);
        free(skill_ids);
    });
    return true;
}

bool EncodeSkillTemplate(const SkillTemplate& in, char* build_code_result, size_t build_code_result_len) {
    const int bufSize = 1024;

    char bitStr[bufSize];
    size_t offset = 0;

    offset += WriteBits(14, &bitStr[offset], 4);
    offset += WriteBits(0, &bitStr[offset], 4);

    int bits_per_prof = 4;
    offset += WriteBits(static_cast<int>((bits_per_prof - 4) * 0.5), &bitStr[offset], 2);
    offset += WriteBits(static_cast<int>(in.primary), &bitStr[offset], bits_per_prof);
    offset += WriteBits(static_cast<int>(in.secondary), &bitStr[offset], bits_per_prof);

    int bits_per_attr = 4;
    int attrib_count = 0;
    for (const Attribute& attribute : in.attributes) {
        if (attribute.attribute == Constants::Attribute::None || attribute.points == 0) {
            continue;
        }
        int tmp = static_cast<int>(log2(static_cast<int>(attribute.attribute))) + 1;
        if (tmp > bits_per_attr) {
            bits_per_attr = tmp;
        }
        attrib_count++;
    }
    offset += WriteBits(attrib_count, &bitStr[offset], 4);
    offset += WriteBits(bits_per_attr - 4, &bitStr[offset], 4);
    for (const Attribute& attribute : in.attributes) {
        if (attribute.attribute != Constants::Attribute::None
            && attribute.points != 0) {
            offset += WriteBits(static_cast<int>(attribute.attribute), &bitStr[offset], bits_per_attr);
            offset += WriteBits(static_cast<int>(attribute.points), &bitStr[offset], 4);
        }
    }

    int bits_per_skill = 8;
    for (const Constants::SkillID skill : in.skills) {
        int tmp = static_cast<int>(log2(static_cast<int>(skill))) + 1;
        if (tmp > bits_per_skill) {
            bits_per_skill = tmp;
        }
    }
    offset += WriteBits(bits_per_skill - 8, &bitStr[offset], 4);
    for (const Constants::SkillID skill : in.skills) {
        offset += WriteBits(static_cast<int>(skill), &bitStr[offset], bits_per_skill);
    }
    offset += WriteBits(0, &bitStr[offset], 1);

    size_t backfill_length = 6 * 27;
    while (offset < backfill_length) {
        bitStr[offset++] = 0;
    }

    char* it = bitStr;
    size_t r = offset % 6;
    for (size_t i = 0; i < r; i++) {
        bitStr[offset++] = 0;
    }
    size_t needed_length = offset / 6;
    if (needed_length > build_code_result_len - 1) {
        char buf[256];
        snprintf(buf, sizeof(buf), "Result length %zu less than required build code length %zu\n", needed_length, build_code_result_len);
        Logger::Instance().LogError(buf, "skillbar");
        return false;
    }
    for (size_t i = 0; i < needed_length; i++) {
        int value = ReadBits(&it, 6);
        build_code_result[i] = static_cast<char>(kBase64Table[value]);
    }
    build_code_result[needed_length] = '\0';
    return true;
}

bool DecodeSkillTemplate(SkillTemplate* result, const char* temp) {
    const int SKILL_MAX = 3431;

    int skill_count = 0;
    int attrib_count = 0;

    size_t len = strlen(temp);

    const int bufSize = 1024;
    PY4GW_ASSERT((len * 6) < static_cast<size_t>(bufSize));
    char bitStr[bufSize];

    size_t bitStrLen = 0;
    for (size_t i = 0; i < len; i++) {
        int numeric_value = kBase64ToValue[static_cast<unsigned char>(temp[i])];
        if (numeric_value == -1) {
            char buf[256];
            snprintf(buf, sizeof(buf), "Invalid base64 character '%c' in string '%s'\n", temp[i], temp);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        bitStrLen += WriteBits(numeric_value, &bitStr[bitStrLen], 6);
    }

    char* it = bitStr;
    char* end = bitStr + 6 * len;

    int header = ReadBits(&it, 4);
    if (header != 0 && header != 14) {
        char buf[128];
        snprintf(buf, sizeof(buf), "Template header '%d' not valid.", header);
        Logger::Instance().LogError(buf, "skillbar");
        return false;
    }
    if (header == 14) ReadBits(&it, 4);
    int bits_per_prof = 2 * ReadBits(&it, 2) + 4;
    Constants::ProfessionByte prof1 = static_cast<Constants::ProfessionByte>(ReadBits(&it, bits_per_prof));
    Constants::ProfessionByte prof2 = static_cast<Constants::ProfessionByte>(ReadBits(&it, bits_per_prof));
    if (prof1 <= Constants::ProfessionByte::None || prof2 < Constants::ProfessionByte::None || prof1 > Constants::ProfessionByte::Dervish || prof2 > Constants::ProfessionByte::Dervish)
        return false;

    attrib_count = ReadBits(&it, 4);
    if (attrib_count >= static_cast<int>(_countof(result->attributes))) {
        char buf[256];
        snprintf(buf, sizeof(buf), "Found too many attributes %d in the template '%s'\n", attrib_count, temp);
        Logger::Instance().LogError(buf, "skillbar");
        return false;
    }

    int bits_per_attr = ReadBits(&it, 4) + 4;
    bool is_primary_attribute = false;
    for (int i = 0; i < attrib_count; i++) {
        uint32_t attrib_id = static_cast<uint32_t>(ReadBits(&it, bits_per_attr));
        int attrib_val = ReadBits(&it, 4);
        if (attrib_id >= g_attribute_array_count) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Attribute id %u is out of range. (count = %u)\n", attrib_id, g_attribute_array_count);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        if (attrib_val > 12) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Attribute id %u has a value of %d. (max = 12)\n", attrib_id, attrib_val);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        if (!attrib_val) {
            continue;
        }
        const auto profession = static_cast<Constants::ProfessionByte>(GetAttributeProfession(static_cast<Constants::Attribute>(attrib_id), &is_primary_attribute));
        if (profession != prof1 && profession != prof2) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Attribute id %u does not match build profession(s)\n", attrib_id);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        if (is_primary_attribute && profession != prof1) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Primary attribute id %u does not match primary profession\n", attrib_id);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        result->attributes[i].attribute = static_cast<Constants::Attribute>(attrib_id);
        result->attributes[i].points = static_cast<uint32_t>(attrib_val);
    }
    for (int i = attrib_count; i < static_cast<int>(_countof(result->attributes)); i++) {
        result->attributes[i].attribute = Constants::Attribute::None;
        result->attributes[i].points = 0;
    }

    int bits_per_skill = ReadBits(&it, 4) + 8;
    for (skill_count = 0; skill_count < static_cast<int>(_countof(result->skills)); skill_count++) {
        if (it + bits_per_skill > end) break;
        int skill_id = ReadBits(&it, bits_per_skill);
        if (skill_id > SKILL_MAX) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Skill id %d is out of range. (max = %d)\n", skill_id, SKILL_MAX);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        Skill* s = GetSkillConstantData(static_cast<Constants::SkillID>(skill_id));
        if (!s) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Failed to get info for skill ID %d\n", skill_id);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        if (s->profession != Constants::ProfessionByte::None && s->profession != prof1 && s->profession != prof2) {
            char buf[128];
            snprintf(buf, sizeof(buf), "Skill id %d doesn't match build profession(s)\n", skill_id);
            Logger::Instance().LogError(buf, "skillbar");
            return false;
        }
        result->skills[skill_count] = static_cast<Constants::SkillID>(skill_id);
    }
    for (int i = skill_count; i < static_cast<int>(_countof(result->skills)); i++) {
        result->skills[i] = Constants::SkillID::No_Skill;
    }

    result->primary = static_cast<Constants::Profession>(prof1);
    result->secondary = static_cast<Constants::Profession>(prof2);
    return true;
}

bool LoadSkillTemplate(const char* temp) {
    using Constants::Profession;

    if (map::GetInstanceType() != Constants::InstanceType::Outpost)
        return false;

    SkillTemplate skill_template;
    if (!DecodeSkillTemplate(&skill_template, temp)) {
        return false;
    }

    agent::AgentLiving* me = agent::GetControlledCharacter();
    if (!me) return false;

    const auto profession_state = GetAgentProfessionState(me->agent_id);
    if (!profession_state) {
        return false;
    }
    if (skill_template.primary != Profession::None && profession_state->primary != skill_template.primary) {
        if (IsPrimaryAttributeRequired(skill_template, skill_template.primary)) {
            return false;
        }
        if (IsProfessionRequired(skill_template, skill_template.primary)) {
            if (IsProfessionRequired(skill_template, skill_template.secondary)) {
                return false;
            }
            skill_template.secondary = skill_template.primary;
        }
    }
    if (skill_template.secondary != Profession::None && IsProfessionRequired(skill_template, skill_template.secondary)) {
        if (!profession_state->IsProfessionUnlocked(skill_template.secondary)) {
            return false;
        }
        if (profession_state->secondary != skill_template.secondary) {
            ChangeSecondProfession(skill_template.secondary);
        }
    }

    LoadSkillbar(skill_template.skills, _countof(skill_template.skills));
    SetAttributes(skill_template.attributes, _countof(skill_template.attributes));
    return true;
}

bool LoadSkillTemplate(const char* temp, uint32_t hero_index) {
    using Constants::Profession;

    if (map::GetInstanceType() != Constants::InstanceType::Outpost)
        return false;

    if (hero_index == 0)
        return LoadSkillTemplate(temp);

    SkillTemplate skill_template;
    if (!DecodeSkillTemplate(&skill_template, temp)) {
        return false;
    }

    const auto party_ctx = Context::GetPartyContext();
    if (!party_ctx || !party_ctx->player_party)
        return false;

    Context::PartyInfo* info = party_ctx->player_party;
    if (!info) return false;

    agent::AgentLiving* me = agent::GetControlledCharacter();
    if (!me) return false;
    Context::HeroPartyMemberArray& heroes = info->heroes;

    if (hero_index <= 0 || static_cast<int>(heroes.size()) < static_cast<int>(hero_index))
        return false;

    Context::HeroPartyMember& hero = heroes[hero_index - 1];
    if (hero.owner_player_id != me->login_number)
        return false;

    const auto profession_state = GetAgentProfessionState(hero.agent_id);
    if (!profession_state) {
        return false;
    }
    if (skill_template.primary != Constants::Profession::None && profession_state->primary != skill_template.primary) {
        if (IsPrimaryAttributeRequired(skill_template, skill_template.primary)) {
            return false;
        }
        if (IsProfessionRequired(skill_template, skill_template.primary)) {
            if (IsProfessionRequired(skill_template, skill_template.secondary)) {
                return false;
            }
            skill_template.secondary = skill_template.primary;
        }
    }
    if (skill_template.secondary != Constants::Profession::None && profession_state->secondary != skill_template.secondary) {
        ChangeSecondProfession(skill_template.secondary, hero_index);
    }

    LoadSkillbar(skill_template.skills, _countof(skill_template.skills), hero_index);
    SetAttributes(skill_template.attributes, _countof(skill_template.attributes), hero_index);
    return true;
}

bool SetAttributes(uint32_t attribute_count,
    uint32_t* attribute_ids, uint32_t* attribute_values, uint32_t hero_index) {
    if (!g_load_attributes_func)
        return false;
    uint32_t agent_id = agent::GetHeroAgentID(hero_index);
    g_load_attributes_func(agent_id, attribute_count, attribute_ids, attribute_values);
    return true;
}

bool SetAttributes(Attribute* attributes, size_t n_attributes, uint32_t hero_index) {
    uint32_t count;
    uint32_t attribute_ids[16];
    uint32_t attribute_values[16];

    for (count = 0; count < n_attributes; count++) {
        if (attributes[count].attribute == Constants::Attribute::None)
            break;
        attribute_ids[count] = static_cast<uint32_t>(attributes[count].attribute);
        attribute_values[count] = static_cast<uint32_t>(attributes[count].points);
    }

    return SetAttributes(count, attribute_ids, attribute_values, hero_index);
}

bool UseSkill(uint32_t slot, uint32_t target) {
    if (target && target != agent::GetTargetId())
        agent::ChangeTarget(target);
    return ui::Keypress(static_cast<ui::ControlAction>(static_cast<uint32_t>(ui::ControlAction::ControlAction_UseSkill1) + slot));
}

bool PointBlankUseSkill(uint32_t slot) {
    return ui::Keypress(static_cast<ui::ControlAction>(static_cast<uint32_t>(ui::ControlAction::ControlAction_UseSkill1) + slot));
}

bool UseSkillByID(uint32_t skill_id, uint32_t target) {
    int slot = GetSkillSlot(static_cast<Constants::SkillID>(skill_id));
    if (slot == -1)
        return false;
    return UseSkill(static_cast<uint32_t>(slot), target);
}

int GetSkillSlot(Constants::SkillID skill_id) {
    Skillbar* bar = GetPlayerSkillbar();
    if (!bar || !bar->IsValid()) return -1;
    for (int i = 0; i < 8; ++i) {
        if (bar->skills[i].skill_id == skill_id) {
            return i;
        }
    }
    return -1;
}

Skillbar* GetPlayerSkillbar() {
    SkillbarArray* sba = Context::GetSkillbarArray();
    uint32_t player_id = sba ? agent::GetControlledCharacterId() : 0;
    if (!player_id) return nullptr;
    for (auto& sb : *sba) {
        if (sb.agent_id == player_id)
            return &sb;
    }
    return nullptr;
}

Skillbar* GetHeroSkillbar(const uint32_t hero_index) {
    if (hero_index > 7) return nullptr;
    SkillbarArray* sba = Context::GetSkillbarArray();
    uint32_t player_id = sba ? agent::GetHeroAgentID(hero_index) : 0;
    if (!player_id) return nullptr;
    for (auto& sb : *sba) {
        if (sb.agent_id == player_id)
            return &sb;
    }
    return nullptr;
}

Skill* GetHoveredSkill() {
    const auto tooltip = ui::GetCurrentTooltip();
    if (!(tooltip && tooltip->payload_len == 0x14)) {
        return nullptr;
    }
    return GetSkillConstantData(*reinterpret_cast<Constants::SkillID*>(tooltip->payload));
}

SkillTemplate GetSkillTemplate(const uint32_t hero_index) {
    const auto agent_id = agent::GetHeroAgentID(hero_index);
    if (!agent_id) return {};
    const auto skillbar = GetHeroSkillbar(hero_index);
    if (!skillbar) return {};
    const auto skillbar_array = Context::GetSkillbarArray();
    if (!skillbar_array) return {};
    std::vector<Skillbar> skillbars(skillbar_array->begin(), skillbar_array->end());
    SkillTemplate skill_template{};
    for (size_t i = 0; i < _countof(skill_template.skills); i++) {
        const auto skill = GetSkillConstantData(skillbar->skills[i].skill_id);
        if (skill) {
            skill_template.skills[i] = skill->IsPvP() ? skill->skill_id_pvp : skill->skill_id;
        }
    }

    const auto profession_state = GetAgentProfessionState(agent_id);
    if (profession_state) {
        skill_template.primary = profession_state->primary;
        skill_template.secondary = profession_state->secondary;
    }
    auto* game_ctx = Context::GetGameContext();
    if (!game_ctx || !game_ctx->world) return skill_template;
    PartyAttributeArray& party_attributes = game_ctx->world->attributes;
    size_t attribute_idx = 0;
    for (const PartyAttribute& agent_attributes : party_attributes) {
        if (agent_attributes.agent_id != agent_id) {
            continue;
        }
        if (attribute_idx > _countof(skill_template.attributes)) {
            break;
        }
        for (size_t attribute_id = 0; attribute_id < _countof(agent_attributes.attribute); attribute_id++) {
            if (static_cast<Constants::Attribute>(attribute_id) > Constants::Attribute::Mysticism) {
                continue;
            }
            const Context::Attribute& attribute = agent_attributes.attribute[attribute_id];
            if (!attribute.level_base) {
                continue;
            }
            skill_template.attributes[attribute_idx].attribute = static_cast<Constants::Attribute>(attribute_id);
            skill_template.attributes[attribute_idx].points = attribute.level_base;
            attribute_idx++;
        }
    }
    return skill_template;
}

bool GetIsSkillUnlocked(Constants::SkillID skill_id) {
    auto* account_ctx = Context::GetAccountContext();
    if (!account_ctx) return false;
    auto& array = account_ctx->unlocked_account_skills;

    uint32_t index = static_cast<uint32_t>(skill_id);
    uint32_t real_index = index / 32;
    if (real_index >= array.size())
        return false;
    uint32_t shift = index % 32;
    uint32_t flag = 1U << shift;
    return (array[real_index] & flag) != 0;
}

bool GetIsSkillLearnt(Constants::SkillID skill_id) {
    auto* world_ctx = Context::GetWorldContext();
    if (!world_ctx) return false;
    auto& array = world_ctx->unlocked_character_skills;

    uint32_t index = static_cast<uint32_t>(skill_id);
    uint32_t real_index = index / 32;
    if (real_index >= array.size())
        return false;
    uint32_t shift = index % 32;
    uint32_t flag = 1U << shift;
    return (array[real_index] & flag) != 0;
}

void RegisterUseSkillCallback(
    PY4GW::HookEntry* entry,
    const UseSkillCallback& callback) {
    g_use_skill_callbacks.insert({ entry, callback });
}

void RemoveUseSkillCallback(
    PY4GW::HookEntry* entry) {
    auto it = g_use_skill_callbacks.find(entry);
    if (it != g_use_skill_callbacks.end())
        g_use_skill_callbacks.erase(it);
}

}  // namespace GW::skillbar
