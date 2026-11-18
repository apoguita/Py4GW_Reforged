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
             completed=False, override=False, heroai_backup=None, map_id=0)


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
    try:
        player_xy = Player.GetXY()
        best, best_distance = 0, float('inf')
        for raw in AgentArray.GetNPCMinipetArray():
            agent_id = int(raw)
            if not Agent.IsValid(agent_id):
                continue
            if (Agent.GetNameByID(agent_id) or '').strip().casefold() != MAYOR_NAME.casefold():
                continue
            distance = Utils.Distance(player_xy, Agent.GetXY(agent_id))
            if distance < best_distance:
                best, best_distance = agent_id, distance
        return best, best_distance
    except Exception as exc:
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
        if not spirit and not state['override']:
            if state['heroai_backup']:
                _restore_heroai()
            if state['completed']:
                state['completed'] = False
            _set_stage('Waiting', 'Spirit Form not detected')
            return BehaviorTree.NodeState.RUNNING
        if state['completed']:
            _set_stage('Completed', 'Dialog command dispatched; waiting for Spirit Form to end')
            return BehaviorTree.NodeState.RUNNING
        npc, dist = _find_mayor()
        state['npc'], state['distance'] = npc, dist
        if not npc:
            _set_stage('Find mayor', 'Mayor not loaded / not found (no movement possible)')
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


def _draw_status():
    # Always render the diagnostic panel, even with no map or buff.
    if PyImGui.begin('Dhuum Helper BT - Diagnostic'):
        PyImGui.text('Account: ' + str(Player.GetName() or '?'))
        PyImGui.text('Map: ' + str(state['map_id']) + ' | Spirit Form (3134): ' + ('YES' if state['spirit'] else 'NO'))
        PyImGui.text('BT stage: ' + str(state['stage']))
        PyImGui.text('Mayor agent: ' + str(state['npc']))
        PyImGui.text('Mayor distance: ' + (f"{state['distance']:.0f}" if state['distance'] != float('inf') else 'not loaded'))
        PyImGui.text_wrapped('Last action: ' + str(state['note']))
        if state['last_error']:
            PyImGui.text_wrapped('Last error: ' + str(state['last_error']))
        if PyImGui.button('Retry / reset'):
            _reset('Manual reset')
        PyImGui.same_line()
        if PyImGui.button('Force test (Spirit Form only!)'):
            # Test navigation in Spirit Form even when the Effects cache misses 3134.
            if state['spirit']:
                state['override'] = True
                state['completed'] = False
                _set_stage('Find mayor', 'Manual test requested')
            else:
                _log('Force test refused: no Spirit Form', True)
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
                if not entry.get('normal') and not entry.get('capture_request'):
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
