#pragma once

#include "base/error_handling.h"

#include "base/scanner.h"

#include <filesystem>
#include <string>
#include <type_traits>
#include <vector>

namespace PY4GW {

struct PatternObject {
    std::string name;
    std::string pattern;
    std::string mask;
    std::string assertion_file;
    std::string assertion_message;
    int offset = 0;
    int line_number = 0;
    int range = 0;
    ScannerSection section = ScannerSection::Text;
};

enum class ResolveFailureSeverity : uint8_t {
    Warning = 0,
    Error = 1,
};

enum class ResolveFailureAction : uint8_t {
    Continue = 0,
    Halt = 1,
};

struct PointerResolutionTraceStep {
    std::string name;
    std::string op;
    uintptr_t input = 0;
    uintptr_t output = 0;
    bool ok = false;
    std::string detail;
};

struct PointerResolutionResult {
    bool ok = false;
    uintptr_t value = 0;
    std::string name;
    std::string module;
    std::string selected_attempt;
    std::string failed_attempt;
    std::string failed_step;
    std::string message;
    ResolveFailureSeverity severity = ResolveFailureSeverity::Error;
    ResolveFailureAction action = ResolveFailureAction::Halt;
    std::vector<PointerResolutionTraceStep> trace;

    bool ShouldContinue() const {
        return ok || action == ResolveFailureAction::Continue;
    }
};

class Patterns {
public:
    static bool Initialize(const std::filesystem::path& directory = {});
    static const PatternObject* Get(const std::string& name);
    static PointerResolutionResult ResolvePointer(const std::string& name);

    template <typename T>
    static bool Resolve(const std::string& name, T* out) {
        if (!out) {
            return false;
        }
        const PointerResolutionResult result = ResolvePointer(name);
        if (result.ok) {
            if constexpr (std::is_integral_v<T>) {
                *out = static_cast<T>(result.value);
            } else if constexpr (std::is_enum_v<T>) {
                *out = static_cast<T>(result.value);
            } else if constexpr (std::is_pointer_v<T>) {
                *out = reinterpret_cast<T>(result.value);
            } else if constexpr (std::is_same_v<T, uintptr_t>) {
                *out = result.value;
            } else {
                *out = reinterpret_cast<T>(result.value);
            }
        } else {
            *out = T{};
        }
        return result.ShouldContinue();
    }
};

}  // namespace PY4GW
