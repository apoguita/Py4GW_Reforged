"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "nightfall_grand_court"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'nightfall.npc.head_priest_vahmani.encoded',
        'npc',
        ('Head Priest Vahmani',),
        (33025, 16576, 62165, 31299),
        None,
        (5715,),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '5D98433EC729C4CA02647370F8B1EFE8E9D60A67C5BD8999C544F3FC872DC33E'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'nightfall.npc.head_priest_vahmani.grand_court_of_sebelkeh.1493_6659',
        'nightfall.npc.head_priest_vahmani.encoded',
        435,
        'Grand Court of Sebelkeh outpost',
        (1493.0, 6659.0),
        (1528.26, 6721.85),
        ('USER-20261107-HEAD_PRIEST_VAHMANI', 'NPC-20260830-094619-190', 'NPC-20260830-094628-893'),
        'reviewed',
        (
            (
                ('source_type', 'user_supplied_entity_capture'),
                ('source_sha256', '5D98433EC729C4CA02647370F8B1EFE8E9D60A67C5BD8999C544F3FC872DC33E'),
            ),
        ),
    ),
)
