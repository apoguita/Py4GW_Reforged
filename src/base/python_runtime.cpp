#include "base/error_handling.h"

#include "base/python_runtime.h"

#include "base/logger.h"
#include "base/process_manager.h"
#include "base/timer.h"

#include <imgui.h>
#include <pybind11/embed.h>
#include <pybind11/eval.h>
#include <pybind11/pybind11.h>

#include <fstream>
#include <functional>
#include <memory>
#include <sstream>
namespace py = pybind11;

namespace PY4GW::python_runtime {

namespace {

py::scoped_interpreter* g_python_runtime = nullptr;
PyThreadState* g_python_thread_state = nullptr;
ScriptState g_script_state = ScriptState::Stopped;
std::string g_selected_script_path;
std::string g_loaded_script_content;
py::object g_script_module;
py::object g_main_function;
py::object g_update_function;
py::object g_draw_function;
py::object g_console_scope;
PY4GW::Timer g_script_timer;

struct DeferredMixedCommand {
    std::function<void()> action;
    int delay_ms = 0;
    PY4GW::Timer timer;
    bool active = false;
};

DeferredMixedCommand g_mixed_deferred;

bool CallPythonFunctionSafe(py::object& fn, const char* label) {
    if (!fn || fn.is_none()) {
        return false;
    }

    try {
        fn();
        return true;
    } catch (const py::error_already_set& error) {
        g_script_state = ScriptState::Stopped;
        Logger::Instance().LogError(std::string("Python error (") + label + "): " + error.what());
    } catch (const std::exception& error) {
        g_script_state = ScriptState::Stopped;
        Logger::Instance().LogError(std::string("Runtime error (") + label + "): " + error.what());
    }
    return false;
}

py::object GetCallableIfExists(py::object& module, const char* name) {
    if (!module || module.is_none() || !py::hasattr(module, name)) {
        return py::object();
    }

    py::object obj = module.attr(name);
    if (!obj || obj.is_none() || !PyCallable_Check(obj.ptr())) {
        return py::object();
    }
    return obj;
}

std::string LoadPythonScript(const std::string& file_path) {
    std::ifstream script_file(file_path);
    if (!script_file.is_open()) {
        Logger::Instance().LogError("Failed to open script file: " + file_path);
        return {};
    }

    std::stringstream buffer;
    buffer << script_file.rdbuf();
    if (buffer.str().empty()) {
        Logger::Instance().LogError("Script file is empty: " + file_path);
    }
    return buffer.str();
}

void ResetScriptEnvironment() {
    g_loaded_script_content.clear();
    g_script_module = py::object();
    g_main_function = py::object();
    g_update_function = py::object();
    g_draw_function = py::object();
    g_script_state = ScriptState::Stopped;
    Logger::Instance().LogNotice("Python environment reset.");
}

void ClearScriptEnvironment() {
    g_loaded_script_content.clear();
    g_script_module = py::object();
    g_main_function = py::object();
    g_update_function = py::object();
    g_draw_function = py::object();
    g_script_state = ScriptState::Stopped;
}

void ScheduleDeferredAction(std::function<void()> fn, int delay_ms) {
    g_mixed_deferred.action = std::move(fn);
    g_mixed_deferred.delay_ms = delay_ms;
    g_mixed_deferred.timer.reset();
    g_mixed_deferred.timer.start();
    g_mixed_deferred.active = true;
}

PYBIND11_EMBEDDED_MODULE(Py4GW, m) {
    m.doc() = "Embedded Py4GW runtime module.";
    m.def("version", []() { return "0.1.0"; });
    m.def("log", [](const std::string& message) { Logger::Instance().LogInfo(message); });
    m.def("get_projects_path", []() -> std::string {
        return process_manager::GetModuleDirectory().string();
    });

    py::module_ console = m.def_submodule("Console", "Console and logger bindings");
    console.def("log", [](const std::string& module_name, const std::string& message, const std::string& level, bool export_to_disk) {
        Logger::Instance().Log(module_name, level, message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("level") = "INFO", py::arg("export") = false);
    console.def("info", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "INFO", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("warning", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "WARNING", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("error", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "ERROR", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("notice", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "NOTICE", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("success", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "SUCCESS", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("debug", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "DEBUG", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("performance", [](const std::string& module_name, const std::string& message, bool export_to_disk) {
        Logger::Instance().Log(module_name, "PERFORMANCE", message, export_to_disk);
    }, py::arg("module_name"), py::arg("message"), py::arg("export") = false);
    console.def("print", [](const std::string& message, bool export_to_disk) {
        Logger::Instance().Log("Python", "INFO", message, export_to_disk);
    }, py::arg("message"), py::arg("export") = false);
    console.def("load", [](const std::string& path) {
        SetSelectedScriptPath(path);
        return LoadSelectedScript();
    }, py::arg("path"));
    console.def("run", []() {
        return RunScript();
    });
    console.def("stop", []() {
        StopScript();
    });
    console.def("pause", []() {
        return PauseScript();
    });
    console.def("resume", []() {
        return ResumeScript();
    });
    console.def("status", []() {
        return GetScriptStatus();
    });
    console.def("defer_load_and_run", [](const std::string& path, int delay_ms) {
        DeferLoadAndRun(path, delay_ms);
    }, py::arg("path"), py::arg("delay_ms") = 1000);
    console.def("defer_stop_load_and_run", [](const std::string& path, int delay_ms) {
        DeferStopLoadAndRun(path, delay_ms);
    }, py::arg("path"), py::arg("delay_ms") = 1000);
    console.def("defer_stop_and_run", [](int delay_ms) {
        DeferStopAndRun(delay_ms);
    }, py::arg("delay_ms") = 1000);

    py::module_ imgui = m.def_submodule("ImGui", "Minimal ImGui bindings for script smoke tests");
    imgui.def("begin", [](const std::string& name) {
        return ImGui::Begin(name.c_str());
    });
    imgui.def("end", []() {
        ImGui::End();
    });
    imgui.def("text", [](const std::string& value) {
        ImGui::TextUnformatted(value.c_str());
    });
    imgui.def("button", [](const std::string& label) {
        return ImGui::Button(label.c_str());
    });
}

}

bool Initialize() {
    try {
        g_python_runtime = new py::scoped_interpreter();
        py::module_ sys = py::module_::import("sys");
        const auto root = process_manager::GetModuleDirectory();
        if (!root.empty()) {
            sys.attr("path").attr("insert")(0, root.string());
            sys.attr("path").attr("insert")(0, (root / "scripts").string());
        }
        py::module_::import("Py4GW");
        g_console_scope = py::module_::import("__main__");
        g_script_state = ScriptState::Stopped;
        g_python_thread_state = PyEval_SaveThread();
        return true;
    } catch (const std::exception& error) {
        Logger::Instance().LogError(std::string("Python initialization failed: ") + error.what());
        delete g_python_runtime;
        g_python_runtime = nullptr;
        return false;
    }
}

void Shutdown() {
    if (!g_python_runtime) {
        return;
    }
    if (g_python_thread_state != nullptr) {
        PyEval_RestoreThread(g_python_thread_state);
        g_python_thread_state = nullptr;
    }
    ClearScriptEnvironment();
    g_console_scope = py::object();
    delete g_python_runtime;
    g_python_runtime = nullptr;
}

void ExecutePythonUpdate() {
    if (g_script_state != ScriptState::Running || g_loaded_script_content.empty()) {
        return;
    }
    py::gil_scoped_acquire gil;
    CallPythonFunctionSafe(g_update_function, "update()");
}

void ExecutePythonDraw() {
    if (g_script_state != ScriptState::Running || g_loaded_script_content.empty()) {
        return;
    }
    py::gil_scoped_acquire gil;
    if (CallPythonFunctionSafe(g_draw_function, "draw()")) {
        return;
    }
    CallPythonFunctionSafe(g_main_function, "main()");
}

void ProcessDeferredActions() {
    if (g_mixed_deferred.active && g_mixed_deferred.timer.hasElapsed(g_mixed_deferred.delay_ms)) {
        if (g_mixed_deferred.action) {
            g_mixed_deferred.action();
        }
        g_mixed_deferred.active = false;
    }
}

bool SetSelectedScriptPath(const std::string& path) {
    g_selected_script_path = path;
    return !g_selected_script_path.empty();
}

const std::string& GetSelectedScriptPath() {
    return g_selected_script_path;
}

bool LoadSelectedScript() {
    if (g_selected_script_path.empty()) {
        Logger::Instance().LogError("Script path is empty.");
        return false;
    }

    py::gil_scoped_acquire gil;
    ClearScriptEnvironment();
    g_loaded_script_content = LoadPythonScript(g_selected_script_path);
    if (g_loaded_script_content.empty()) {
        Logger::Instance().LogError("Failed to load script.");
        return false;
    }

    try {
        py::module_ py_compile = py::module_::import("py_compile");
        try {
            py_compile.attr("compile")(g_selected_script_path, py::none(), py::none(), py::bool_(true));
            Logger::Instance().LogNotice("Script compiled successfully.");
        } catch (const py::error_already_set& error) {
            Logger::Instance().LogError(std::string("Python syntax error: ") + error.what());
            g_script_state = ScriptState::Stopped;
            return false;
        }

        py::object types_module = py::module_::import("types");
        g_script_module = types_module.attr("ModuleType")("py4gw_script_module");
        g_script_module.attr("__file__") = py::str(g_selected_script_path);
        try {
            py::exec(g_loaded_script_content, g_script_module.attr("__dict__"));
        } catch (const py::error_already_set& error) {
            Logger::Instance().LogError(std::string("Python error: ") + error.what());
            g_script_state = ScriptState::Stopped;
            return false;
        }

        g_main_function = GetCallableIfExists(g_script_module, "main");
        g_update_function = GetCallableIfExists(g_script_module, "update");
        g_draw_function = GetCallableIfExists(g_script_module, "draw");

        if (g_draw_function && !g_draw_function.is_none()) {
            Logger::Instance().LogNotice("draw() function found.");
        }
        if (g_update_function && !g_update_function.is_none()) {
            Logger::Instance().LogNotice("update() function found.");
        }
        if (g_main_function && !g_main_function.is_none()) {
            Logger::Instance().LogNotice("main() function found.");
        }

        if ((g_main_function && !g_main_function.is_none()) ||
            (g_update_function && !g_update_function.is_none()) ||
            (g_draw_function && !g_draw_function.is_none())) {
            return true;
        }

        g_script_state = ScriptState::Stopped;
        Logger::Instance().LogError("No main()/update()/draw() function found in the script.");
    } catch (const py::error_already_set& error) {
        Logger::Instance().LogError(std::string("Python error: ") + error.what());
        g_script_state = ScriptState::Stopped;
    } catch (const std::exception& error) {
        Logger::Instance().LogError(std::string("Standard exception: ") + error.what());
        g_script_state = ScriptState::Stopped;
    } catch (...) {
        Logger::Instance().LogError("Unknown error occurred during script execution.");
        g_script_state = ScriptState::Stopped;
    }

    return false;
}

bool StartSelectedScript() {
    if (g_script_state == ScriptState::Paused) {
        g_script_state = ScriptState::Running;
        g_script_timer.Resume();
        Logger::Instance().LogNotice("Script resumed.");
        return true;
    }
    if (!LoadSelectedScript()) {
        ResetScriptEnvironment();
        g_script_state = ScriptState::Stopped;
        g_script_timer.stop();
        Logger::Instance().LogNotice("Script stopped.");
        return false;
    }
    g_script_state = ScriptState::Running;
    g_script_timer.reset();
    Logger::Instance().LogNotice("Script started.");
    return true;
}

bool RunScript() {
    if (g_script_state == ScriptState::Stopped) {
        if (LoadSelectedScript()) {
            g_script_state = ScriptState::Running;
            g_script_timer.reset();
            Logger::Instance().LogNotice("Script started from binding.");
            return true;
        }
    }
    return false;
}

void StopScript() {
    py::gil_scoped_acquire gil;
    ResetScriptEnvironment();
    g_script_state = ScriptState::Stopped;
    g_script_timer.stop();
    Logger::Instance().LogNotice("Script stopped.");
}

bool PauseScript() {
    if (g_script_state != ScriptState::Running) {
        return false;
    }
    g_script_state = ScriptState::Paused;
    g_script_timer.Pause();
    Logger::Instance().LogNotice("Script paused.");
    return true;
}

bool ResumeScript() {
    if (g_script_state != ScriptState::Paused) {
        return false;
    }
    g_script_state = ScriptState::Running;
    g_script_timer.Resume();
    Logger::Instance().LogNotice("Script resumed.");
    return true;
}

std::string GetScriptStatus() {
    switch (g_script_state) {
    case ScriptState::Running:
        return "Running";
    case ScriptState::Paused:
        return "Paused";
    case ScriptState::Stopped:
        return "Stopped";
    }
    return "Unknown";
}

double GetScriptElapsedMilliseconds() {
    return g_script_timer.getElapsedTime();
}

void DeferLoadAndRun(const std::string& path, int delay_ms) {
    ScheduleDeferredAction([path]() {
        SetSelectedScriptPath(path);
        if (LoadSelectedScript()) {
            g_script_state = ScriptState::Running;
            g_script_timer.reset();
            Logger::Instance().LogNotice("Deferred: script loaded and started.");
        }
    }, delay_ms);
}

void DeferStopLoadAndRun(const std::string& path, int delay_ms) {
    ScheduleDeferredAction([path]() {
        StopScript();
        SetSelectedScriptPath(path);
        if (LoadSelectedScript()) {
            g_script_state = ScriptState::Running;
            g_script_timer.reset();
            Logger::Instance().LogNotice("Deferred: stopped, loaded and started.");
        }
    }, delay_ms);
}

void DeferStopAndRun(int delay_ms) {
    ScheduleDeferredAction([]() {
        StopScript();
        RunScript();
        Logger::Instance().LogNotice("Deferred: stopped and restarted.");
    }, delay_ms);
}

bool ExecuteCommand(const std::string& command) {
    py::gil_scoped_acquire gil;
    try {
        py::object scope = g_script_module;
        if (!scope || scope.is_none()) {
            if (!g_console_scope || g_console_scope.is_none()) {
                g_console_scope = py::module_::import("__main__");
            }
            scope = g_console_scope;
        }

        py::object result = py::eval(command, scope.attr("__dict__"));
        Logger::Instance().Log("Python", "INFO", ">>> " + command, false);
        if (!result.is_none()) {
            Logger::Instance().Log("Python", "INFO", py::str(result).cast<std::string>(), false);
        }
        return true;
    } catch (const py::error_already_set& error) {
        Logger::Instance().LogError(std::string("Error executing command: ") + command + "\n" + error.what(), "Python");
    } catch (const std::exception& error) {
        Logger::Instance().LogError(std::string("Standard error executing command: ") + command + "\n" + error.what(), "Python");
    } catch (...) {
        Logger::Instance().LogError("Unknown error executing command: " + command, "Python");
    }
    return false;
}

ScriptState GetScriptState() {
    return g_script_state;
}

const char* GetScriptStateLabel() {
    switch (g_script_state) {
    case ScriptState::Running: return "Running";
    case ScriptState::Paused: return "Paused";
    case ScriptState::Stopped: return "Stopped";
    }
    return "Unknown";
}

bool HasLoadedScript() {
    return !g_loaded_script_content.empty();
}

}  // namespace PY4GW::python_runtime
