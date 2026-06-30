#include "base/error_handling.h"

#include "base/patterns.h"

#include "base/process_manager.h"
#include "base/logger.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

using json = nlohmann::json;

std::unordered_map<std::string, PY4GW::PatternObject> g_patterns;
enum class ResolverStepOp : uint8_t {
    PatternScan = 0,
    PatternScanInRange,
    ToFunctionStart,
    FunctionFromNearCall,
    FindUseOfString,
    Dereference,
    ReadU32,
    Add,
    Divide,
    ValidateSection,
};

struct ResolverStepObject {
    std::string name;
    ResolverStepOp op = ResolverStepOp::PatternScan;
    std::string input;
    std::string output;
    std::string pattern_name;
    std::string literal;
    std::string start;
    std::string end;
    int start_add = 0;
    int end_add = 0;
    int value = 0;
    int nth = 0;
    int scan_range = 0xFF;
    bool check_valid_ptr = true;
    bool wide_string = false;
    bool has_section = false;
    PY4GW::ScannerSection section = PY4GW::ScannerSection::Text;
};

struct ResolverAttemptObject {
    std::string name;
    std::vector<ResolverStepObject> steps;
};

struct ResolverObject {
    std::string name;
    std::string module;
    PY4GW::ResolveFailureSeverity severity = PY4GW::ResolveFailureSeverity::Error;
    PY4GW::ResolveFailureAction action = PY4GW::ResolveFailureAction::Halt;
    std::vector<ResolverAttemptObject> attempts;
};

std::unordered_map<std::string, ResolverObject> g_resolvers;
bool g_initialized = false;

bool CanReadMemory(uintptr_t address, size_t size) {
    if (!(address && size)) {
        return false;
    }

    MEMORY_BASIC_INFORMATION mbi = {};
    if (::VirtualQuery(reinterpret_cast<LPCVOID>(address), &mbi, sizeof(mbi)) != sizeof(mbi)) {
        return false;
    }
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return false;
    }

    const DWORD readable_mask =
        PAGE_READONLY |
        PAGE_READWRITE |
        PAGE_WRITECOPY |
        PAGE_EXECUTE_READ |
        PAGE_EXECUTE_READWRITE |
        PAGE_EXECUTE_WRITECOPY;
    if ((mbi.Protect & readable_mask) == 0) {
        return false;
    }

    const auto region_start = reinterpret_cast<uintptr_t>(mbi.BaseAddress);
    const auto region_end = region_start + mbi.RegionSize;
    return address >= region_start && (address + size) <= region_end;
}

std::string QualifyName(const std::string& name_space, const std::string& name) {
    if (name_space.empty() || name.find('.') != std::string::npos) {
        return name;
    }
    return name_space + "." + name;
}

std::string ModuleFromQualifiedName(const std::string& name) {
    const size_t dot = name.find('.');
    if (dot == std::string::npos) {
        return "patterns";
    }
    return name.substr(0, dot);
}

PY4GW::ScannerSection ParseSection(const std::string& text) {
    std::string lowered = text;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });

    if (lowered == "rdata") {
        return PY4GW::ScannerSection::RData;
    }
    if (lowered == "data") {
        return PY4GW::ScannerSection::Data;
    }
    return PY4GW::ScannerSection::Text;
}

bool ParseInt(const std::string& text, int* value) {
    if (!value) {
        return false;
    }

    try {
        size_t parsed = 0;
        const long long result = std::stoll(text, &parsed, 0);
        if (parsed != text.size() ||
            result < std::numeric_limits<int>::min() ||
            result > std::numeric_limits<int>::max()) {
            return false;
        }
        *value = static_cast<int>(result);
        return true;
    }
    catch (...) {
        return false;
    }
}

bool DecodePatternLiteral(const std::string& literal, std::string* bytes) {
    if (!bytes) {
        return false;
    }

    bytes->clear();
    for (size_t i = 0; i < literal.size(); ++i) {
        if (literal[i] != '\\') {
            bytes->push_back(literal[i]);
            continue;
        }
        if (i + 1 >= literal.size()) {
            return false;
        }

        const char escape = literal[++i];
        switch (escape) {
        case '\\':
            bytes->push_back('\\');
            break;
        case '0':
            bytes->push_back('\0');
            break;
        case 'n':
            bytes->push_back('\n');
            break;
        case 'r':
            bytes->push_back('\r');
            break;
        case 't':
            bytes->push_back('\t');
            break;
        case 'x': {
            if (i + 2 >= literal.size()) {
                return false;
            }
            const char hi = literal[++i];
            const char lo = literal[++i];
            if (!std::isxdigit(static_cast<unsigned char>(hi)) || !std::isxdigit(static_cast<unsigned char>(lo))) {
                return false;
            }
            const std::string hex = { hi, lo };
            bytes->push_back(static_cast<char>(std::stoi(hex, nullptr, 16)));
            break;
        }
        default:
            bytes->push_back(escape);
            break;
        }
    }

    return true;
}

bool ParseBool(const json& value, bool* out) {
    if (!out) {
        return false;
    }
    if (value.is_boolean()) {
        *out = value.get<bool>();
        return true;
    }
    if (value.is_number_integer()) {
        *out = value.get<int>() != 0;
        return true;
    }
    if (value.is_string()) {
        std::string lowered = value.get<std::string>();
        std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
            return static_cast<char>(std::tolower(c));
        });
        if (lowered == "true" || lowered == "1" || lowered == "yes") {
            *out = true;
            return true;
        }
        if (lowered == "false" || lowered == "0" || lowered == "no") {
            *out = false;
            return true;
        }
    }
    return false;
}

bool ParseIntValue(const json& value, int* out) {
    if (!out) {
        return false;
    }
    if (value.is_number_integer()) {
        const auto raw = value.get<long long>();
        if (raw < std::numeric_limits<int>::min() || raw > std::numeric_limits<int>::max()) {
            return false;
        }
        *out = static_cast<int>(raw);
        return true;
    }
    if (value.is_string()) {
        return ParseInt(value.get<std::string>(), out);
    }
    return false;
}

bool ParseSeverity(const std::string& text, PY4GW::ResolveFailureSeverity* severity) {
    if (!severity) {
        return false;
    }
    std::string lowered = text;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    if (lowered == "warning" || lowered == "warn") {
        *severity = PY4GW::ResolveFailureSeverity::Warning;
        return true;
    }
    if (lowered == "error") {
        *severity = PY4GW::ResolveFailureSeverity::Error;
        return true;
    }
    return false;
}

bool ParseAction(const std::string& text, PY4GW::ResolveFailureAction* action) {
    if (!action) {
        return false;
    }
    std::string lowered = text;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    if (lowered == "continue") {
        *action = PY4GW::ResolveFailureAction::Continue;
        return true;
    }
    if (lowered == "halt" || lowered == "abort" || lowered == "fail") {
        *action = PY4GW::ResolveFailureAction::Halt;
        return true;
    }
    return false;
}

bool ParseStepOp(const std::string& text, ResolverStepOp* op) {
    if (!op) {
        return false;
    }
    std::string lowered = text;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    if (lowered == "scan" || lowered == "pattern_scan" || lowered == "pattern") {
        *op = ResolverStepOp::PatternScan;
        return true;
    }
    if (lowered == "scan_in_range" || lowered == "pattern_scan_in_range" || lowered == "find_in_range") {
        *op = ResolverStepOp::PatternScanInRange;
        return true;
    }
    if (lowered == "to_function_start") {
        *op = ResolverStepOp::ToFunctionStart;
        return true;
    }
    if (lowered == "function_from_near_call") {
        *op = ResolverStepOp::FunctionFromNearCall;
        return true;
    }
    if (lowered == "find_use_of_string" || lowered == "use_of_string" || lowered == "scan_use_of_string") {
        *op = ResolverStepOp::FindUseOfString;
        return true;
    }
    if (lowered == "deref" || lowered == "dereference") {
        *op = ResolverStepOp::Dereference;
        return true;
    }
    if (lowered == "read_u32" || lowered == "read_uint32") {
        *op = ResolverStepOp::ReadU32;
        return true;
    }
    if (lowered == "add") {
        *op = ResolverStepOp::Add;
        return true;
    }
    if (lowered == "divide" || lowered == "div") {
        *op = ResolverStepOp::Divide;
        return true;
    }
    if (lowered == "validate_section") {
        *op = ResolverStepOp::ValidateSection;
        return true;
    }
    return false;
}

std::string FormatPointer(uintptr_t value) {
    std::ostringstream stream;
    stream << "0x" << std::hex << std::uppercase << value;
    return stream.str();
}

void AppendTraceSummary(const std::vector<PY4GW::PointerResolutionTraceStep>& trace, std::string* out) {
    if (!out || trace.empty()) {
        return;
    }
    std::ostringstream stream;
    stream << " trace=[";
    for (size_t i = 0; i < trace.size(); ++i) {
        if (i) {
            stream << "; ";
        }
        const auto& step = trace[i];
        stream << step.name << ":" << step.op
               << "(in=" << FormatPointer(step.input)
               << ", out=" << FormatPointer(step.output)
               << ", ok=" << (step.ok ? "true" : "false");
        if (!step.detail.empty()) {
            stream << ", detail=" << step.detail;
        }
        stream << ")";
    }
    stream << "]";
    out->append(stream.str());
}

void LogResolutionFailure(const PY4GW::PointerResolutionResult& result) {
    std::string message = "Pointer resolution failed: " + result.name;
    if (!result.failed_attempt.empty()) {
        message += " attempt=" + result.failed_attempt;
    }
    if (!result.failed_step.empty()) {
        message += " step=" + result.failed_step;
    }
    if (!result.message.empty()) {
        message += " reason=" + result.message;
    }
    message += " policy=";
    message += (result.action == PY4GW::ResolveFailureAction::Halt) ? "halt" : "continue";
    AppendTraceSummary(result.trace, &message);

    if (result.severity == PY4GW::ResolveFailureSeverity::Warning) {
        Logger::Instance().Log(result.module, MessageType::Warning, message);
    } else {
        Logger::Instance().Log(result.module, MessageType::Error, message);
    }
}

bool ParseResolverStep(
    const std::string& name_space,
    const std::string& resolver_name,
    const json& value,
    ResolverStepObject* step)
{
    if (!(step && value.is_object())) {
        return false;
    }

    if (!ParseStepOp(value.value("op", ""), &step->op)) {
        Logger::Instance().LogError("Invalid resolver step op in " + resolver_name, "patterns");
        return false;
    }

    step->name = value.value("name", value.value("op", ""));
    step->input = value.value("in", "");
    step->output = value.value("out", "");
    if (step->output.empty()) {
        step->output = "value";
    }
    const std::string raw_pattern_name = value.value("pattern", "");
    step->pattern_name = raw_pattern_name.empty() ? std::string() : QualifyName(name_space, raw_pattern_name);
    step->literal = value.value("literal", "");
    step->start = value.value("start", "");
    step->end = value.value("end", "");

    const auto parse_optional_int = [&](const char* key, int* target) -> bool {
        if (!value.contains(key)) {
            return true;
        }
        return ParseIntValue(value.at(key), target);
    };

    bool ok = parse_optional_int("start_add", &step->start_add) &&
        parse_optional_int("end_add", &step->end_add) &&
        parse_optional_int("value", &step->value) &&
        parse_optional_int("nth", &step->nth) &&
        parse_optional_int("scan_range", &step->scan_range);
    if (!ok) {
        Logger::Instance().LogError("Invalid numeric resolver step field in " + resolver_name, "patterns");
        return false;
    }

    if (value.contains("check_valid_ptr") &&
        !ParseBool(value.at("check_valid_ptr"), &step->check_valid_ptr)) {
        Logger::Instance().LogError("Invalid check_valid_ptr field in " + resolver_name, "patterns");
        return false;
    }
    if (value.contains("wide") &&
        !ParseBool(value.at("wide"), &step->wide_string)) {
        Logger::Instance().LogError("Invalid wide field in " + resolver_name, "patterns");
        return false;
    }

    if (value.contains("section")) {
        step->has_section = true;
        step->section = ParseSection(value.value("section", "text"));
    }

    if ((step->op == ResolverStepOp::PatternScan || step->op == ResolverStepOp::PatternScanInRange) &&
        step->pattern_name.empty()) {
        Logger::Instance().LogError("Resolver step missing pattern reference in " + resolver_name, "patterns");
        return false;
    }
    if ((step->op == ResolverStepOp::ToFunctionStart ||
         step->op == ResolverStepOp::FunctionFromNearCall ||
         step->op == ResolverStepOp::Dereference ||
         step->op == ResolverStepOp::ReadU32 ||
         step->op == ResolverStepOp::Add ||
         step->op == ResolverStepOp::Divide ||
         step->op == ResolverStepOp::ValidateSection) &&
        step->input.empty()) {
        Logger::Instance().LogError("Resolver step missing input reference in " + resolver_name, "patterns");
        return false;
    }
    if (step->op == ResolverStepOp::FindUseOfString &&
        step->pattern_name.empty() &&
        step->literal.empty()) {
        Logger::Instance().LogError("Resolver find_use_of_string step missing pattern/literal in " + resolver_name, "patterns");
        return false;
    }
    if (step->op == ResolverStepOp::PatternScanInRange &&
        (step->start.empty() || step->end.empty())) {
        Logger::Instance().LogError("Resolver range scan missing start/end reference in " + resolver_name, "patterns");
        return false;
    }
    if (step->op == ResolverStepOp::ValidateSection && !step->has_section) {
        Logger::Instance().LogError("Resolver validate_section missing section in " + resolver_name, "patterns");
        return false;
    }

    return true;
}

bool ParseResolverAttempt(
    const std::string& name_space,
    const std::string& resolver_name,
    const json& value,
    ResolverAttemptObject* attempt)
{
    if (!(attempt && value.is_object())) {
        return false;
    }

    attempt->name = value.value("name", "");
    if (!value.contains("steps") || !value["steps"].is_array() || value["steps"].empty()) {
        Logger::Instance().LogError("Resolver attempt has no steps: " + resolver_name, "patterns");
        return false;
    }

    for (const auto& step_value : value["steps"]) {
        ResolverStepObject step;
        if (!ParseResolverStep(name_space, resolver_name, step_value, &step)) {
            return false;
        }
        attempt->steps.push_back(std::move(step));
    }

    return true;
}

bool LoadResolvers(const std::filesystem::path& path, const json& root) {
    if (!root.contains("resolvers") || !root["resolvers"].is_object()) {
        return true;
    }

    const std::string name_space = root.value("namespace", "");
    for (const auto& [raw_name, value] : root["resolvers"].items()) {
        const std::string name = QualifyName(name_space, raw_name);
        if (g_resolvers.contains(name)) {
            Logger::Instance().LogError("Duplicate resolver entry: " + name + " in " + path.string(), "patterns");
            return false;
        }
        if (!value.is_object()) {
            Logger::Instance().LogError("Invalid resolver object: " + name, "patterns");
            return false;
        }

        ResolverObject resolver;
        resolver.name = name;
        resolver.module = value.value("module", name_space.empty() ? ModuleFromQualifiedName(name) : name_space);

        const std::string severity_text = value.value("log_level", "error");
        const std::string action_text = value.value("on_fail", "halt");
        if (!ParseSeverity(severity_text, &resolver.severity) ||
            !ParseAction(action_text, &resolver.action)) {
            Logger::Instance().LogError("Invalid resolver failure policy: " + name, "patterns");
            return false;
        }

        if (value.contains("attempts")) {
            if (!value["attempts"].is_array() || value["attempts"].empty()) {
                Logger::Instance().LogError("Resolver has invalid attempts: " + name, "patterns");
                return false;
            }
            for (const auto& attempt_value : value["attempts"]) {
                ResolverAttemptObject attempt;
                if (!ParseResolverAttempt(name_space, name, attempt_value, &attempt)) {
                    return false;
                }
                resolver.attempts.push_back(std::move(attempt));
            }
        } else {
            ResolverAttemptObject attempt;
            attempt.name = "default";
            if (!value.contains("steps") || !value["steps"].is_array() || value["steps"].empty()) {
                Logger::Instance().LogError("Resolver has no steps: " + name, "patterns");
                return false;
            }
            for (const auto& step_value : value["steps"]) {
                ResolverStepObject step;
                if (!ParseResolverStep(name_space, name, step_value, &step)) {
                    return false;
                }
                attempt.steps.push_back(std::move(step));
            }
            resolver.attempts.push_back(std::move(attempt));
        }

        g_resolvers.emplace(name, std::move(resolver));
    }

    return true;
}

bool LoadFile(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input.is_open()) {
        Logger::Instance().LogError("Unable to open pattern file: " + path.string(), "patterns");
        return false;
    }

    json root;
    try {
        input >> root;
    }
    catch (const std::exception& ex) {
        Logger::Instance().LogError("Failed to parse " + path.string() + ": " + ex.what(), "patterns");
        return false;
    }

    const std::string name_space = root.value("namespace", "");
    if (root.contains("patterns") && root["patterns"].is_object()) {
        for (const auto& [raw_name, value] : root["patterns"].items()) {
            const std::string name = QualifyName(name_space, raw_name);
            if (g_patterns.contains(name)) {
                Logger::Instance().LogError("Duplicate pattern entry: " + name, "patterns");
                return false;
            }

            PY4GW::PatternObject pattern_object;
            pattern_object.name = name;
            pattern_object.mask = value.value("mask", "");
            pattern_object.assertion_file = value.value("assertion_file", "");
            pattern_object.assertion_message = value.value("assertion_message", "");
            pattern_object.section = ParseSection(value.value("section", "text"));

            const bool has_pattern_field = value.contains("pattern");
            const bool has_mask_field = value.contains("mask");
            const bool has_assertion_file_field = value.contains("assertion_file");
            const bool has_assertion_message_field = value.contains("assertion_message");
            const bool has_offset_field = value.contains("offset");
            const bool has_line_field = value.contains("line_number");
            const bool has_range_field = value.contains("range");
            const bool has_section_field = value.contains("section");

            const std::string pattern_literal = value.value("pattern", "");
            const std::string offset_text = value.value("offset", "0");
            const std::string line_text = value.value("line_number", "0");
            const std::string range_text = value.value("range", "0");
            if ((!pattern_literal.empty() && !DecodePatternLiteral(pattern_literal, &pattern_object.pattern)) ||
                !ParseInt(offset_text, &pattern_object.offset) ||
                !ParseInt(line_text, &pattern_object.line_number) ||
                !ParseInt(range_text, &pattern_object.range)) {
                Logger::Instance().LogError("Invalid pattern entry: " + name, "patterns");
                return false;
            }

            const bool has_byte_pattern = has_pattern_field || has_mask_field;
            const bool has_assertion = has_assertion_file_field || has_assertion_message_field;
            const bool has_scan_config = has_offset_field || has_line_field || has_range_field || has_section_field;
            if (!has_byte_pattern && !has_assertion && !has_scan_config) {
                Logger::Instance().LogError("Pattern entry has no usable scanner inputs: " + name, "patterns");
                return false;
            }

            g_patterns.emplace(name, std::move(pattern_object));
        }
    }

    return LoadResolvers(path, root);
}

}  // namespace

namespace PY4GW {

bool Patterns::Initialize(const std::filesystem::path& directory) {
    if (g_initialized) {
        return true;
    }

    const std::filesystem::path pattern_directory = directory.empty()
        ? process_manager::GetModuleDirectory() / "offsets"
        : directory;
    if (pattern_directory.empty() || !std::filesystem::exists(pattern_directory)) {
        Logger::Instance().LogError("Pattern directory not found: " + pattern_directory.string(), "patterns");
        return false;
    }

    std::vector<std::filesystem::path> files;
    for (const auto& entry : std::filesystem::directory_iterator(pattern_directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".json") {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());

    if (files.empty()) {
        Logger::Instance().LogError("No pattern JSON files found in: " + pattern_directory.string(), "patterns");
        return false;
    }

    g_patterns.clear();
    g_resolvers.clear();
    for (const auto& file : files) {
        if (!LoadFile(file)) {
            g_patterns.clear();
            g_resolvers.clear();
            return false;
        }
    }

    if (g_patterns.empty()) {
        Logger::Instance().LogError("Pattern initialization completed with zero loaded patterns.", "patterns");
        return false;
    }

    g_initialized = true;
    return true;
}

const PatternObject* Patterns::Get(const std::string& name) {
    if (!g_initialized) {
        return nullptr;
    }

    const auto it = g_patterns.find(name);
    if (it == g_patterns.end()) {
        return nullptr;
    }
    return &it->second;
}

PointerResolutionResult Patterns::ResolvePointer(const std::string& name) {
    PointerResolutionResult result;
    result.name = name;
    result.module = ModuleFromQualifiedName(name);

    if (!g_initialized) {
        result.failed_step = "initialize";
        result.message = "Patterns subsystem is not initialized";
        LogResolutionFailure(result);
        return result;
    }

    const auto resolver_it = g_resolvers.find(name);
    if (resolver_it == g_resolvers.end()) {
        result.failed_step = "resolver_lookup";
        result.message = "Resolver definition not found";
        LogResolutionFailure(result);
        return result;
    }

    const ResolverObject& resolver = resolver_it->second;
    result.module = resolver.module;
    result.severity = resolver.severity;
    result.action = resolver.action;

    const auto run_attempt = [&](const ResolverAttemptObject& attempt) -> PointerResolutionResult {
        PointerResolutionResult attempt_result;
        attempt_result.name = result.name;
        attempt_result.module = result.module;
        attempt_result.severity = result.severity;
        attempt_result.action = result.action;
        attempt_result.selected_attempt = attempt.name;
        attempt_result.failed_attempt = attempt.name;

        std::unordered_map<std::string, uintptr_t> values;
        for (const auto& step : attempt.steps) {
            PointerResolutionTraceStep trace_step;
            trace_step.name = step.name.empty() ? step.output : step.name;

            switch (step.op) {
            case ResolverStepOp::PatternScan:
                trace_step.op = "scan";
                break;
            case ResolverStepOp::PatternScanInRange:
                trace_step.op = "scan_in_range";
                break;
            case ResolverStepOp::ToFunctionStart:
                trace_step.op = "to_function_start";
                break;
            case ResolverStepOp::FunctionFromNearCall:
                trace_step.op = "function_from_near_call";
                break;
            case ResolverStepOp::FindUseOfString:
                trace_step.op = "find_use_of_string";
                break;
            case ResolverStepOp::Dereference:
                trace_step.op = "dereference";
                break;
            case ResolverStepOp::ReadU32:
                trace_step.op = "read_u32";
                break;
            case ResolverStepOp::Add:
                trace_step.op = "add";
                break;
            case ResolverStepOp::Divide:
                trace_step.op = "divide";
                break;
            case ResolverStepOp::ValidateSection:
                trace_step.op = "validate_section";
                break;
            }

            uintptr_t output = 0;
            bool ok = false;
            std::string detail;

            switch (step.op) {
            case ResolverStepOp::PatternScan: {
                const auto pattern_it = g_patterns.find(step.pattern_name);
                if (pattern_it == g_patterns.end()) {
                    detail = "pattern not found: " + step.pattern_name;
                    break;
                }
                const auto& pattern = pattern_it->second;
                if (!pattern.assertion_file.empty() || !pattern.assertion_message.empty()) {
                    output = Scanner::FindAssertion(
                        pattern.assertion_file.c_str(),
                        pattern.assertion_message.c_str(),
                        static_cast<uint32_t>(pattern.line_number),
                        pattern.offset);
                } else {
                    output = Scanner::Find(
                        pattern.pattern.c_str(),
                        pattern.mask.c_str(),
                        pattern.offset,
                        pattern.section);
                }
                ok = output != 0;
                if (!ok) {
                    detail = "scan returned null";
                }
                break;
            }
            case ResolverStepOp::PatternScanInRange: {
                const auto pattern_it = g_patterns.find(step.pattern_name);
                const auto start_it = values.find(step.start);
                const auto end_it = values.find(step.end);
                if (pattern_it == g_patterns.end()) {
                    detail = "pattern not found: " + step.pattern_name;
                    break;
                }
                if (start_it == values.end()) {
                    detail = "start reference not found: " + step.start;
                    break;
                }
                if (end_it == values.end()) {
                    detail = "end reference not found: " + step.end;
                    break;
                }
                const uintptr_t start = start_it->second + step.start_add;
                const uintptr_t end = end_it->second + step.end_add;
                trace_step.input = start;
                const auto& pattern = pattern_it->second;
                output = Scanner::FindInRange(
                    pattern.pattern.c_str(),
                    pattern.mask.c_str(),
                    pattern.offset,
                    start,
                    end);
                ok = output != 0;
                if (!ok) {
                    detail = "range scan returned null";
                }
                break;
            }
            case ResolverStepOp::ToFunctionStart: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                output = Scanner::ToFunctionStart(input_it->second, static_cast<uint32_t>(step.scan_range));
                ok = output != 0;
                if (!ok) {
                    detail = "resolved function start is null";
                }
                break;
            }
            case ResolverStepOp::FunctionFromNearCall: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                output = Scanner::FunctionFromNearCall(input_it->second, step.check_valid_ptr);
                ok = output != 0;
                if (!ok) {
                    detail = "near-call target is null";
                }
                break;
            }
            case ResolverStepOp::FindUseOfString: {
                std::string literal = step.literal;
                int offset = 0;
                PY4GW::ScannerSection section = PY4GW::ScannerSection::Text;
                if (!step.pattern_name.empty()) {
                    const auto pattern_it = g_patterns.find(step.pattern_name);
                    if (pattern_it == g_patterns.end()) {
                        detail = "pattern not found: " + step.pattern_name;
                        break;
                    }
                    literal = pattern_it->second.pattern;
                    offset = pattern_it->second.offset;
                    section = pattern_it->second.section;
                }
                if (literal.empty()) {
                    detail = "string literal is empty";
                    break;
                }
                if (step.wide_string) {
                    std::wstring wide_literal(literal.begin(), literal.end());
                    output = Scanner::FindNthUseOfString(wide_literal.c_str(), static_cast<size_t>(step.nth), offset, section);
                } else {
                    output = Scanner::FindNthUseOfString(literal.c_str(), static_cast<size_t>(step.nth), offset, section);
                }
                ok = output != 0;
                if (!ok) {
                    detail = "string use scan returned null";
                }
                break;
            }
            case ResolverStepOp::Dereference: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                if (!input_it->second) {
                    detail = "cannot dereference null input";
                    break;
                }
                if (!CanReadMemory(input_it->second, sizeof(uintptr_t))) {
                    detail = "cannot dereference unreadable input";
                    break;
                }
                output = *reinterpret_cast<const uintptr_t*>(input_it->second);
                ok = output != 0;
                if (!ok) {
                    detail = "dereferenced pointer is null";
                }
                break;
            }
            case ResolverStepOp::ReadU32: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                if (!input_it->second) {
                    detail = "cannot read from null input";
                    break;
                }
                if (!CanReadMemory(input_it->second, sizeof(uint32_t))) {
                    detail = "cannot read from unreadable input";
                    break;
                }
                output = *reinterpret_cast<const uint32_t*>(input_it->second);
                ok = true;
                break;
            }
            case ResolverStepOp::Add: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                output = input_it->second + step.value;
                ok = output != 0;
                if (!ok) {
                    detail = "arithmetic result is null";
                }
                break;
            }
            case ResolverStepOp::Divide: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                if (step.value == 0) {
                    detail = "cannot divide by zero";
                    break;
                }
                output = input_it->second / static_cast<uintptr_t>(step.value);
                ok = true;
                break;
            }
            case ResolverStepOp::ValidateSection: {
                const auto input_it = values.find(step.input);
                if (input_it == values.end()) {
                    detail = "input reference not found: " + step.input;
                    break;
                }
                trace_step.input = input_it->second;
                output = input_it->second;
                ok = Scanner::IsValidPtr(output, step.section);
                if (!ok) {
                    detail = "pointer is outside expected section";
                }
                break;
            }
            }

            trace_step.output = output;
            trace_step.ok = ok;
            trace_step.detail = detail;
            attempt_result.trace.push_back(trace_step);

            if (!ok) {
                attempt_result.failed_step = trace_step.name;
                attempt_result.message = detail;
                return attempt_result;
            }

            values[step.output] = output;
        }

        const auto final_it = values.find("final");
        if (final_it == values.end()) {
            attempt_result.failed_step = "final";
            attempt_result.message = "resolver did not populate final output";
            return attempt_result;
        }

        attempt_result.ok = true;
        attempt_result.value = final_it->second;
        return attempt_result;
    };

    PointerResolutionResult last_attempt_result = result;
    for (const auto& attempt : resolver.attempts) {
        PointerResolutionResult attempt_result = run_attempt(attempt);
        if (attempt_result.ok) {
            return attempt_result;
        }
        last_attempt_result = std::move(attempt_result);
    }

    if (resolver.attempts.size() > 1 && !last_attempt_result.message.empty()) {
        last_attempt_result.message = "all attempts failed; last_error=" + last_attempt_result.message;
    }
    LogResolutionFailure(last_attempt_result);
    return last_attempt_result;
}

}  // namespace PY4GW
