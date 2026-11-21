import PySystem

from Py4GWCoreLib import (
	Agent,
	AgentArray,
	Color,
	GLOBAL_CACHE,
	ImGui,
	JsonFactory,
	Map,
	Player,
	Py4GW,
	Routines,
	ThrottledTimer,
	UIManager,
	Utils,
)
from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler
import PyImGui
import PyInventory
from Py4GWCoreLib import Inventory
import time
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

MODULE_NAME = "Dhuum Helper"
MODULE_ICON = "Assets/Textures/Module_Icons/Underworld.png"

# Keep this helper very cheap while idle.
_CHECK_TIMER = ThrottledTimer(750)
_CHECK_TIMER.Reset()

_DIALOG_COOLDOWN_TIMER = ThrottledTimer(2500)
_DIALOG_COOLDOWN_TIMER.Reset()

_armor_written_this_map: bool = False

# Shared, cross-account equipped-armor document (global scope so every multibox
# client reads/writes the same map keyed by account email). Underworld.py binds
# this same (name, scope) pair.
_armor_doc = JsonFactory("Widgets/EquippedArmor.json", "global")


def _write_equipped_armor_json() -> None:
	try:
		email = Player.GetAccountEmail()
		if not email:
			return

		_ARMOR_SLOTS = {2, 3, 4, 5, 6}  # Head, Chest, Hands, Legs, Feet
		bag = PyInventory.Bag(22, "Equipped_Items")
		slots: dict[str, int] = {}
		for item in bag.GetItems():
			item_id  = int(getattr(item, "item_id",  0) or 0)
			model_id = int(getattr(item, "model_id", 0) or 0)
			slot     = int(getattr(item, "slot",     0) or 0)
			if item_id == 0 or slot not in _ARMOR_SLOTS:
				continue
			slots[str(slot)] = model_id

		# Merge this account's entry into the shared armor document.
		existing = _armor_doc.get_json(email, {})
		if not isinstance(existing, dict) or "normal" not in existing:
			old_slots = (
				{k: v for k, v in existing.items() if isinstance(k, str) and k.isdigit()}
				if isinstance(existing, dict) else {}
			)
			existing = {"normal": old_slots, "sacrifice": {}}

		# Skip writing if sacrifice armor is currently equipped to avoid overwriting
		# the normal armor configuration with sacrifice model IDs.
		saved_sacrifice = existing.get("sacrifice") or {}
		sacrifice_model_ids = {v for v in saved_sacrifice.values() if v != 0}
		current_model_ids = set(slots.values())
		if sacrifice_model_ids and sacrifice_model_ids.issubset(current_model_ids):
			PySystem.Console.Log(MODULE_NAME, "Armor write skipped - sacrifice armor is equipped.", PySystem.Console.MessageType.Info)
			return

		existing["normal"] = slots
		_armor_doc.set_json(email, existing)
	except Exception as e:
		PySystem.Console.Log(MODULE_NAME, f"Armor write error: {e}", PySystem.Console.MessageType.Warning)


def _dhuum_process_armor_capture_request() -> None:
	"""Capture the actual local equipped armor for a request from UW BT.

	Executed on the follower account, never on the leader. The shared global
	JsonFactory stores per-email requests and the two five-slot profiles.
	"""
	email = str(Player.GetAccountEmail() or '').strip().lower()
	if not email:
		return
	try:
		# Read the request written by the leader in another Py4GW client.
		_armor_doc.reload()
		entry = _armor_doc.get_json(email, {})
		if not isinstance(entry, dict):
			return
		request = entry.get('capture_request', {})
		if not isinstance(request, dict) or not request:
			return
		profile = str(request.get('profile', ''))
		request_id = str(request.get('id', ''))
		if profile not in ('normal', 'sacrifice') or not request_id:
			return
		slots = {}
		bag = PyInventory.Bag(22, 'Equipped_Items')
		for item in bag.GetItems():
			slot = int(getattr(item, 'slot', 0) or 0)
			model_id = int(getattr(item, 'model_id', 0) or 0)
			if slot in (2, 3, 4, 5, 6) and model_id > 0:
				slots[str(slot)] = model_id
		# Never overwrite a previously valid profile on partial/failed capture.
		if len(slots) != 5:
			message = f'FAILED: detected {len(slots)}/5 equipped armor parts. Keep all five pieces equipped and retry.'
			PySystem.Console.Log(MODULE_NAME, message, PySystem.Console.MessageType.Warning)
		else:
			entry[profile] = slots
			message = f'OK: {profile} armor saved (5/5 equipped parts).'
			PySystem.Console.Log(MODULE_NAME, message, PySystem.Console.MessageType.Info)
		entry['capture_response'] = {'id': request_id, 'profile': profile, 'message': message}
		entry.pop('capture_request', None)
		_armor_doc.set_json(email, entry)
		# Publish the response to the leader immediately.
		_armor_doc.save()
	except Exception as exc:
		PySystem.Console.Log(MODULE_NAME, f'Armor capture failed: {exc}', PySystem.Console.MessageType.Warning)



# Standalone BT helper. Run on EACH sacrifice account, not only the leader.
# The tiny window is intentionally always drawn, including outside UW.
MAYOR_NAME = 'Mayor Alegheri'
SPIRIT_ID = 3134
UW_MAP = 72
DIALOG_ID = 0x84
INTERACT_RANGE = 400.0
STEP_TIMEOUT = 25.0
RETRY_MOVE = 1.5
RETRY_INTERACT = 2.0
state = dict(stage='Waiting', note='Widget initialized', npc=0, distance=-1.0,
             spirit=False, last_error='', since=time.monotonic(), last_action=0.0,
             completed=False, override=False, heroai_backup=None, map_id=0,
             npc_scan_count=0, npc_scan_names='', last_scan_error='',
             had_spirit=False, armor_restore_pending=False, armor_last_attempt=0.0,
             armor_started=0.0, armor_error='', armor_restored=False)


def _set_stage(stage, note=''):
    if state['stage'] != stage:
        state['stage'] = stage
        state['since'] = time.monotonic()
    if note:
        state['note'] = note


def _log(note, error=False):
    state['note'] = str(note)
    if error:
        state['last_error'] = str(note)
    PySystem.Console.Log(MODULE_NAME, '[BT] ' + str(note),
        PySystem.Console.MessageType.Warning if error else PySystem.Console.MessageType.Info)


def _find_mayor():
    """Find the loaded mayor, accepting a localized title (Maire/Mayor/etc.)."""
    try:
        player_xy = Player.GetXY()
        best, best_distance = 0, float('inf')
        scanned = 0
        nearby = []
        for raw in AgentArray.GetNPCMinipetArray():
            agent_id = int(raw)
            if not Agent.IsValid(agent_id):
                continue
            scanned += 1
            name = str(Agent.GetNameByID(agent_id) or '').strip()
            if name and len(nearby) < 8:
                nearby.append(name)
            # 'Mayor' is localized on non-English game clients.
            # Do not select generic NPCs: the surname must still match.
            if 'alegheri' not in name.casefold():
                continue
            distance = Utils.Distance(player_xy, Agent.GetXY(agent_id))
            if distance < best_distance:
                best, best_distance = agent_id, distance
        state['npc_scan_count'] = scanned
        state['npc_scan_names'] = ', '.join(nearby)
        state['last_scan_error'] = ''
        return best, best_distance
    except Exception as exc:
        state['last_scan_error'] = str(exc)
        _log('NPC scan failed: ' + str(exc), True)
        return 0, float('inf')


def _pause_heroai():
    if state['heroai_backup'] is not None:
        return
    try:
        email = str(Player.GetAccountEmail() or '').strip()
        opts = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(email)
        if opts is None:
            _log('HeroAI options unavailable; cannot suspend safely', True)
            return
        snapshot = {'email': email}
        for key in ('Following', 'Avoidance', 'Looting', 'Targeting', 'Combat'):
            snapshot[key] = bool(getattr(opts, key, False))
            if hasattr(opts, key):
                setattr(opts, key, False)
        skills = getattr(opts, 'Skills', None)
        snapshot['Skills'] = [bool(skills[i]) for i in range(len(skills))] if skills is not None else []
        if skills is not None:
            for i in range(len(skills)):
                skills[i] = False
        GLOBAL_CACHE.ShMem.SetHeroAIOptionsByEmail(email, opts)
        state['heroai_backup'] = snapshot
        _log('HeroAI movement/combat paused on local sacrifice')
    except Exception as exc:
        _log('HeroAI pause error: ' + str(exc), True)


def _restore_heroai():
    snap = state.get('heroai_backup')
    if not snap:
        return
    try:
        opts = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(snap['email'])
        if opts is None:
            _log('HeroAI restore pending: account options unavailable', True)
            return
        for key in ('Following', 'Avoidance', 'Looting', 'Targeting', 'Combat'):
            if hasattr(opts, key):
                setattr(opts, key, snap[key])
        skills = getattr(opts, 'Skills', None)
        if skills is not None:
            for i, enabled in enumerate(snap['Skills'][:len(skills)]):
                skills[i] = enabled
        GLOBAL_CACHE.ShMem.SetHeroAIOptionsByEmail(snap['email'], opts)
        state['heroai_backup'] = None
        _log('HeroAI restored')
    except Exception as exc:
        _log('HeroAI restore failed: ' + str(exc), True)


# Equipment restoration runs locally on the sacrificed character; it does not
# depend on the leader Planner, which may be paused during Dhuum.
_ARMOR_SLOTS = ('2', '3', '4', '5', '6')
_ARMOR_RETRY_SECONDS = 1.25
_ARMOR_RESTORE_TIMEOUT_SECONDS = 45.0


def _equipped_armor_slots():
    slots = {}
    for item in PyInventory.Bag(22, 'Equipped_Items').GetItems():
        slot = str(int(getattr(item, 'slot', 0) or 0))
        if slot in _ARMOR_SLOTS:
            slots[slot] = int(getattr(item, 'model_id', 0) or 0)
    return slots


def _restore_normal_armor_tick():
    """Restore one missing piece per tick and verify the actual equipped items."""
    if not state['armor_restore_pending']:
        return
    now = time.monotonic()
    if now - state['armor_last_attempt'] < _ARMOR_RETRY_SECONDS:
        return
    state['armor_last_attempt'] = now
    try:
        email = str(Player.GetAccountEmail() or '').strip().lower()
        _armor_doc.reload()
        entry = _armor_doc.get_json(email, {})
        saved = entry.get('normal', {}) if isinstance(entry, dict) else {}
        if not isinstance(saved, dict) or any(int(saved.get(k, 0) or 0) <= 0 for k in _ARMOR_SLOTS):
            raise RuntimeError('NORMAL armor profile incomplete (5 pieces required)')
        equipped = _equipped_armor_slots()
        missing = [k for k in _ARMOR_SLOTS if equipped.get(k) != int(saved[k])]
        if not missing:
            state['armor_restore_pending'] = False
            state['armor_restored'] = True
            state['armor_error'] = ''
            _set_stage('Completed', 'Normal armor restored (5/5)')
            _log('Normal armor restored and verified (5/5)')
            return
        if now - state['armor_started'] > _ARMOR_RESTORE_TIMEOUT_SECONDS:
            state['armor_restore_pending'] = False
            state['armor_error'] = f"Armor not restored: {len(missing)} missing piece(s)"
            _set_stage('Error', state['armor_error'])
            _log(state['armor_error'], True)
            return
        # Bag 22 reports currently equipped items; bags 1-4 carry spare armor.
        needed_slot = missing[0]
        model_id = int(saved[needed_slot])
        matches = []
        for bag_id in (1, 2, 3, 4):
            for item in PyInventory.Bag(bag_id, f'Bag_{bag_id}').GetItems():
                if int(getattr(item, 'model_id', 0) or 0) == model_id:
                    item_id = int(getattr(item, 'item_id', 0) or 0)
                    if item_id > 0:
                        matches.append(item_id)
        if not matches:
            state['armor_error'] = f'Normal armor piece not found: slot {needed_slot}, model {model_id}'
            _set_stage('Restore armor', state['armor_error'])
            return
        Inventory.EquipItem(matches[0], int(Player.GetAgentID()))
        state['armor_error'] = ''
        _set_stage('Restore armor', f'Re-equipping normal armor ({5 - len(missing)}/5)')
    except Exception as exc:
        state['armor_error'] = str(exc)
        _set_stage('Restore armor', 'Armor: ' + state['armor_error'])
        if now - state['armor_started'] > _ARMOR_RESTORE_TIMEOUT_SECONDS:
            state['armor_restore_pending'] = False
            _set_stage('Error', 'Armor restoration failed: ' + state['armor_error'])
            _log(state['note'], True)


def _reset(reason='Reset'):
    _restore_heroai()
    try:
        Player.ChangeTarget(0)
    except Exception:
        pass
    state.update(stage='Waiting', note=reason, npc=0, distance=-1.0,
                 since=time.monotonic(), last_action=0.0, completed=False,
                 override=False)
    tree.reset()


def _tick(_node):
    try:
        if not Routines.Checks.Map.MapValid() or Map.IsMapLoading():
            _set_stage('Waiting', 'Map invalid/loading')
            return BehaviorTree.NodeState.RUNNING
        current_map = int(Map.GetMapID())
        if current_map != UW_MAP:
            _set_stage('Waiting', 'Outside UW')
            return BehaviorTree.NodeState.RUNNING
        pid = int(Player.GetAgentID())
        spirit = bool(GLOBAL_CACHE.Effects.HasEffect(pid, SPIRIT_ID))
        state['spirit'] = spirit
        if spirit:
            if not state['had_spirit']:
                state['armor_restored'] = False
            state['had_spirit'] = True
        elif state['had_spirit'] and not state['armor_restored'] and not state['armor_restore_pending']:
            state['had_spirit'] = False
            state['armor_restore_pending'] = True
            state['armor_started'] = time.monotonic()
            state['armor_last_attempt'] = 0.0
            _log('Spirit Form ended: restoring normal armor locally')
        if state['armor_restore_pending']:
            _restore_heroai()
            _restore_normal_armor_tick()
            return BehaviorTree.NodeState.RUNNING
        if not spirit and not state['override']:
            if state['heroai_backup']:
                _restore_heroai()
            if state['completed']:
                state['completed'] = False
            if not state['armor_restored'] and state['stage'] != 'Error':
                _set_stage('Waiting', 'Spirit Form not detected')
            return BehaviorTree.NodeState.RUNNING
        if state['completed']:
            _set_stage('Completed', 'Dialog command dispatched; waiting for Spirit Form to end')
            return BehaviorTree.NodeState.RUNNING
        npc, dist = _find_mayor()
        state['npc'], state['distance'] = npc, dist
        if not npc:
            _set_stage('Find mayor', f"Mayor not found among {state['npc_scan_count']} loaded NPCs; no movement sent")
            return BehaviorTree.NodeState.RUNNING
        now = time.monotonic()
        if state['stage'] not in ('Move', 'Interact', 'Dialog'):
            _pause_heroai()
            _set_stage('Move')
        if state['stage'] == 'Move':
            if dist <= INTERACT_RANGE:
                _set_stage('Interact', 'Within NPC interaction range')
            elif now - state['last_action'] >= RETRY_MOVE:
                Player.Move(*Agent.GetXY(npc))
                state['last_action'] = now
                state['note'] = f'Move sent, remaining distance {dist:.0f}'
            if now - state['since'] > STEP_TIMEOUT:
                _set_stage('Error', 'Movement timeout; check navigation/obstacles')
                _log(state['note'], True)
                return BehaviorTree.NodeState.RUNNING
        if state['stage'] == 'Interact':
            if now - state['last_action'] >= RETRY_INTERACT:
                Player.ChangeTarget(npc)
                Player.Interact(npc)
                state['last_action'] = now
                state['note'] = f'Interact sent to Mayor agent {npc}'
            if UIManager.IsNPCDialogVisible():
                _set_stage('Dialog', 'NPC dialog opened')
            elif now - state['since'] > STEP_TIMEOUT:
                _set_stage('Error', 'Interaction timeout; NPC dialog not visible')
                _log(state['note'], True)
        if state['stage'] == 'Dialog':
            if UIManager.IsNPCDialogVisible():
                Player.SendDialog(DIALOG_ID)
                state['completed'] = True
                state['override'] = False
                _set_stage('Completed', 'Dialog 0x84 sent; outcome not yet confirmed')
                Player.ChangeTarget(0)
                _restore_heroai()
                _log('Mayor dialog 0x84 sent')
            elif now - state['since'] > STEP_TIMEOUT:
                _set_stage('Error', 'Dialog window disappeared before command')
        return BehaviorTree.NodeState.RUNNING
    except Exception as exc:
        _set_stage('Error')
        _log('BT tick: ' + str(exc), True)
        return BehaviorTree.NodeState.RUNNING


tree = BehaviorTree(BehaviorTree.ActionNode(name='Dhuum Spirit Form: Mayor dialog', action_fn=_tick, aftercast_ms=0))


# Dashboard palette: violet UW accent, green success, amber activity, red errors.
_UI_PURPLE = (0.67, 0.48, 0.97, 1.0)
_UI_GREEN = (0.38, 0.86, 0.63, 1.0)
_UI_AMBER = (1.0, 0.76, 0.37, 1.0)
_UI_RED = (1.0, 0.41, 0.44, 1.0)
_UI_MUTED = (0.61, 0.65, 0.73, 1.0)
_UI_WHITE = (0.92, 0.94, 0.98, 1.0)
_UI_STEPS = ('Waiting', 'Find mayor', 'Move', 'Interact', 'Dialog', 'Completed')


def _ui_text(value, color=None):
    if color is not None:
        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, color)
    PyImGui.text(str(value))
    if color is not None:
        PyImGui.pop_style_color(1)


def _ui_kv(label, value, color=None):
    _ui_text(label, _UI_MUTED)
    PyImGui.same_line()
    _ui_text(value, color or _UI_WHITE)


def _ui_section(title):
    PyImGui.spacing()
    _ui_text(title, _UI_PURPLE)
    PyImGui.separator()


def _draw_status():
    """Compact monitor: current action and BT progress only."""
    opened = PyImGui.begin('Dhuum Helper BT')
    if opened:
        stage = str(state['stage'])
        if stage in _UI_STEPS:
            fraction = _UI_STEPS.index(stage) / (len(_UI_STEPS) - 1)
        elif stage == 'Restore armor':
            fraction = 0.9
        else:
            fraction = 0.0
        labels = {
            'Waiting': 'Waiting for Spirit Form',
            'Find mayor': 'Finding Mayor Alegheri',
            'Move': 'Moving to Mayor Alegheri',
            'Interact': 'Interacting with Mayor Alegheri',
            'Dialog': 'Talking to Mayor Alegheri',
            'Completed': 'Normal armor restored' if state['armor_restored'] else 'Dialog sent',
            'Restore armor': 'Restoring normal armor',
            'Error': 'Error: ' + str(state['note'] or state['last_error'] or 'Unknown'),
        }
        color = (_UI_RED if stage == 'Error' else
                 _UI_GREEN if stage == 'Completed' else
                 _UI_AMBER if stage not in ('Waiting',) else _UI_MUTED)
        _ui_text(labels.get(stage, stage), color)
        PyImGui.progress_bar(fraction, -1, 0, f'{int(fraction * 100)}%')
    PyImGui.end()


_armor_written_this_map = False
_last_capture_check = 0.0


def main():
    global _armor_written_this_map, _last_capture_check
    try:
        valid = Routines.Checks.Map.MapValid() and not Map.IsMapLoading()
        state['map_id'] = int(Map.GetMapID()) if valid else 0
        if valid:
            now = time.monotonic()
            if now - _last_capture_check >= 1.0:
                _last_capture_check = now
                _dhuum_process_armor_capture_request()
            if not _armor_written_this_map:
                email = str(Player.GetAccountEmail() or '').strip().lower()
                entry = _armor_doc.get_json(email, {}) if email else {}
                if not isinstance(entry, dict):
                    entry = {}
                # Never capture sacrifice gear as a new normal profile while a
                # spirit is active or armor restoration is pending.
                if (not entry.get('normal') and not entry.get('capture_request')
                        and not state['had_spirit'] and not state['armor_restore_pending']
                        and not GLOBAL_CACHE.Effects.HasEffect(int(Player.GetAgentID()), SPIRIT_ID)):
                    _write_equipped_armor_json()
                _armor_written_this_map = True
        else:
            _armor_written_this_map = False
        tree.tick()
    except Exception as exc:
        _log('main: ' + str(exc), True)
    finally:
        try:
            _draw_status()
        except Exception as exc:
            PySystem.Console.Log(MODULE_NAME, 'UI error: ' + str(exc), PySystem.Console.MessageType.Warning)


if __name__ == '__main__':
    main()
