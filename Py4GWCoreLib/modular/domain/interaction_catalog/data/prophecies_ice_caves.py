"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_ice_caves"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.ice_caves.identity.rornak',
        'npc',
        ('Rornak Stonesledge',),
        (15040, 48224, 32585),
        None,
        (1560,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-rornak'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.identity.evennia',
        'npc',
        ('Evennia',),
        (15076, 34416, 27295),
        None,
        (1533,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-evennia'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.identity.hamdor',
        'npc',
        ('Hamdor Grandaxe',),
        (15046, 34501, 43649, 19020),
        None,
        (1556,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-hamdor'),
                ('scope', 'Exact automation identity and entity XY; user player XY intentionally excluded.'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.ice_caves.lever',
        'prophecies.frost_gate.identity.firing_lever',
        22,
        'Ice Caves of Sorrow',
        (-11527.0, 1631.0),
        (-11514.07, 1618.98),
        ('USER-20261108-ICS-lever',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-lever'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'prophecies.gadget.firing_lever.frost_gate.-3644_-8415'),
                (
                    'scope',
                    'Direct Ice Caves capture independently corroborates exact encoded identity, visible name and '
                    'gadget kind; retain distinct map, role, coordinates and capture provenance.',
                ),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.station_1',
        'eotn.gadget.dwarven_powder_keg_station.enc_213b_8bb2_bbfb_197e',
        22,
        'Ice Caves of Sorrow',
        (-9963.0, 9414.0),
        (-9908.63, 9409.95),
        ('USER-20261108-ICS-station_1',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-station_1'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                (
                    'reference_occurrence',
                    'eotn.gadget.dwarven_powder_keg_station.enc_213b_8bb2_bbfb_197e.vloxen_excavations_level_2.17923_15344',
                ),
                (
                    'scope',
                    'Direct Ice Caves capture independently corroborates exact encoded identity, visible name and '
                    'gadget kind; retain distinct map, role, coordinates and capture provenance.',
                ),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.station_2',
        'eotn.gadget.dwarven_powder_keg_station.enc_213b_8bb2_bbfb_197e',
        22,
        'Ice Caves of Sorrow',
        (672.0, -8850.0),
        (644.56, -8745.85),
        ('USER-20261108-ICS-station_2',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-station_2'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                (
                    'reference_occurrence',
                    'eotn.gadget.dwarven_powder_keg_station.enc_213b_8bb2_bbfb_197e.vloxen_excavations_level_2.17923_15344',
                ),
                (
                    'scope',
                    'Direct Ice Caves capture independently corroborates exact encoded identity, visible name and '
                    'gadget kind; retain distinct map, role, coordinates and capture provenance.',
                ),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.rornak',
        'prophecies.ice_caves.identity.rornak',
        22,
        'Ice Caves of Sorrow',
        (-2811.0, -5009.0),
        (-2942.94, -4942.55),
        ('USER-20261108-ICS-rornak',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-rornak'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.evennia',
        'prophecies.ice_caves.identity.evennia',
        22,
        'Ice Caves of Sorrow',
        (5387.0, -7867.0),
        None,
        ('USER-20261108-ICS-evennia',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-evennia'),
                ('scope', 'Exact automation identity and entity XY; player XY intentionally excluded.'),
            ),
        ),
    ),
    (
        'prophecies.ice_caves.hamdor',
        'prophecies.ice_caves.identity.hamdor',
        22,
        'Ice Caves of Sorrow',
        (9682.0, -9309.0),
        (9755.44, -9283.19),
        ('USER-20261108-ICS-hamdor',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261108-ICS-hamdor'),
                ('scope', 'Exact automation identity and entity XY; user player XY intentionally excluded.'),
            ),
        ),
    ),
)
