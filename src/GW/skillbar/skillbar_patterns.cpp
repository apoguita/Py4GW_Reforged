#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/skillbar/skillbar.h"

namespace GW::Context {
extern Skill* g_skill_array_addr;
extern AttributeInfo* g_attribute_array_addr;
}

namespace GW::skillbar {

using UseSkillFn = void(__cdecl*)(uint32_t, uint32_t, uint32_t, uint32_t);
using LoadSkillsFn = void(__cdecl*)(uint32_t agent_id, uint32_t skill_ids_count, uint32_t* skill_ids);
using LoadAttributesFn = void(__cdecl*)(uint32_t agent_id, uint32_t attribute_count, uint32_t* attribute_ids, uint32_t* attribute_values);
using ChangeSecondaryFn = void(__cdecl*)(uint32_t agent_id, uint32_t profession);

extern UseSkillFn g_use_skill_func;
extern LoadSkillsFn g_load_skills_func;
extern LoadAttributesFn g_load_attributes_func;
extern ChangeSecondaryFn g_change_secondary_func;

bool ResolveSkillArray() {
    CrashContextScope context("startup", "skillbar", "resolve_skill_array");
    return PY4GW::Patterns::Resolve("skillbar.skill_array_addr", &Context::g_skill_array_addr);
}

bool ResolveAttributeArray() {
    CrashContextScope context("startup", "skillbar", "resolve_attribute_array");
    return PY4GW::Patterns::Resolve("skillbar.attribute_array_addr", &Context::g_attribute_array_addr);
}

bool ResolveUseSkillFunction() {
    CrashContextScope context("startup", "skillbar", "resolve_use_skill");
    return PY4GW::Patterns::Resolve("skillbar.use_skill_func", &g_use_skill_func);
}

bool ResolveTemplatesFunctions() {
    CrashContextScope context("startup", "skillbar", "resolve_templates_functions");
    return PY4GW::Patterns::Resolve("skillbar.change_secondary_func", &g_change_secondary_func) &&
        PY4GW::Patterns::Resolve("skillbar.load_attributes_func", &g_load_attributes_func) &&
        PY4GW::Patterns::Resolve("skillbar.load_skills_func", &g_load_skills_func);
}

}  // namespace GW::skillbar
