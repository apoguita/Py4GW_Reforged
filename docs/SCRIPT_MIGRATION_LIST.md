# Script migration list

All 179 modules are currently **widgets**. This is the candidate list for moving them to
`Scripts/` one at a time. Nothing here is done yet.

Ordering is lowest-risk first: no `__file__` use, no path derivation, no sibling assets.
Rows with a **risk** entry need a look before moving -- that column is what broke things
in the bulk trial run.

## Process per script

1. Add the `__script__` block shown in the row
2. `git mv` the file to `Scripts/<name>.py` (flat -- no subfolders)
3. Move any listed sibling assets alongside it
4. Remove the folder's `.widget` marker if no `.py` remains
5. Verify with the registry: metadata extracts, imports resolve

## Candidates (146)

| # | id | function | tags | claims | loc | risk | current path |
|---|---|---|---|---|---|---|---|
| 1 | `packetsniffertester` | debug | - | **none** | 146 | - | `Coding/Debug/Guild Wars/PacketSnifferTester.py` |
| 2 | `resolve_catalog_text` | debug | - | **none** | 156 | - | `Coding/Debug/Py4GW/Resolve Catalog Text.py` |
| 3 | `ui_listener` | debug | - | **none** | 177 | - | `Coding/Debug/Guild Wars/UI_Listener.py` |
| 4 | `dump_named_mod_table` | debug | - | **none** | 179 | - | `Coding/Debug/Py4GW/Dump Named Mod Table.py` |
| 5 | `callback_monitor` | debug | - | **none** | 185 | - | `Coding/Debug/Py4GW/Callback Monitor.py` |
| 6 | `mod_discovery` | debug | - | **none** | 195 | - | `Coding/Debug/Py4GW/Mod Discovery.py` |
| 7 | `mod_parity_scan` | debug | - | **none** | 201 | - | `Coding/Debug/Py4GW/Mod Parity Scan.py` |
| 8 | `resolve_mod_tables` | debug | - | **none** | 229 | - | `Coding/Debug/Py4GW/Resolve Mod Tables.py` |
| 9 | `dump_item_catalogs` | debug | - | **none** | 259 | - | `Coding/Debug/Py4GW/Dump Item Catalogs.py` |
| 10 | `sharedmem_isolation_manager` | debug | - | **sharedmem** | 308 | - | `Coding/Debug/Py4GW/SharedMem Isolation Manager.py` |
| 11 | `item_mods_playground` | debug | - | **inventory** | 381 | - | `Coding/Debug/Py4GW/Item Mods Playground.py` |
| 12 | `frame_tester` | debug | - | **none** | 483 | - | `Coding/Debug/Guild Wars/Frame_Tester.py` |
| 13 | `accountdata` | debug | - | **skills** | 530 | - | `Coding/Debug/Guild Wars/AccountData.py` |
| 14 | `agent_info` | debug | - | **none** | 597 | - | `Coding/Debug/Guild Wars/Agent Info.py` |
| 15 | `quest_data` | debug | - | **none** | 634 | - | `Coding/Debug/Guild Wars/Quest Data.py` |
| 16 | `rawframe_tester` | debug | - | **none** | 810 | - | `Coding/Debug/Guild Wars/RawFrame_Tester.py` |
| 17 | `system_monitor` | debug | - | **none** | 849 | - | `Coding/Debug/Py4GW/System Monitor.py` |
| 18 | `gameconfigviewer` | debug | - | **none** | 854 | - | `Coding/Debug/Guild Wars/GameConfigViewer.py` |
| 19 | `sharedmem_monitor` | debug | - | **none** | 1045 | - | `Coding/Debug/Py4GW/SharedMem Monitor.py` |
| 20 | `combateventstester` | debug | - | **skills** | 1188 | - | `Coding/Debug/Guild Wars/CombatEventsTester.py` |
| 21 | `frame_showcase` | debug | - | **none** | 1351 | - | `Coding/Debug/Guild Wars/Frame_Showcase.py` |
| 22 | `skill_trainer` | dialog | - | **dialog** | 33 | - | `Automation/Helpers/Dialogs/Skill Trainer.py` |
| 23 | `profession_unlocker` | dialog | - | **dialog inventory** | 233 | - | `Automation/Helpers/Dialogs/Profession Unlocker.py` |
| 24 | `snowball_dominance` | event | - | **character inventory** | 575 | - | `Automation/Bots/Events/Winter/snowball_dominance.py` |
| 25 | `rollerbeetle_racing` | event | - | **character inventory** | 624 | - | `Automation/Bots/Events/Rollerbeetle Racing.py` |
| 26 | `imgui_official_demo` | example | - | **none** | 47 | - | `Coding/ImGui/ImGui Official DEMO.py` |
| 27 | `floatingicon_example` | example | - | **none** | 89 | - | `Coding/Examples/FloatingIcon example.py` |
| 28 | `color_picker` | example | - | **none** | 95 | - | `Coding/ImGui/Color Picker.py` |
| 29 | `color_pallete` | example | - | **none** | 135 | - | `Coding/ImGui/Color Pallete.py` |
| 30 | `icon_explorer` | example | - | **none** | 206 | - | `Coding/ImGui/Icon Explorer.py` |
| 31 | `pathplanner` | example | - | **character** | 218 | - | `Coding/Examples/Pathing/PathPlanner.py` |
| 32 | `scanner_test` | example | - | **none** | 350 | - | `Coding/Examples/Low Level/Scanner Test.py` |
| 33 | `skillinfo` | example | - | **skills** | 686 | - | `Coding/Examples/Skills/SkillInfo.py` |
| 34 | `gold_crimson_skull` | farmer | nicholas trophie | **character** | 50 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Gold Crimson Skull.py` |
| 35 | `jade_bracelet` | farmer | nicholas trophie | **character** | 57 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Jade Bracelet.py` |
| 36 | `behemoth_hides` | farmer | nicholas trophie | **character** | 59 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Behemoth Hides.py` |
| 37 | `skull_juju` | farmer | nicholas trophie | **character** | 60 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Skull Juju.py` |
| 38 | `truffle` | farmer | nicholas trophie | **character** | 62 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Truffle.py` |
| 39 | `putrid_cyst` | farmer | nicholas trophie | **character** | 63 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Putrid Cyst.py` |
| 40 | `mandragor_swamproot` | farmer | nicholas trophie | **character** | 64 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Mandragor Swamproot.py` |
| 41 | `kath_hammers` | farmer | - | **character** | 64 | - | `Automation/Bots/Miscellaneous/kath_hammers.py` |
| 42 | `dragon_root` | farmer | nicholas trophie | **character** | 65 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Dragon Root.py` |
| 43 | `maguuma_mane` | farmer | nicholas trophie | **character** | 68 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Maguuma Mane.py` |
| 44 | `minotaur_horn_farm` | farmer | nicholas trophie | **character** | 69 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Minotaur Horn Farm.py` |
| 45 | `frosted_griffon_wing` | farmer | nicholas trophie | **character** | 70 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Frosted Griffon Wing.py` |
| 46 | `jade_mandible` | farmer | nicholas trophie | **character** | 70 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Jade Mandible.py` |
| 47 | `spiked_crest` | farmer | nicholas trophie | **character** | 70 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Spiked Crest.py` |
| 48 | `glowing_heart` | farmer | nicholas trophie | **character** | 73 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Glowing Heart.py` |
| 49 | `berserker_horn` | farmer | nicholas trophie | **character** | 75 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Berserker Horn.py` |
| 50 | `chunk_of_drake_flesh` | farmer | nicholas trophie | **character** | 75 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Chunk of Drake Flesh.py` |
| 51 | `eye_of_argon` | farmer | green shield weapon | **character** | 76 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Shield/Eye of Argon.py` |
| 52 | `frigid_heart` | farmer | nicholas trophie | **character** | 80 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Frigid Heart.py` |
| 53 | `intricate_grawl_necklace` | farmer | nicholas trophie | **character** | 80 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Intricate Grawl Necklace.py` |
| 54 | `saurian_bone` | farmer | nicholas trophie | **character** | 80 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Saurian Bone.py` |
| 55 | `behemoth_jaw` | farmer | nicholas trophie | **character** | 82 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Behemoth Jaw.py` |
| 56 | `silver_bullion_coin` | farmer | nicholas trophie | **character** | 82 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Silver Bullion Coin.py` |
| 57 | `shriveled_eye` | farmer | nicholas trophie | **character** | 95 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Shriveled Eye.py` |
| 58 | `skelk_claw` | farmer | nicholas trophie | **character** | 95 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Skelk Claw.py` |
| 59 | `gold_doubloon` | farmer | nicholas trophie | **character** | 105 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Gold Doubloon.py` |
| 60 | `kaolin_wand` | farmer | green wand weapon | **character** | 105 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Wand/Kaolin Wand.py` |
| 61 | `ssaresh_s_kris_daggers` | farmer | dagger green weapon | **character** | 109 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Dagger/Ssaresh's Kris Daggers.py` |
| 62 | `exuro_s_will` | farmer | green staff weapon | **character** | 112 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Staff/Exuro's Will.py` |
| 63 | `kepkhet_s_refuge` | farmer | green staff weapon | **character** | 113 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Staff/Kepkhet's Refuge.py` |
| 64 | `the_scar_eater` | farmer | green staff weapon | **character** | 113 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Staff/The Scar Eater.py` |
| 65 | `confessors_orders_exchange` | farmer | trophie warsupply | **character inventory** | 118 | - | `Automation/Bots/Farmers/Trophies/War Supply/Confessors Orders Exchange.py` |
| 66 | `brightclaw` | farmer | green wand weapon | **character** | 121 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Wand/Brightclaw.py` |
| 67 | `ice_breaker` | farmer | green hammer weapon | **character** | 126 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Hammer/Ice Breaker.py` |
| 68 | `rajazan_s_fervor` | farmer | green sword weapon | **character** | 127 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Sword/Rajazan's Fervor.py` |
| 69 | `dessicated_hydra_claws` | farmer | nicholas trophie | **character** | 140 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Dessicated Hydra Claws.py` |
| 70 | `charr_farmer` | farmer | presearing trophie | **character inventory** | 144 | - | `Automation/Bots/Farmers/Trophies/PreAscalon/Charr Farmer.py` |
| 71 | `totem_axe` | farmer | axe green weapon | **character** | 156 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Axe/Totem Axe.py` |
| 72 | `icy_dragon_sword` | farmer | skin sword weapon | **character** | 167 | - | `Automation/Bots/Farmers/Weapons/Cool Skins/Sword/Icy Dragon Sword.py` |
| 73 | `asterius_scythe` | farmer | green scythe weapon | **character** | 214 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Scythe/Asterius Scythe.py` |
| 74 | `briahns_guidance` | farmer | green shield weapon | **character** | 231 | - | `Automation/Bots/Farmers/Weapons/Green_Unique/Shield/Briahns Guidance.py` |
| 75 | `keen_oni_talon` | farmer | nicholas trophie | **character** | 261 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Keen Oni Talon.py` |
| 76 | `hardened_hump` | farmer | nicholas trophie | **character** | 268 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Hardened Hump.py` |
| 77 | `pile_of_elemental_dust` | farmer | nicholas trophie | **character** | 270 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Pile Of Elemental Dust.py` |
| 78 | `icy_lodestone` | farmer | nicholas trophie | **character** | 283 | - | `Automation/Bots/Farmers/Trophies/Nicholas the Traveler/Icy Lodestone.py` |
| 79 | `crystalline_sword` | farmer | skin sword weapon | **character** | 289 | - | `Automation/Bots/Farmers/Weapons/Cool Skins/Sword/Crystalline Sword.py` |
| 80 | `proof_of_legend_bot_faction_edition` | farmer | trophie | **character inventory** | 497 | - | `Automation/Bots/Farmers/Trophies/Proof of Legend bot Faction edition.py` |
| 81 | `yavb_2_0` | farmer | - | **character inventory** | 615 | - | `Automation/Bots/Farmers/Events/YAVB 2.0.py` |
| 82 | `proof_of_legend_bot_3_0_nightfall_edition_by_wick_divinus` | farmer | nightfall trophie | **character** | 710 | - | `Automation/Bots/Farmers/Trophies/Proof of Legend bot 3.0 Nightfall edition by Wick Divinus.py` |
| 83 | `tower_of_courage_farmer` | farmer | material | **character inventory** | 1089 | - | `Automation/Bots/Farmers/Materials/Obsidian Shards/tower_of_courage_farmer.py` |
| 84 | `heartsofthenorth` | farmer | trophie warsupply | **character inventory** | 1485 | - | `Automation/Bots/Farmers/Trophies/War Supply/HeartsOfTheNorth.py` |
| 85 | `cof_bone_farmer` | farmer | material | **character inventory** | 1713 | - | `Automation/Bots/Farmers/Materials/Bones/cof_bone_farmer.py` |
| 86 | `dragon_moss_fiber_farmer` | farmer | material | **character inventory** | 2297 | - | `Automation/Bots/Farmers/Materials/fiber/dragon moss fiber farmer.py` |
| 87 | `item_eater` | inventory | - | **inventory** | 87 | - | `Guild Wars/Items & Loot/item_eater.py` |
| 88 | `superitemeater` | inventory | - | **inventory** | 627 | - | `Guild Wars/Items & Loot/SuperItemEater.py` |
| 89 | `kilroy_stonekins_punch_out_extravaganza` | leveler | - | **character** | 117 | - | `Automation/Bots/Levelers/KillroyStoneskin/Kilroy Stonekins Punch-Out Extravaganza.py` |
| 90 | `farmer_hamnet_bot` | leveler | - | **character inventory** | 453 | - | `Automation/Bots/Levelers/Farmer Hamnet Bot.py` |
| 91 | `nightfall_leveler` | leveler | nightfall | **character inventory** | 2055 | - | `Automation/Bots/Levelers/Nightfall/Nightfall_leveler.py` |
| 92 | `factions_character_leveler` | leveler | factions | **character inventory** | 2719 | - | `Automation/Bots/Levelers/Factions/Factions Character Leveler.py` |
| 93 | `py4gw_ldoa` | leveler | prophecies | **character inventory** | 3564 | - | `Automation/Bots/Levelers/Prophecies/Py4GW - LDoA.py` |
| 94 | `tihark_orchard` | mission | nightfall | **character** | 116 | - | `Automation/Bots/Missions/NightFall/Tihark Orchard.py` |
| 95 | `chahbek_village_zm` | mission | nightfall | **character inventory** | 661 | - | `Automation/Bots/Missions/NightFall/Chahbek Village ZM.py` |
| 96 | `zaishen_bounty` | mission | - | **character** | 685 | - | `Automation/Bots/Missions/Zaishen_Bounty.py` |
| 97 | `legendary_guardian` | mission | - | **character** | 1587 | - | `Automation/Bots/Missions/Legendary Guardian.py` |
| 98 | `underworld` | mission | core | **character inventory** | 3261 | - | `Automation/Bots/Missions/Core/Underworld.py` |
| 99 | `sulfurous_runner` | runner | - | **character** | 104 | - | `Automation/Bots/Runners/Sulfurous Runner.py` |
| 100 | `outpostrunnerv2` | runner | - | **character** | 374 | - | `Automation/Bots/Runners/OutpostRunnerV2.py` |
| 101 | `pongmei_chestrun` | runner | chest | **character inventory** | 381 | - | `Automation/Bots/Runners/Chest/Pongmei chestrun.py` |
| 102 | `barbarous_shore_chestrun` | runner | chest | **character inventory** | 420 | - | `Automation/Bots/Runners/Chest/Barbarous_Shore_Chestrun.py` |
| 103 | `hells_precipice_chestrun` | runner | chest | **character inventory** | 452 | - | `Automation/Bots/Runners/Chest/Hells_Precipice_Chestrun.py` |
| 104 | `modular_coder` | tool | - | **none** | 35 | - | `Automation/modular/Modular Coder.py` |
| 105 | `disable_camera_smoothing` | tool | - | **ui** | 43 | - | `Guild Wars/Customization/Disable Camera Smoothing.py` |
| 106 | `window_renamer` | tool | - | **ui** | 54 | - | `Guild Wars/Customization/Window Renamer.py` |
| 107 | `close_rejoinable` | tool | - | **ui** | 124 | - | `Coding/Tools/Close Rejoinable.py` |
| 108 | `native_button_test_harness` | tool | - | **none** | 496 | - | `Coding/Tools/Native Button Test Harness.py` |
| 109 | `layout_manager` | tool | - | **ui** | 696 | - | `Guild Wars/Customization/Layout Manager.py` |
| 110 | `modular_tester` | tool | - | **character** | 910 | - | `Automation/modular/Modular Tester.py` |
| 111 | `bridge_client` | tool | - | **inventory skills** | 1106 | - | `Coding/Tools/Bridge Client.py` |
| 112 | `route_builder` | tool | - | **character** | 1392 | - | `Coding/Tools/Route Builder.py` |
| 113 | `py4gw_demo` | tool | - | **character inventory** | 2778 | - | `Coding/Py4GW_DEMO.py` |
| 114 | `drazach_thicket` | vanquish | factions | **character** | 362 | - | `Automation/Bots/Vanquish/Factions/Echovald Forest/Drazach Thicket.py` |
| 115 | `ferndale` | vanquish | factions | **character** | 364 | - | `Automation/Bots/Vanquish/Factions/Echovald Forest/Ferndale.py` |
| 116 | `morostav_trail` | vanquish | factions | **character** | 367 | - | `Automation/Bots/Vanquish/Factions/Echovald Forest/Morostav Trail.py` |
| 117 | `pyquishai` | vanquish | - | **character** | 845 | - | `Automation/Bots/Vanquish/PyQuishAI.py` |
| 118 | `simple_vanquish` | vanquish | - | **character** | 945 | - | `Automation/Bots/Vanquish/Simple_Vanquish.py` |
| 119 | `eliteskillscapture` | capture | - | **character inventory** | 12617 | __file__ path-derive | `Automation/Helpers/Elite Skills/EliteSkillsCapture.py` |
| 120 | `canthadialogsender` | dialog | factions | **dialog** | 237 | __file__ path-derive | `Automation/Helpers/Dialogs/CanthaDialogSender.py` |
| 121 | `nfdialogsender` | dialog | - | **dialog** | 336 | __file__ path-derive | `Automation/Helpers/Dialogs/NFDialogSender.py` |
| 122 | `balthazar_skill_unlock` | dialog | - | **dialog** | 566 | __file__ path-derive | `Automation/Helpers/Dialogs/Balthazar Skill Unlock.py` |
| 123 | `terob` | farmer | green wand weapon | **character** | 98 | path-derive | `Automation/Bots/Farmers/Weapons/Green_Unique/Wand/Terob.py` |
| 124 | `darkroot` | farmer | dagger green weapon | **character** | 99 | path-derive | `Automation/Bots/Farmers/Weapons/Green_Unique/Dagger/Darkroot.py` |
| 125 | `focus_of_hanaku` | farmer | focus green weapon | **character** | 99 | path-derive | `Automation/Bots/Farmers/Weapons/Green_Unique/Focus/Focus of Hanaku.py` |
| 126 | `wingstorm` | farmer | green wand weapon | **character** | 107 | path-derive | `Automation/Bots/Farmers/Weapons/Green_Unique/Wand/Wingstorm.py` |
| 127 | `the_mindsquall` | farmer | focus green weapon | **character** | 110 | path-derive | `Automation/Bots/Farmers/Weapons/Green_Unique/Focus/The Mindsquall.py` |
| 128 | `sunspear_title_farm` | farmer | nightfall title | **character** | 695 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Sunspear title farm.py` |
| 129 | `lightbringer_mirroroflyss` | farmer | nightfall title | **character** | 875 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Lightbringer - MirrorOfLyss.py` |
| 130 | `vanguard_title_farm` | farmer | eotn title | **character** | 947 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Vanguard title farm.py` |
| 131 | `deldrimor_title_farm_by_wick_divinus` | farmer | eotn title | **character inventory** | 1411 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Deldrimor title farm by Wick Divinus.py` |
| 132 | `asura_title_farm_by_wick_divinus` | farmer | eotn title | **character inventory** | 1552 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Asura title farm by Wick Divinus.py` |
| 133 | `norn_title_farmer_by_wick_divinus` | farmer | eotn title | **character inventory** | 1707 | __file__ path-derive assets:Asura Title Farm Heroes.json | `Automation/Bots/Farmers/Titles/Norn title farmer by Wick Divinus.py` |
| 134 | `kamadan_trade_spammer` | helper | - | **character** | 483 | __file__ assets:Kamadan Trade Spammer.ini | `Automation/Enhancements/Kamadan Trade Spammer.py` |
| 135 | `dhuum_helper` | helper | - | **character inventory** | 571 | assets:Kamadan Trade Spammer.ini | `Automation/Enhancements/Dhuum Helper.py` |
| 136 | `inventoryplus` | inventory | - | **inventory** | 3085 | __file__ path-derive | `Guild Wars/Items & Loot/InventoryPlus.py` |
| 137 | `xunlaimanager` | inventory | - | **inventory** | 3400 | path-derive | `Guild Wars/Items & Loot/Xunlaimanager.py` |
| 138 | `merchantrules` | inventory | - | **inventory** | 30378 | path-derive | `Guild Wars/Items & Loot/MerchantRules.py` |
| 139 | `polymock` | minigame | - | **character** | 78 | __file__ path-derive | `Automation/Bots/Miscellaneous/Polymock.py` |
| 140 | `frog_scepter_bot` | mission | dungeon | **character inventory** | 2927 | path-derive assets:bds.png,Frog Scepter.png | `Automation/Bots/Missions/Dungeons/Frog Scepter bot.py` |
| 141 | `soo` | mission | dungeon | **character inventory** | 3429 | path-derive assets:bds.png,Frog Scepter.png | `Automation/Bots/Missions/Dungeons/SoO.py` |
| 142 | `quest_auto_runner_simple` | runner | - | **character inventory** | 812 | path-derive | `Automation/Bots/Runners/Quest Auto-Runner (Simple).py` |
| 143 | `outpostrunner_v1_0` | runner | - | **character** | 907 | path-derive | `Automation/Bots/Runners/Outpostrunner v1.0.py` |
| 144 | `script_runner` | tool | - | **none** | 282 | path-derive | `Coding/Tools/Script Runner.py` |
| 145 | `heroai_skill_editor` | tool | - | **skills** | 2179 | __file__ | `Guild Wars/Customization/HeroAi Skill Editor.py` |
| 146 | `mount_qinkai` | vanquish | factions | **character inventory** | 1566 | __file__ path-derive | `Automation/Bots/Vanquish/Factions/The Jade Sea/Mount Qinkai.py` |

## Staying as widgets (33)

`action_queue_monitor`, `active_dialog_viewer`, `calendar`, `chatcommandbroadcast`, `combatprep`, `debug_terminal`, `disable_alcohol_effect`, `enemy_tracker`, `environment_upkeeper`, `ez_cast`, `frame_limiter`, `heroai`, `herohelper`, `heroic_refrain`, `instance_timer`, `lootmanager`, `map_overlay`, `messaging`, `multiboxing`, `partyquestlog`, `pet_helper`, `pycons`, `skillbar`, `style_manager`, `survival_title_helper`, `switch_character`, `system_settings`, `teaminventoryviewer`, `titlehelper`, `titles`, `travel`, `vanquish_tracker`, `widgettemplate`

## Vocabulary

`character` `inventory` `skills` `dialog` `ui` `sharedmem`

Arbitration: two scripts claiming the same resource cannot co-run.
`character` subsumes `dialog`, so a bot excludes dialog senders.

## Known issues found during the trial run

- `Widgets/Automation/Bots/Farmers/Weapons/Green_Unique/Bow/Chiggen's Shortbow` is a
  working bot **missing its `.py` extension**, so discovery has never seen it.
- `GTOB killer.py` and `EOTN_SKILL_UNLOCKER.py` sit in folders with no `.widget`
  marker, so they are also undiscovered.
- `EOTN_SKILL_UNLOCKER.py` reads `ICONS_PATH` from `Bots/SkillsUnlocker/icons`, which
  is empty; its icons are at `Widgets/Automation/Bots/SkillsUnlocker/icons`.
- The `update_ownership` hook splits filenames on spaces and writes truncated entries
  (`Monitor.py`, `Info.py`) into `.vscode/settings.json`. Pre-existing.
- Widget discovery imports every module it finds (`Widget.__post_init__` calls
  `load_module`), so all 179 execute at boot.
