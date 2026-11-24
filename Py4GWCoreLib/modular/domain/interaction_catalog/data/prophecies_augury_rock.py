"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "prophecies_augury_rock"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'prophecies.augury_rock.identity.great_ritual_priest_zahmut',
        'npc',
        ('Great Ritual Priest Zahmut',),
        (12831, 34368, 34435, 11007),
        None,
        (94,),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-ZAHMUT-AUGURY38'),
                (
                    'scope',
                    'User supplied exact automation identity, actor kind, diagnostic model ID and target/player '
                    'coordinates. Runtime agent ID is excluded from durable identity.',
                ),
            ),
        ),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'prophecies.npc.great_ritual_priest_zahmut.augury_rock_outpost.-14294_-422',
        'prophecies.augury_rock.identity.great_ritual_priest_zahmut',
        38,
        'Augury Rock outpost',
        (-14294.0, -422.0),
        (-14373.97, -419.7),
        ('USER-20261107-ZAHMUT-AUGURY38', 'NPC-20260829-100459-831', 'NPC-20260829-100519-172'),
        'candidate',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261107-ZAHMUT-AUGURY38'),
                (
                    'scope',
                    'User supplied exact automation identity, actor kind, diagnostic model ID and target/player '
                    'coordinates. Runtime agent ID is excluded from durable identity.',
                ),
            ),
            (
                ('source_type', 'existing_mission_source'),
                ('capture_ids', ['NPC-20260829-100459-831', 'NPC-20260829-100519-172']),
                (
                    'scope',
                    'Baseline augury_enter_mission recorded visible one-based buttons (1, 1); canonical automatic '
                    'dialogue preserves those choices as zero-based [0, 0]. Original capture payloads were not '
                    're-read; this is source-reference evidence.',
                ),
            ),
        ),
    ),
)
