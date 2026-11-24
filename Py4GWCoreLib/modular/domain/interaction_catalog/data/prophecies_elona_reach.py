"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_elona_reach"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.elona_reach.identity.ghostly_hero',
        'npc',
        ('Ghostly Hero',),
        (12894, 62886, 52176, 15824),
        None,
        (1785,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261029-GHOSTLY-HERO'),
                ('scope', 'Exact automation identity, NPC kind and model supplied by user; moving NPC'),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.ghostly_hero.elona_reach.crystal_1',
        'prophecies.elona_reach.identity.ghostly_hero',
        118,
        'Elona Reach',
        (3317.0, 4927.0),
        (3420.0, 4932.0),
        (
            'NPC-20260821-155534-902:marker:ghostly_hero_1_approach:crystal_1',
            'USER-20261107-INTERACT-ONLY:crystal_1_handoff',
        ),
        'candidate',
        (
            (
                ('source_type', 'existing_capture_occurrence'),
                ('capture_id', 'NPC-20260821-155534-902:marker:ghostly_hero_1_approach:crystal_1'),
                ('source_capture_id', 'NPC-20260821-155534-902'),
                ('source_field', 'markers.ghostly_hero_1_approach'),
                (
                    'scope',
                    'Occurrence-specific identifier derived from the existing capture and preserved route marker; '
                    'this is not a new game capture. Target and approach coordinates are unchanged.',
                ),
            ),
            (
                ('source_type', 'user_chat_clarification'),
                ('capture_id', 'USER-20261107-INTERACT-ONLY:crystal_1_handoff'),
                ('source_message', 'USER-20261107-INTERACT-ONLY'),
                (
                    'scope',
                    'Applies the user statement that all three Hero handoffs require only one interaction, no '
                    'dialogue follow-up, to crystal 1; an occurrence-specific reference to the same '
                    'clarification, not a separate observation.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghostly_hero.elona_reach.crystal_2',
        'prophecies.elona_reach.identity.ghostly_hero',
        118,
        'Elona Reach',
        (-1135.58, 5018.02),
        (-1342.17, 4831.94),
        ('ROUTE-20261029-132249-843:marker:hero_2_approach:crystal_2', 'USER-20261107-INTERACT-ONLY:crystal_2_handoff'),
        'candidate',
        (
            (
                ('source_type', 'existing_capture_occurrence'),
                ('capture_id', 'ROUTE-20261029-132249-843:marker:hero_2_approach:crystal_2'),
                ('source_capture_id', 'ROUTE-20261029-132249-843'),
                ('source_field', 'markers.hero_2_approach'),
                (
                    'scope',
                    'Occurrence-specific identifier derived from the existing capture and preserved route marker; '
                    'this is not a new game capture. Target and approach coordinates are unchanged.',
                ),
            ),
            (
                ('source_type', 'user_chat_clarification'),
                ('capture_id', 'USER-20261107-INTERACT-ONLY:crystal_2_handoff'),
                ('source_message', 'USER-20261107-INTERACT-ONLY'),
                (
                    'scope',
                    'Applies the user statement that all three Hero handoffs require only one interaction, no '
                    'dialogue follow-up, to crystal 2; an occurrence-specific reference to the same '
                    'clarification, not a separate observation.',
                ),
            ),
        ),
    ),
    (
        'prophecies.npc.ghostly_hero.elona_reach.crystal_3',
        'prophecies.elona_reach.identity.ghostly_hero',
        118,
        'Elona Reach',
        (-1135.58, 5018.02),
        (-1340.47, 4885.34),
        (
            'ROUTE-20261029-132249-843:marker:hero_final_approach:crystal_3',
            'USER-20261107-INTERACT-ONLY:crystal_3_handoff',
        ),
        'candidate',
        (
            (
                ('source_type', 'existing_capture_occurrence'),
                ('capture_id', 'ROUTE-20261029-132249-843:marker:hero_final_approach:crystal_3'),
                ('source_capture_id', 'ROUTE-20261029-132249-843'),
                ('source_field', 'markers.hero_final_approach'),
                (
                    'scope',
                    'Occurrence-specific identifier derived from the existing capture and preserved route marker; '
                    'this is not a new game capture. Target and approach coordinates are unchanged.',
                ),
            ),
            (
                ('source_type', 'user_chat_clarification'),
                ('capture_id', 'USER-20261107-INTERACT-ONLY:crystal_3_handoff'),
                ('source_message', 'USER-20261107-INTERACT-ONLY'),
                (
                    'scope',
                    'Applies the user statement that all three Hero handoffs require only one interaction, no '
                    'dialogue follow-up, to crystal 3; an occurrence-specific reference to the same '
                    'clarification, not a separate observation.',
                ),
            ),
        ),
    ),
)
