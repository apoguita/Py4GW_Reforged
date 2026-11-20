#region STATES
from typing import TYPE_CHECKING, Dict, Callable, Any

if TYPE_CHECKING:
    from Py4GWCoreLib.botting_src.helpers import BottingClass


#region EVENTS
class _EVENTS:
    def __init__(self, parent: "BottingClass"):
        self.parent = parent
        self._config = parent.config
        self._helpers = parent.helpers
        self._events = parent.config.events
        
    def _on_party_member_behind(self):
            from ...Routines import Routines
            from ...Py4GWcorelib import Utils
            from ...enums import Range
            from ...GlobalCache import GLOBAL_CACHE
            bot = self.parent

            left_direction  = True
            try:
                print("Party Member behind, emitting pixel stack")
                yield from Routines.Yield.Movement.StopMovement()

                retries = 0
                max_retries = 3  # <-- configurable number of retries
                emit_count = 0  # <--- added: count pixel-stack emits
                
                while retries < max_retries:
                    if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                        print("Party wiped, aborting OnPartyMemberBehind")
                        return
                    
                    
                    
                    yield from bot.helpers.Multibox._pixel_stack()
                    emit_count += 1
                    # call brute-force helper every 2 emits
                    if emit_count % 2 == 0:
                        yield from bot.helpers.Multibox._brute_force_unstuck()
                        
                    last_emit = Utils.GetBaseTimestamp()

                    # inner wait loop for this attempt
                    while not Routines.Checks.Party.IsAllPartyMembersInRange(Range.Spellcast.value):
                        yield from bot.Wait._coro_for_time(500)

                        # re-emit pixel stack every 10s
                        now = Utils.GetBaseTimestamp()
                        if now - last_emit >= 10000:
                            print("Re-emitting pixel stack, and spinning in place!, weeeee")
                            yield from bot.helpers.Multibox._pixel_stack()
                            last_emit = now
                            emit_count += 1
                            # call brute-force helper every 2 emits
                            if emit_count % 2 == 0:
                                yield from bot.helpers.Multibox._brute_force_unstuck()


                        if not Routines.Checks.Agents.InDanger():
                            if left_direction:
                                yield from Routines.Yield.Movement.TurnLeft(300)
                                left_direction = False
                            else:
                                yield from Routines.Yield.Movement.TurnRight(300)
                                left_direction = True


                        if not Routines.Checks.Map.MapValid():
                            print("Map invalid, breaking pixel stack loop")
                            return

                        # success condition
                        if Routines.Checks.Party.IsAllPartyMembersInRange(Range.Spellcast.value):
                            print("Party Member in range, resuming")
                            return

                    retries += 1
                    print(f"Pixel stack attempt {retries} failed, retrying...")

                print("Pixel stack retries exhausted, giving up")

            finally:
                # guarantee FSM resume no matter what
                bot.config.FSM.resume()
                yield

    def _on_party_member_in_danger(self):
        from ...Routines import Routines
        from ...GlobalCache import GLOBAL_CACHE
        from ...Agent import Agent
        from ...Player import Player
        from ...Pathing import AutoPathing
        from ...Py4GWcorelib import Utils
        from ...enums import Range
        bot = self.parent

        try:
            while True:
                if not Routines.Checks.Map.MapValid():
                    return

                if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                    return

                if Routines.Checks.Agents.InDanger():
                    return

                party_member_id = Routines.Checks.Party.GetPartyMemberInDangerID()
                if party_member_id == 0 or not Agent.IsValid(party_member_id) or Agent.IsDead(party_member_id):
                    return

                member_pos = Agent.GetXY(party_member_id)
                if Utils.Distance(member_pos, Player.GetXY()) <= Range.Spellcast.value:
                    return

                path = yield from AutoPathing().get_path_to(member_pos[0], member_pos[1])
                if not path:
                    return

                exit_condition = lambda: (
                    not Routines.Checks.Map.MapValid()
                    or Routines.Checks.Agents.InDanger()
                    or Routines.Checks.Party.IsPartyWiped()
                    or GLOBAL_CACHE.Party.IsPartyDefeated()
                    or Routines.Checks.Party.GetPartyMemberInDangerID() == 0
                )

                yield from Routines.Yield.Movement.FollowPath(
                    path_points=path,
                    custom_exit_condition=exit_condition,
                    tolerance=Range.Spellcast.value,
                    timeout=10000,
                )
                yield from Routines.Yield.wait(100)
                return
        finally:
            bot.config.FSM.resume()
            yield

    def _on_party_member_death_behind(self):
        from ...Routines import Routines
        from ...GlobalCache import GLOBAL_CACHE
        from ...Agent import Agent
        from ...Player import Player
        from ...Py4GWcorelib import Utils
        from ...enums import Range
        from ..helpers_src.HeroAICombatRange import hero_ai_combat_detected
        bot = self.parent

        def _combat_active() -> bool:
            return bool(hero_ai_combat_detected(include_party=True))

        def _recovery_must_abort() -> bool:
            return bool(
                not Routines.Checks.Map.MapValid()
                or Routines.Checks.Party.IsPartyWiped()
                or GLOBAL_CACHE.Party.IsPartyDefeated()
                or _combat_active()
            )

        try:
            if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                print("Party wiped, aborting OnPartyMemberDeadBehind")
                return

            # The event is already gated on HeroAI combat state, but check it
            # again here to close the race between event detection and callback
            # execution.  Never start corpse regrouping during combat.
            if _combat_active():
                print("Combat active, postponing dead-party-member recovery")
                return

            print("Party Member dead behind")
            dead_player = Routines.Party.GetDeadPartyMemberID()
            if dead_player == 0 or not Agent.IsValid(dead_player):
                return

            print("Combat is over, moving to a safe regroup point near dead party member")
            dead_pos = Agent.GetXY(dead_player)
            player_pos = Player.GetXY()
            dead_distance = Utils.Distance(dead_pos, player_pos)
            if dead_distance <= Range.Spellcast.value:
                print("Dead party member already within spellcast range")
                return

            # Keep the regroup flag away from the corpse itself.  If the player
            # died inside a trap or another hazardous area, stacking directly on
            # the body can kill the rest of the party.  Approach from the current
            # leader side and stop 500 units short of the corpse.
            regroup_distance = 500.0
            scale = regroup_distance / dead_distance
            regroup_pos = (
                dead_pos[0] + (player_pos[0] - dead_pos[0]) * scale,
                dead_pos[1] + (player_pos[1] - dead_pos[1]) * scale,
            )

            print(
                f"Dead party member at ({dead_pos[0]:.0f}, {dead_pos[1]:.0f}); "
                f"safe regroup point=({regroup_pos[0]:.0f}, {regroup_pos[1]:.0f}) "
                f"({regroup_distance:.0f} units from corpse)"
            )

            path = [regroup_pos]
            result = yield from Routines.Yield.Movement.FollowPath(
                path,
                custom_exit_condition=_recovery_must_abort,
                tolerance=100.0,
                timeout=30000,
            )
            yield from Routines.Yield.wait(100)

            if _recovery_must_abort():
                print("Dead-party-member recovery interrupted before regroup")
                return

            # The target may have been resurrected while the leader was moving.
            if not Agent.IsValid(dead_player) or not Agent.IsDead(dead_player):
                print("Dead party member was revived before regroup")
                return

            if not result:
                print("Failed to move to safe regroup point")
                return

            print("Arrived at safe regroup point, regrouping for revival")

            # This is the multibox regroup order.  It is deliberately the last
            # action and only runs after all combat/wipe checks have passed.
            yield from bot.helpers.Multibox._pixel_stack()
        finally:
            # The callback pauses the FSM before starting this coroutine.  A
            # wipe/combat abort must therefore resume it too, not just success.
            bot.config.FSM.resume()
            yield

    def OnDeathCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.on_death.set_callback(callback)

    def OnPartyWipeCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.on_party_wipe.set_callback(callback)

    def OnPartyDefeatedCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.on_party_defeated.set_callback(callback)
        
    #def OnStuckCallback(self, callback: Callable[[], None]) -> None:
    #    self._config.events.on_stuck.set_callback(callback)
        
    #def SetStuckRoutineEnabled(self, state: bool) -> None:
    #    self._config.events.set_stuck_routine_enabled(state)
        
    def OnPartyMemberBehindCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.set_on_party_member_behind_callback(callback)

    def OnPartyMemberInDangerCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.set_on_party_member_in_danger_callback(callback)

    def OnPartyMemberDeadCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.set_on_party_member_dead_callback(callback)
        
    def OnPartyMemberDeadBehindCallback(self, callback: Callable[[], None]) -> None:
        self._config.events.set_on_party_member_dead_behind_callback(callback)
        
    
