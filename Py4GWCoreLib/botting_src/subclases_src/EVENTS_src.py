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
        from ...Pathing import AutoPathing
        from ...Py4GWcorelib import Utils
        from ...enums import Range
        bot = self.parent

        try:
            print("Party member dead behind; pausing route for recovery")
            recovery_pass = 0
            while True:
                if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                    print("Party wiped during member recovery; handing off to wipe recovery")
                    return

                dead_player = Routines.Party.GetDeadPartyMemberID()
                if dead_player == 0:
                    print("All party members revived; resuming route")
                    return
                if not Agent.IsValid(dead_player):
                    yield from Routines.Yield.wait(500)
                    continue

                # Finish nearby combat before backtracking so survivors do not
                # drag a mob train onto the corpse.
                while Routines.Checks.Agents.InDanger():
                    if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                        return
                    yield from Routines.Yield.wait(500)

                dead_player = Routines.Party.GetDeadPartyMemberID()
                if dead_player == 0:
                    continue
                if not Agent.IsValid(dead_player):
                    yield from Routines.Yield.wait(500)
                    continue

                dead_pos = Agent.GetXY(dead_player)
                distance = Utils.Distance(dead_pos, Player.GetXY())
                if distance > Range.Spellcast.value:
                    print(
                        f"Backtracking to dead party member {dead_player} "
                        f"at ({dead_pos[0]:.0f}, {dead_pos[1]:.0f}), distance={distance:.0f}"
                    )
                    path = yield from AutoPathing().get_path_to(dead_pos[0], dead_pos[1])
                    if not path:
                        path = [(dead_pos[0], dead_pos[1])]
                    yield from Routines.Yield.Movement.FollowPath(
                        path_points=path,
                        custom_exit_condition=lambda target=dead_player: (
                            Routines.Checks.Party.IsPartyWiped()
                            or GLOBAL_CACHE.Party.IsPartyDefeated()
                            or not Agent.IsValid(target)
                            or not Agent.IsDead(target)
                        ),
                        tolerance=Range.Spellcast.value,
                        timeout=30000,
                    )

                if Routines.Checks.Party.IsPartyWiped() or GLOBAL_CACHE.Party.IsPartyDefeated():
                    return

                # Gather surviving heroes at the corpse and actually wait for
                # HeroAI to perform resurrection. Repeat for multiple corpses.
                recovery_pass += 1
                print(f"Waiting at corpse for HeroAI resurrection (pass {recovery_pass})")
                yield from bot.helpers.Multibox._pixel_stack()
                yield from Routines.Yield.wait(2500)
        finally:
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
        
    
