"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "nightfall_pogahn"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'nightfall.npc.jack_of_truths.enc_8101_3d20_e184_b08c_29f1',
        'npc',
        ('Jack of Truths',),
        (33025, 15648, 57732, 45196, 10737),
        None,
        (5123,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Jack of Truths entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.guard_captain_kahturin.enc_8101_5146_812c_f511_3a39',
        'npc',
        ('Guard Captain Kahturin',),
        (33025, 20806, 33068, 62737, 14905),
        None,
        (5417,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Guard Captain Kahturin entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.captain_nahnkos.enc_8101_5143_92af_f6ee_657b',
        'npc',
        ('Captain Nahnkos',),
        (33025, 20803, 37551, 63214, 25979),
        None,
        (5417,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Captain Nahnkos entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.guard_linko.enc_8101_47a1_ce40_f203_387f',
        'npc',
        ('Guard Linko',),
        (33025, 18337, 52800, 61955, 14463),
        None,
        (5415,),
        'reviewed',
        ((('source_type', 'route_waypoint_capture'), ('locator', 'ROUTE-20261118-102150-808:point-31')),),
    ),
    (
        'nightfall.npc.prison_keeper_shelkesh.enc_8101_5145_83db_fd29_19cd',
        'npc',
        ('Prison Keeper Shelkesh',),
        (33025, 20805, 33755, 64809, 6605),
        None,
        (5417,),
        'reviewed',
        ((('source_type', 'route_waypoint_capture'), ('locator', 'ROUTE-20261118-102508-436:point-13')),),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'nightfall.npc.jack_of_truths.pogahn_passage.3986_1393',
        'nightfall.npc.jack_of_truths.enc_8101_3d20_e184_b08c_29f1',
        426,
        'Pogahn Passage',
        (3986.0, 1393.0),
        (3917.64, 1273.53),
        ('USER-20261118-POGAHN-JACK',),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Jack of Truths entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.guard_captain_kahturin.pogahn_passage.5815_10708',
        'nightfall.npc.guard_captain_kahturin.enc_8101_5146_812c_f511_3a39',
        426,
        'Pogahn Passage',
        (5815.0, 10708.0),
        (5867.53, 10762.47),
        ('USER-20261118-POGAHN-KAHTURIN',),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Guard Captain Kahturin entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.captain_nahnkos.pogahn_passage.4238_5203',
        'nightfall.npc.captain_nahnkos.enc_8101_5143_92af_f6ee_657b',
        426,
        'Pogahn Passage',
        (4238.0, 5203.0),
        (4162.64, 5191.7),
        ('USER-20261118-POGAHN-NAHNKOS',),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_text_capture'),
                ('source', 'Codex chat'),
                ('locator', 'Mission: Pogahn Passage, Captain Nahnkos entity capture, 2026-11-18'),
            ),
        ),
    ),
    (
        'nightfall.npc.guard_linko.pogahn_passage.1933_-7655',
        'nightfall.npc.guard_linko.enc_8101_47a1_ce40_f203_387f',
        426,
        'Pogahn Passage',
        (1933.0, -7655.0),
        (2004.96, -7648.61),
        ('NPC-20261118-102404-812',),
        'reviewed',
        ((('source_type', 'route_waypoint_capture'), ('locator', 'ROUTE-20261118-102150-808:point-31')),),
    ),
    (
        'nightfall.npc.prison_keeper_shelkesh.pogahn_passage.5957_-3412',
        'nightfall.npc.prison_keeper_shelkesh.enc_8101_5145_83db_fd29_19cd',
        426,
        'Pogahn Passage',
        (5957.0, -3412.0),
        (5898.27, -3453.46),
        ('NPC-20261118-102535-302', 'USER-20261118-POGAHN-SHELKESH'),
        'reviewed',
        ((('source_type', 'route_waypoint_capture'), ('locator', 'ROUTE-20261118-102508-436:point-13')),),
    ),
)
