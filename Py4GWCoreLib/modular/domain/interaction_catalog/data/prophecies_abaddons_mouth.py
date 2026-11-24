"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_abaddons_mouth"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.abaddons_mouth.identity.leah_stone',
        'npc',
        ('Leah Stone',),
        (15563, 44760, 42877, 32717),
        None,
        (2406,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-LEAH-20261114'),
                ('scope', 'Escort-time observation; not initial-spawn geometry.'),
            ),
        ),
    ),
    (
        'prophecies.abaddons_mouth.identity.ether_seal',
        'npc',
        ('Ether Seal',),
        (4683, 59422, 34787, 32022),
        None,
        (2302,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-ETHER-SEAL-20261114'),
                ('scope', 'Seal imprisoning Leah Stone.'),
            ),
        ),
    ),
    (
        'prophecies.abaddons_mouth.identity.spectral_essence',
        'item',
        ('Spectral Essence',),
        (9609, 62480, 8322),
        None,
        (2569,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-SPECTRAL-ESSENCE-20261114'),
                (
                    'scope',
                    'Ground item and held slot matched item ID 119 and model 2569; runtime item ID is not ' 'durable.',
                ),
            ),
        ),
    ),
    (
        'prophecies.abaddons_mouth.identity.ancient_seer',
        'npc',
        ('Ancient Seer',),
        (15476, 60492, 54280, 26978),
        None,
        (2600,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-ANCIENT-SEER-20261114'),
                ('scope', 'Infusion interaction target.'),
            ),
        ),
    ),
    (
        'prophecies.abaddons_mouth.identity.eidolon',
        'npc',
        ('Eidolon',),
        (15157, 54967, 52198, 26780),
        None,
        (2603,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-EIDOLON-20261114'),
                ('scope', 'Spectral Essence producer.'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.leah_stone.abaddons_mouth.7652_4260',
        'prophecies.abaddons_mouth.identity.leah_stone',
        123,
        "Abaddon's Mouth",
        (7652.36, 4260.03),
        (7784.85, 3816.47),
        ('USER-AM-LEAH-20261114',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-LEAH-20261114'),
                ('scope', 'Moving escort observation only.'),
            ),
        ),
    ),
    (
        'prophecies.npc.ether_seal.abaddons_mouth.6147_10386',
        'prophecies.abaddons_mouth.identity.ether_seal',
        123,
        "Abaddon's Mouth",
        (6147.0, 10386.0),
        (6304.99, 7782.91),
        ('USER-AM-ETHER-SEAL-20261114',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-ETHER-SEAL-20261114'),
                ('scope', 'Exact bonus seal occurrence.'),
            ),
        ),
    ),
    (
        'prophecies.item.spectral_essence.abaddons_mouth.-20789_801',
        'prophecies.abaddons_mouth.identity.spectral_essence',
        123,
        "Abaddon's Mouth",
        (-20789.03, 801.1),
        (-21311.87, 149.06),
        ('USER-AM-SPECTRAL-ESSENCE-20261114',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-SPECTRAL-ESSENCE-20261114'),
                ('scope', 'Exact dropped item occurrence with ground-to-held proof.'),
            ),
        ),
    ),
    (
        'prophecies.npc.ancient_seer.abaddons_mouth.-13997_-12201',
        'prophecies.abaddons_mouth.identity.ancient_seer',
        123,
        "Abaddon's Mouth",
        (-13997.0, -12201.0),
        (-13722.09, -12775.05),
        ('USER-AM-ANCIENT-SEER-20261114',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-ANCIENT-SEER-20261114'),
                ('scope', 'Exact infusion interaction occurrence.'),
            ),
        ),
    ),
    (
        'prophecies.npc.eidolon.abaddons_mouth.-21424_308',
        'prophecies.abaddons_mouth.identity.eidolon',
        123,
        "Abaddon's Mouth",
        (-21423.85, 307.82),
        (-20716.56, 797.03),
        ('USER-AM-EIDOLON-20261114',),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-AM-EIDOLON-20261114'),
                ('scope', 'Exact mission Eidolon occurrence.'),
            ),
        ),
    ),
)
