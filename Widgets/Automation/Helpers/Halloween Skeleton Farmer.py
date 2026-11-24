"""One window for collecting, capturing, and turning in Halloween skeletons."""
import importlib
import PyImGui
from Py4GWCoreLib import ImGui, Routines
from Sources.HalloweenSkeletonFarmer import capture, mobstoppers, turn_ins

# Refresh All Widgets must refresh imported task modules before using their
# interfaces. Installation/replacement requires the host and old widgets stopped.
capture = importlib.reload(capture)
mobstoppers = importlib.reload(mobstoppers)
turn_ins = importlib.reload(turn_ins)

MODULE_NAME = "Halloween Skeleton Farmer"
BUILD_ID = "halloween-skeleton-farmer-20261102-v1"
TASKS = ("Get Mobstoppers", "Capture Skeletons", "Every Bit Helps - Turn Ins")


class Farmer:
    def __init__(self):
        self.selected = 1
        self.notice = ""

    def running(self):
        return (mobstoppers.collector.running, capture.assistant.enabled, turn_ins.runner.running)

    def select(self, index):
        if index not in range(len(TASKS)):
            self.notice = "Choose a task from the list."
            return False
        if any(self.running()):
            self.notice = "Stop the current task before choosing another."
            return False
        self.selected = index
        self.notice = ""
        return True

    def stop(self):
        # Continue cancelling the others even if one native cleanup raises.
        errors = []
        for engine in (mobstoppers, capture, turn_ins):
            try:
                engine.on_disable()
            except Exception as error:
                errors.append(f"{engine.MODULE_NAME}: {error}")
        self.notice = "Stopped. Already queued actions may finish."
        if errors:
            self.notice += " Cleanup needs attention: " + "; ".join(errors)

    def update(self):
        active = self.running()
        if sum(bool(value) for value in active)>1 or any(
                value and index!=self.selected for index,value in enumerate(active)):
            self.stop()
            self.notice = "Conflicting tasks were stopped. Choose one task and start it again."
            return
        (mobstoppers, capture, turn_ins)[self.selected].update()


farmer = Farmer()


def update():
    Farmer.update(farmer)


def draw():
    try:
        if ImGui.Begin(MODULE_NAME, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
            if any(farmer.running()):
                PyImGui.text("Active task: " + TASKS[farmer.selected])
            else:
                farmer.select(PyImGui.combo("Task", farmer.selected, list(TASKS)))
            if farmer.notice:
                PyImGui.text_wrapped(farmer.notice)
            PyImGui.separator()
            # Capture already renders a loading-safe, observable status panel.
            # The outpost tasks retain their original native-read readiness gate.
            if farmer.selected==1 or Routines.Checks.Map.MapValid():
                (mobstoppers, capture, turn_ins)[farmer.selected].draw_contents()
            else:
                PyImGui.text_wrapped("Waiting for the map and character to load.")
            if PyImGui.collapsing_header("About this widget"):
                PyImGui.text_wrapped("Choose one job at a time. Collect Mobstoppers, capture Skeletons of Dhuum, or turn in Captured Skeletons for Every Bit Helps.")
                PyImGui.text_wrapped("Tasks do not automatically start one another. Stop before changing jobs.")
                PyImGui.text(BUILD_ID)
    finally:
        ImGui.End(MODULE_NAME)


def main():
    pass


def on_disable():
    farmer.stop()
