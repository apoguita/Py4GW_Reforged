"""Temporary widget. Start beside the Steward with the Xunlai storage open."""
import random
import time
import math

import PyImGui
from Py4GWCoreLib import GLOBAL_CACHE, Agent, ImGui, Map, Player, Routines
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT

MODULE_NAME = "Get Mobstoppers (Halloween)"
ITEM_MODEL = 32558
STEWARD = r"\x8102\x5C22\xA92E\x2451"
target = 402
ini_key = ""


class Collector:
    def __init__(self):
        self.running = False
        self.collected = 0
        self.goal = 0
        self.state = "idle"
        self.message = "Open your storage and stand beside Mad King's Steward."
        self.tree = None
        self.deadline = 0.0
        self.ready_at = 0.0
        self.bag_before = 0
        self.storage_before = 0

    def stop(self, message):
        self.running = False
        if self.tree is not None:
            self.tree.reset()
            self.tree = None
        self.message = message
        print(f"[{MODULE_NAME}] {self.state}: {message} ({self.collected}/{self.goal})")

    def enter(self, state, delay=False):
        self.state = state
        self.ready_at = time.monotonic() + (random.uniform(0.2, 0.6) if delay else 0)
        self.deadline = self.ready_at + 15.0
        self.message = state.replace("_", " ").capitalize()

    def start(self, requested):
        if requested <= 0 or requested % 3:
            self.message = "Enter a positive multiple of 3 (each reward gives 3)."
            return
        if not Routines.Checks.Map.MapValid() or Map.GetMapID() != 808:
            self.message = "Start in Lion's Arch (Halloween)."
            return
        if not GLOBAL_CACHE.Inventory.IsStorageOpen():
            self.message = "Open your Xunlai storage first."
            return
        self.goal = requested
        self.collected = 0
        self.running = True
        self.enter("store" if GLOBAL_CACHE.Inventory.GetModelCount(ITEM_MODEL) else "interact", delay=True)

    def tick(self):
        if not self.running:
            return
        inv = GLOBAL_CACHE.Inventory
        if not Routines.Checks.Map.MapValid() or Map.GetMapID() != 808:
            self.stop("Stopped: map changed or became unavailable.")
            return
        if not inv.IsStorageOpen():
            self.stop("Stopped: storage closed.")
            return
        now = time.monotonic()
        if now > self.deadline:
            self.stop(f"Stopped: timeout waiting for {self.state}; inspect bags/dialogue before restarting.")
            return
        if now < self.ready_at:
            return
        count = inv.GetModelCount(ITEM_MODEL)
        if self.state == "store":
            if count == 0:
                if self.collected >= self.goal:
                    self.stop("Complete: all collected Mobstoppers are in storage.")
                else:
                    self.enter("interact", delay=True)
                return
            self.bag_before = count
            self.storage_before = inv.GetModelCountInStorage(ITEM_MODEL)
            # The existing inventory owner fills partial stacks, then empty slots.
            if not inv.DepositItemToStorageByModelID(ITEM_MODEL):
                self.stop("Stopped: no storage destination available.")
                return
            self.enter("confirm_storage")
        elif self.state == "confirm_storage":
            moved = self.bag_before - count
            stored = inv.GetModelCountInStorage(ITEM_MODEL) - self.storage_before
            if moved > 0 and stored == moved:
                if count:
                    self.enter("store", delay=True)
                elif self.collected >= self.goal:
                    self.stop("Complete: all collected Mobstoppers are in storage.")
                else:
                    self.enter("interact", delay=True)
        elif self.state == "interact":
            if count:
                self.stop("Stopped: Mobstoppers appeared in bags unexpectedly.")
                return
            self.bag_before = count
            # The movement transaction closes all panels before reinteraction.
            # This stationary collector must preserve the already-open storage.
            agent_id = Agent.GetAgentIDByEncString(STEWARD)
            if not agent_id or not Agent.IsNPC(agent_id):
                self.stop("Stopped: Mad King's Steward could not be resolved.")
                return
            npc_xy = Agent.GetXY(agent_id)
            if math.dist(npc_xy, (5332.0, 9048.0)) > 160.0:
                self.stop("Stopped: Steward is outside the expected location.")
                return
            if math.dist(Player.GetXY(), npc_xy) > 250.0:
                self.stop("Stopped: stand closer to Mad King's Steward.")
                return
            Player.Interact(agent_id, False)
            self.tree = BT.Player.SendAutomaticDialog(
                button_number=1, aftercast_ms=0, log=False,
            )
            self.enter("choose_every_bit_helps")
        elif self.state == "choose_every_bit_helps":
            result = self.tree.tick()
            if result == BehaviorTree.NodeState.FAILURE:
                self.stop("Stopped: interaction/dialogue failed; no automatic retry.")
            elif result == BehaviorTree.NodeState.SUCCESS:
                self.tree.reset()
                self.tree = None
                self.enter("confirm_reward")
        elif self.state == "confirm_reward":
            gained = count - self.bag_before
            if gained == 3:
                self.collected += gained
                self.enter("store", delay=True)
            elif gained != 0:
                self.stop(f"Stopped: expected 3 Mobstoppers, observed {gained}.")


collector = Collector()


def update():
    try:
        collector.tick()
    except Exception as exc:
        collector.stop(f"Stopped: {type(exc).__name__}: {exc}")


def draw():
    global target, ini_key
    if not Routines.Checks.Map.MapValid():
        return
    if not ini_key:
        ini_key = Settings("Widgets/GetMobstoppersHalloween.ini", "account").name
    if not ini_key:
        return
    try:
        if ImGui.Begin(ini_key, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
            if not collector.running:
                target = PyImGui.input_int("Mobstoppers to collect", target)
                if PyImGui.button("Start"):
                    collector.start(target)
            elif PyImGui.button("Stop"):
                collector.stop("Stopped by you. Already queued actions may finish.")
            PyImGui.text(f"Collected this run: {collector.collected} / {collector.goal}")
            PyImGui.text_wrapped(collector.message)
            PyImGui.text("Keep the storage open. Use a multiple of 3.")
    finally:
        ImGui.End(ini_key)


def main():
    pass


def on_disable():
    collector.stop("Widget disabled.")


def draw_contents():
    global target, ini_key
    if not collector.running:
        target = PyImGui.input_int('Mobstoppers to collect', target)
        if PyImGui.button('Start'):
            collector.start(target)
    elif PyImGui.button('Stop'):
        collector.stop('Stopped by you. Already queued actions may finish.')
    PyImGui.text(f'Collected this run: {collector.collected} / {collector.goal}')
    PyImGui.text_wrapped(collector.message)
    PyImGui.text('Keep the storage open. Use a multiple of 3.')
