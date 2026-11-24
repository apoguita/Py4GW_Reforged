"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "cantha_eotn_entry"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'cantha.npc.raiugyon.encoded',
        'npc',
        ('Minister of Maintenance Raiugyon',),
        (33025, 30955, 52200, 51149, 16639),
        None,
        (3292,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'cantha.npc.chasm.encoded',
        'npc',
        ('Chasm',),
        (33026, 951, 54640, 7366),
        None,
        (5917,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'nightfall.npc.bendah.encoded',
        'npc',
        ('Bendah',),
        (33025, 30985, 65258, 53031, 15973),
        None,
        (4756,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'nightfall.npc.fissure.encoded',
        'npc',
        ('Fissure',),
        (33026, 958, 64327, 60784, 15956),
        None,
        (5917,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'eotn.npc.jora.encoded',
        'npc',
        ('Jora',),
        (33026, 1628),
        None,
        (6034,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'eotn.npc.scrying_pool.encoded',
        'npc',
        ('Scrying Pool',),
        None,
        ('npc', 'SCRYING_POOL', 0),
        (5959,),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'cantha.npc.raiugyon.kaineng_center',
        'cantha.npc.raiugyon.encoded',
        194,
        'Kaineng Center',
        (3747.0, -2174.0),
        None,
        ('USER-RAIUGYON-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'cantha.npc.chasm.bukdek_byway',
        'cantha.npc.chasm.encoded',
        240,
        'Bukdek Byway',
        (-10103.0, 16493.0),
        (-10056.87, 16498.35),
        ('USER-CHASM-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'nightfall.npc.bendah.kamadan',
        'nightfall.npc.bendah.encoded',
        449,
        '',
        (-8793.0, 14255.0),
        (-8690.62, 14228.0),
        ('USER-BENDAH-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'nightfall.npc.fissure.plains_of_jarin',
        'nightfall.npc.fissure.encoded',
        430,
        '',
        (13823.0, -13166.0),
        (13760.86, -13131.84),
        ('USER-FISSURE-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'eotn.npc.jora.boreal_exit',
        'eotn.npc.jora.encoded',
        499,
        '',
        (3537.0, -21937.0),
        (3574.07, -22008.62),
        ('USER-JORA-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'eotn.npc.scrying_pool.first_vision',
        'eotn.npc.scrying_pool.encoded',
        646,
        '',
        (-6662.0, 6584.0),
        (-6654.39, 6539.89),
        ('USER-SCRYING_POOL-THIS-CHAT',),
        'candidate',
        ((('source_type', 'user_supplied_entity_capture'),),),
    ),
    (
        'eotn.npc.scrying_pool.against_destroyers_vision',
        'eotn.npc.scrying_pool.encoded',
        646,
        'Hall of Monuments',
        (-6662.0, 6584.0),
        (-6640.09, 6568.69),
        ('NPC-20260829-231831-432', 'NPC-20260829-231928-425'),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'existing_capture_store'),
                ('capture_id', 'NPC-20260829-231831-432'),
                (
                    'evidence',
                    'Same pool name/model/type/target; first visible page and safe player coordinate observed.',
                ),
            ),
            (
                ('source_type', 'existing_mission_source'),
                ('capture_id', 'NPC-20260829-231928-425'),
                ('limitation', 'Declared in source; this second capture is not present in the current capture store.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.scrying_pool.first_vision'),
                (
                    'scope',
                    'Reuse the reviewed encoded Scrying Pool identity only; preserve the Against the Destroyers '
                    'role, map 646 target geometry, source approach, and capture provenance in this distinct '
                    'occurrence.',
                ),
                (
                    'evidence',
                    "Independent mission capture matches the reviewed identity's visible name, model 5959, NPC "
                    'kind, map 646, and target.',
                ),
            ),
        ),
    ),
)
