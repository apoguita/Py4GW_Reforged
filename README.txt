Party member recovery centralization patch

Modified files:
- Py4GWCoreLib/botting_tree_src/services.py
- Py4GWCoreLib/botting_tree_src/upkeep.py
- Py4GWCoreLib/botting_tree_src/config.py
- Py4GWCoreLib/botting_tree_src/ticks.py
- Widgets/Automation/Bots/Missions/Dungeons/Shards Of Orr BT.py

Behavior:
- Planner freezes as soon as a party member is dead.
- No corpse regroup flags/movement are issued during combat.
- Existing recovery flags are restored immediately if combat starts.
- Outside combat, living members regroup 500 units from the selected corpse.
- Recovery remains active until the party is alive again.
- Total party wipes remain owned by PartyWipeRecoveryService.
- Shards no longer contains its own PartyAliveGate recovery implementation.
