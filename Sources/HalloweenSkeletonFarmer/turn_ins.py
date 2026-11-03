"""Repeat Every Bit Helps; assumes The Waiting Game has not been completed."""
import random
import time

import PyImGui
from Py4GWCoreLib import GLOBAL_CACHE, Dialog, ImGui, Map, Player, Quest, Routines
from Py4GWCoreLib.enums_src.Region_enums import District, ServerLanguage, ServerRegion
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT
from Py4GWCoreLib.routines_src.behaviourtrees_src.movement import BTMovement

MODULE_NAME = 'Every Bit Helps (Halloween)'
BUILD_ID = 'every-bit-helps-v14-target-retries'
QUEST_ID = 1123
DEPOSIT_THRESHOLD = 90_000
DEFAULT_CYCLES = 134
CAPTURED_SKELETON = 32559
MOBSTOPPER = 32558
LIONS_ARCH = 808
STEWARD = r'\x8102\x5C22\xA92E\x2451'
APPROACH_XY = (5222.76, 9118.42)
EUROPEAN_DISTRICTS = (
    (District.EuropeItalian.value, ServerLanguage.Italian.value),
    (District.EuropeSpanish.value, ServerLanguage.Spanish.value),
    (District.EuropePolish.value, ServerLanguage.Polish.value),
    (District.EuropeRussian.value, ServerLanguage.Russian.value),
)
DESCRIPTION = (
    "Travels to Halloween Lion's Arch if needed. An already-taken quest counts as the first turn-in. "
    'Assumes you have NOT completed The Waiting Game. '
    'Each cycle takes Every Bit Helps and turns in 3 Captured Skeletons. '
    'This will randomly switch between random European districts. '
    'Switching district makes the quest appear again before the next cycle. '
    '134 cycles require 402 Captured Skeletons in your bags. '
    'Automatically deposits carried gold at 90 platinum, including gold you started with. '
    'Run this widget by itself; keep room for Mobstoppers and reward bags.'
)


def bag_count(model):
    return int(GLOBAL_CACHE.Inventory.GetModelCount(model))


def skeleton_stacks():
    stacks = []
    for bag in (1, 2, 3, 4):
        for item in GLOBAL_CACHE.ItemArray.GetRawItemArray([bag]):
            if int(item.model_id) == CAPTURED_SKELETON:
                quantity = int(item.quantity)
                if quantity > 0:
                    stacks.append((bag, int(item.slot), int(item.item_id), quantity))
    return sorted(stacks)


def district_identity():
    return (int(Map.GetRegion()[0]), int(Map.GetLanguage()[0]), int(Map.GetDistrict()))


def interact_with_steward():
    # Only this pre-dialogue boundary may retry. Dialogue choices are outside it.
    attempts = []
    branches = []
    for index in range(3):
        attempt = BT.Composite.Sequence(
            BT.Agents.TargetAgentByModelID(modelID_or_encStr=STEWARD, log=False),
            BT.Player.InteractTarget(log=False), name='Target and interact with Steward')
        if index == 0:
            branches.append(attempt)
        else:
            previous = attempts[-1]
            def can_retry(previous=previous, index=index):
                eligible = int(previous.blackboard.get('result', 0)) > 0 and Player.GetTargetID() == 0
                if eligible:
                    print(f'[{MODULE_NAME}] No target selected; retry {index}/2 before dialogue.')
                return eligible
            branches.append(BT.Composite.Sequence(
                BehaviorTree(BehaviorTree.ConditionNode(name='Retry only absent selection', condition_fn=can_retry)),
                attempt, name='Retry Steward interaction'))
        attempts.append(attempt)
    return BehaviorTree(BehaviorTree.SelectorNode(children=branches, name='Steward interaction, maximum two retries'))


def dialog_page_signature():
    active = Dialog.get_active_dialog()
    if active is None:
        return None
    ids = tuple(int(button.dialog_id) for button in Dialog.get_active_dialog_buttons()
                if int(button.dialog_id or 0))
    return (int(active.context_dialog_id), ids) if ids else None


class CycleRunner:
    def __init__(self):
        self.running = False
        self.goal = 0
        self.completed = 0
        self.state = 'idle'
        self.message = "Start in Lion's Arch (Halloween)."
        self.tree = None
        self.deadline = 0.
        self.skeleton_before = 0
        self.mob_before = 0
        self.origin = None
        self.destination = None
        self.account = ''

    def enter(self, state, timeout=20.):
        self.state = state
        self.deadline = time.monotonic() + timeout
        self.message = state.replace('_', ' ').capitalize()
        print(f'[{MODULE_NAME}] state={state}; cycles={self.completed}/{self.goal}')

    def stop(self, message):
        self.running = False
        if self.tree is not None:
            self.tree.reset()
            self.tree = None
        self.message = message
        print(f'[{MODULE_NAME}] {self.state}: {message} ({self.completed}/{self.goal})')

    def start(self, cycles):
        if self.running:
            return
        if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles <= 0:
            self.message = 'Enter a positive whole number of cycles.'
            return
        if not Routines.Checks.Map.MapValid():
            self.message = 'Wait until the map is ready before starting.'
            return
        required = cycles * 3
        available = bag_count(CAPTURED_SKELETON)
        if available < required:
            self.message = f'Need {required} Captured Skeletons in bags; you have {available}. Nothing started.'
            return
        self.account = Player.GetAccountEmail()
        self.goal, self.completed = cycles, 0
        self.running = True
        try:
            if Map.GetMapID() != LIONS_ARCH or not Map.IsOutpost():
                Map.Travel(LIONS_ARCH)
                self.enter('travel_to_lions_arch', 60.)
            else:
                self.begin_cycle()
        except Exception as error:
            self.stop(f'Stopped before starting: {type(error).__name__}: {error}')

    def begin_cycle(self):
        if self.deposit_if_needed('begin_cycle'):
            return
        remaining = (self.goal - self.completed) * 3
        if bag_count(CAPTURED_SKELETON) < remaining:
            self.stop(f'Stopped: need {remaining} Captured Skeletons for the remaining cycles.')
            return
        stacks = skeleton_stacks()
        if not stacks:
            self.stop('Stopped: Captured Skeleton stacks could not be read.')
            return
        first = stacks[0]
        if first[3] < 3:
            if len(stacks) < 2:
                self.stop('Stopped: first Captured Skeleton stack needs at least 3.')
                return
            donor = stacks[1]
            amount = min(3 - first[3], donor[3])
            self.stack_total = bag_count(CAPTURED_SKELETON)
            self.stack_expected = (first[0], first[1], first[3] + amount)
            GLOBAL_CACHE.Inventory.MoveItem(donor[2], first[0], first[1], amount)
            self.enter('confirm_skeleton_stack')
            return
        if GLOBAL_CACHE.Inventory.GetFreeSlotCount() < 2:
            self.stop('Stopped: leave at least two free bag slots for Mobstoppers and rewards.')
            return
        self.tree = BTMovement.Move(
            x=APPROACH_XY[0], y=APPROACH_XY[1], tolerance=25.,
            timeout_ms=60000, pause_on_combat=False,
            path_points_override=[APPROACH_XY], avoid_obstacles=False, log=False)
        self.enter('approach_steward', 65.)

    def deposit_if_needed(self, next_action):
        self.gold_before = int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter())
        if self.gold_before < DEPOSIT_THRESHOLD:
            return False
        self.storage_before = int(GLOBAL_CACHE.Inventory.GetGoldInStorage())
        self.gold_amount = min(self.gold_before, max(0, 1_000_000 - self.storage_before))
        if self.gold_amount == 0:
            self.stop('Stopped: gold storage is full; carried gold is at least 90 platinum.')
            return True
        self.gold_next = next_action
        self.tree = BT.Items.DepositGoldKeep(gold_amount_to_leave_on_character=0, aftercast_ms=350)
        self.enter('deposit_gold')
        return True

    def after_reward(self):
        if self.completed >= self.goal:
            self.stop(f'Complete: {self.completed} cycles; {self.completed * 3} Captured Skeletons turned in.')
        else:
            self.switch_district()

    def accept_quest(self):
        self.skeleton_before = bag_count(CAPTURED_SKELETON)
        self.mob_before = bag_count(MOBSTOPPER)
        origin = {'signature': None}

        def capture_menu():
            signature = dialog_page_signature()
            # Both captured menu choices must have arrived before selecting.
            if signature is None or len(signature[1]) < 2:
                return BehaviorTree.NodeState.RUNNING
            origin['signature'] = signature
            print(f'[{MODULE_NAME}] menu_ready numeric_page={signature}; next_option=0')
            return BehaviorTree.NodeState.SUCCESS

        def offer_arrived():
            signature = dialog_page_signature()
            # The native context ID can populate while the menu's choices
            # remain unchanged. Only replacement choices prove the next page.
            # Appending the second menu choice is not a page transition.
            # The next first choice must replace the menu's first choice.
            if signature is None or signature[1][0] == origin['signature'][1][0]:
                return BehaviorTree.NodeState.RUNNING
            print(f'[{MODULE_NAME}] offer_ready numeric_page={signature}; previous={origin["signature"]}; next_option=0')
            return BehaviorTree.NodeState.SUCCESS

        self.tree = BT.Composite.Sequence(
            interact_with_steward(),
            BehaviorTree(BehaviorTree.WaitUntilNode(name='Wait for quest menu',
                condition_fn=capture_menu, throttle_interval_ms=100, timeout_ms=10000)),
            BT.Player.SendAutomaticDialog(button_number=0, log=True),
            BehaviorTree(BehaviorTree.WaitUntilNode(name='Wait for the quest offer to replace the menu',
                condition_fn=offer_arrived, throttle_interval_ms=100, timeout_ms=10000)),
            BT.Player.SendAutomaticDialog(button_number=0, log=True),
            name='Accept Every Bit Helps',
        )
        self.enter('accept_quest', 65.)

    def accept_reward(self):
        self.tree = BT.Composite.Sequence(
            interact_with_steward(),
            BT.Player.SendAutomaticDialog(button_number=0, log=False),
            name='Accept Every Bit Helps reward',
        )
        self.enter('accept_reward', 65.)

    def resume_or_accept(self):
        if QUEST_ID in Quest.GetQuestLogIds():
            self.skeleton_before = bag_count(CAPTURED_SKELETON)
            # Existing reward verification expects the accepted tonic balance.
            self.mob_before = bag_count(MOBSTOPPER) - 3
            self.accept_reward()
        else:
            self.accept_quest()

    def switch_district(self):
        self.origin = district_identity()
        choices = [(district, language) for district, language in EUROPEAN_DISTRICTS
                   if (self.origin[0], self.origin[1]) != (ServerRegion.Europe.value, language)]
        district, language = random.choice(choices)
        self.destination = (ServerRegion.Europe.value, language)
        # Same primitive and European pool as Simple Vanquish. Exclude the
        # current language so an unchanged map ID cannot masquerade as travel.
        Map.TravelToDistrict(LIONS_ARCH, district)
        self.enter('wait_for_new_district', 60.)

    def tick(self):
        if not self.running:
            return
        current_account = Player.GetAccountEmail()
        if current_account and current_account != self.account:
            self.stop('Stopped: account changed.')
            return
        if time.monotonic() > self.deadline:
            self.stop(f'Stopped: timed out during {self.state}. No automatic retry; inspect the quest and bags.')
            return
        valid = Routines.Checks.Map.MapValid()
        if self.state == 'travel_to_lions_arch':
            if valid and Map.GetMapID() == LIONS_ARCH and Map.IsOutpost():
                self.begin_cycle()
            return
        if self.state == 'wait_for_new_district':
            if not valid:
                return
            if Map.GetMapID() != LIONS_ARCH or not Map.IsOutpost():
                self.stop('Stopped: arrived outside Halloween Lion\'s Arch.')
                return
            current = district_identity()
            if current != self.origin and current[:2] == self.destination:
                self.begin_cycle()
            return
        if not valid or Map.GetMapID() != LIONS_ARCH or not Map.IsOutpost():
            self.stop('Stopped: unexpected map change. No further dialogue sent.')
            return
        if self.tree is not None:
            result = self.tree.tick()
            if result == BehaviorTree.NodeState.FAILURE:
                self.stop('Stopped: movement or dialogue failed. No automatic retry.')
                return
            if result != BehaviorTree.NodeState.SUCCESS:
                return
            self.tree.reset()
            self.tree = None
            if self.state == 'approach_steward':
                self.resume_or_accept()
            elif self.state == 'accept_quest':
                self.enter('confirm_mobstoppers')
            elif self.state == 'accept_reward':
                self.enter('confirm_turn_in')
            elif self.state == 'deposit_gold':
                self.enter('confirm_gold_deposit')
            return
        if self.state == 'confirm_gold_deposit':
            carried = int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter())
            stored = int(GLOBAL_CACHE.Inventory.GetGoldInStorage())
            if (self.gold_before - carried == self.gold_amount
                    and stored - self.storage_before == self.gold_amount):
                if carried >= DEPOSIT_THRESHOLD:
                    self.stop('Stopped: gold storage cannot hold enough to reduce carried gold below 90 platinum.')
                elif self.gold_next == 'begin_cycle':
                    self.begin_cycle()
                else:
                    self.after_reward()
            return
        if self.state == 'confirm_skeleton_stack':
            if bag_count(CAPTURED_SKELETON) != self.stack_total:
                self.stop('Stopped: Captured Skeleton total changed during restacking.')
                return
            stacks = skeleton_stacks()
            bag, slot, quantity = self.stack_expected
            if stacks and (stacks[0][0], stacks[0][1], stacks[0][3]) == (bag, slot, quantity):
                self.begin_cycle()
            return
        if self.state == 'confirm_mobstoppers':
            gained = bag_count(MOBSTOPPER) - self.mob_before
            if bag_count(CAPTURED_SKELETON) != self.skeleton_before:
                self.stop('Stopped: Captured Skeleton count changed before the reward interaction.')
            elif gained == 3:
                self.accept_reward()
            elif gained != 0:
                self.stop(f'Stopped: expected 3 Mobstoppers, observed {gained:+d}.')
        elif self.state == 'confirm_turn_in':
            consumed = self.skeleton_before - bag_count(CAPTURED_SKELETON)
            if bag_count(MOBSTOPPER) != self.mob_before + 3:
                self.stop('Stopped: Mobstopper count changed unexpectedly during turn-in.')
            elif consumed == 3:
                self.completed += 1
                print(f'[{MODULE_NAME}] Reward confirmed: {self.completed}/{self.goal}; 3 Captured Skeletons consumed.')
                if not self.deposit_if_needed('after_reward'):
                    self.after_reward()
            elif consumed != 0:
                self.stop(f'Stopped: expected 3 Captured Skeletons consumed, observed {consumed}.')


runner = CycleRunner()
requested_cycles = DEFAULT_CYCLES
ini_key = ''


def update():
    try:
        CycleRunner.tick(runner)
    except Exception as error:
        runner.stop(f'Stopped: {type(error).__name__}: {error}')


def draw():
    global requested_cycles, ini_key
    if not Routines.Checks.Map.MapValid():
        return
    if not ini_key:
        ini_key = Settings('Widgets/EveryBitHelpsHalloween.ini', 'account').name
    if not ini_key:
        return
    try:
        if ImGui.Begin(ini_key, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
            PyImGui.text_wrapped(DESCRIPTION)
            if not runner.running:
                requested_cycles = PyImGui.input_int('Cycles', requested_cycles)
                PyImGui.text(f'Captured Skeletons required: {max(0, requested_cycles) * 3}')
                PyImGui.text(f'In bags: {bag_count(CAPTURED_SKELETON)}')
                if PyImGui.button('Start'):
                    runner.start(requested_cycles)
            elif PyImGui.button('Stop'):
                runner.stop('Stopped by you. Queued actions may finish; inspect the quest before restarting.')
            PyImGui.text(f'Completed cycles: {runner.completed} / {runner.goal}')
            PyImGui.text_wrapped(runner.message)
            PyImGui.text(BUILD_ID)
    finally:
        ImGui.End(ini_key)


def main():
    pass


def on_disable():
    runner.stop('Widget disabled. Inspect the quest before restarting a partial cycle.')


def draw_contents():
    global requested_cycles, ini_key
    PyImGui.text_wrapped(DESCRIPTION)
    if not runner.running:
        requested_cycles = PyImGui.input_int('Cycles', requested_cycles)
        PyImGui.text(f'Captured Skeletons required: {max(0, requested_cycles) * 3}')
        PyImGui.text(f'In bags: {bag_count(CAPTURED_SKELETON)}')
        if PyImGui.button('Start'):
            runner.start(requested_cycles)
    elif PyImGui.button('Stop'):
        runner.stop('Stopped by you. Queued actions may finish; inspect the quest before restarting.')
    PyImGui.text(f'Completed cycles: {runner.completed} / {runner.goal}')
    PyImGui.text_wrapped(runner.message)
    PyImGui.text(BUILD_ID)
