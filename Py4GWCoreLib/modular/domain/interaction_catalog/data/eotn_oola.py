"""Generated static interaction catalog partition. Do not edit rows in isolation."""

from __future__ import annotations

from .schema import IdentityRow
from .schema import OccurrenceRow

PARTITION = "eotn_oola"

IDENTITIES: tuple[IdentityRow, ...] = (
    (
        'eotn.npc.blimm.oola_rata_sum',
        'npc',
        ('Blimm',),
        (33025, 30604, 51143, 38602, 28022),
        None,
        (6776,),
        'reviewed',
        ((('source_type', 'user_chat_capture'), ('capture_id', 'USER-20261103-OOLA-BLIMM'), ('map_id', 640)),),
    ),
)

OCCURRENCES: tuple[OccurrenceRow, ...] = (
    (
        'eotn.npc.blimm.rata_sum.16024_18468',
        'eotn.npc.blimm.oola_rata_sum',
        640,
        'Rata Sum',
        (16024.0, 18468.0),
        (16930.07, 15330.09),
        ('USER-20261103-OOLA-BLIMM',),
        'reviewed',
        ((('source_type', 'user_chat_capture'), ('capture_id', 'USER-20261103-OOLA-BLIMM')),),
    ),
    (
        'eotn.npc.blimm.lab_space_magus_acknowledgement',
        'eotn.npc.blimm.oola_rata_sum',
        569,
        'Magus Stones',
        (10228.0, 11488.0),
        (10295.4, 11498.67),
        ('NPC-20260809-222221-362', 'NPC-20260809-222223-393'),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'existing_mission_source'),
                ('capture_ids', ['NPC-20260809-222221-362', 'NPC-20260809-222223-393']),
                (
                    'limitation',
                    'Declared source captures and geometry retained; raw capture rows were not located in checked '
                    'stores.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.blimm.rata_sum.16024_18468'),
                (
                    'scope',
                    'Reuse only the reviewed Blimm encoded identity; preserve distinct Lab Space acknowledgement '
                    'role, map569 geometry, approach and source provenance.',
                ),
                (
                    'evidence',
                    'Independent source names Blimm, model6776, living NPC target kind and this role-specific '
                    'geometry; no contrary identity/type observation found.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.blimm.lab_space_reward',
        'eotn.npc.blimm.oola_rata_sum',
        569,
        'Magus Stones',
        (-17597.36, 15027.91),
        (-17443.0, 15132.0),
        ('NPC-20260809-222844-836',),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'existing_mission_source'),
                ('capture_ids', ['NPC-20260809-222844-836']),
                (
                    'limitation',
                    'Declared source captures and geometry retained; raw capture rows were not located in checked '
                    'stores.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.blimm.rata_sum.16024_18468'),
                (
                    'scope',
                    'Reuse only the reviewed Blimm encoded identity; preserve distinct Reward from following '
                    'Blimm role, map569 geometry, approach and source provenance.',
                ),
                (
                    'evidence',
                    'Independent source names Blimm, model6776, living NPC target kind and this role-specific '
                    'geometry; no contrary identity/type observation found.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.blimm.elusive_standalone_start',
        'eotn.npc.blimm.oola_rata_sum',
        569,
        'Magus Stones',
        (-17451.0, 14953.0),
        (-17378.89, 14942.89),
        ('NPC-20260809-141337-993',),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'existing_mission_source'),
                ('capture_ids', ['NPC-20260809-141337-993']),
                (
                    'limitation',
                    'Declared source captures and geometry retained; raw capture rows were not located in checked '
                    'stores.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.blimm.rata_sum.16024_18468'),
                (
                    'scope',
                    'Reuse only the reviewed Blimm encoded identity; preserve distinct Start The Elusive '
                    'Golemancer from standalone route role, map569 geometry, approach and source provenance.',
                ),
                (
                    'evidence',
                    'Independent source names Blimm, model6776, living NPC target kind and this role-specific '
                    'geometry; no contrary identity/type observation found.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.blimm.elusive_after_lab_space_start',
        'eotn.npc.blimm.oola_rata_sum',
        569,
        'Magus Stones',
        (-17597.36, 15027.91),
        (-17443.0, 15132.0),
        (),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'existing_mission_source'),
                ('capture_ids', ['NPC-20260809-222844-836', 'NPC-20260809-141337-993']),
                (
                    'limitation',
                    'Declared source captures and geometry retained; raw capture rows were not located in checked '
                    'stores.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.blimm.rata_sum.16024_18468'),
                (
                    'scope',
                    'Reuse only the reviewed Blimm encoded identity; preserve distinct Continue directly after '
                    'Lab Space reward role, map569 geometry, approach and source provenance.',
                ),
                (
                    'evidence',
                    'Independent source names Blimm, model6776, living NPC target kind and this role-specific '
                    'geometry; no contrary identity/type observation found.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_1.18593_-2488',
        'eotn.npc.beacon_of_droknar',
        578,
        "Oola's Lab (level 1)",
        (18593.0, -2488.0),
        (18470.0, -2470.0),
        (),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'preserved_oola_source'),
                (
                    'scope',
                    'Target geometry and established player approach retained from the installed Oola ' 'composition.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Same Beacon name, model 5916, NPC kind, and canonical encoded identity; Oola map, role, '
                    'target, and player approach remain occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_1.6869_4709',
        'eotn.npc.beacon_of_droknar',
        578,
        "Oola's Lab (level 1)",
        (6869.0, 4709.0),
        (6877.17, 4701.34),
        ('NPC-20260901-211913-738',),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'user_entity_location_capture'),
                ('capture_id', 'NPC-20260901-211913-738'),
                ('scope', 'Oola level-1 Beacon target and player approach geometry.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Same Beacon name, model 5916, NPC kind, and canonical encoded identity; Oola occurrence '
                    'geometry remains distinct.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_1.-10563_12879',
        'eotn.npc.beacon_of_droknar',
        578,
        "Oola's Lab (level 1)",
        (-10563.0, 12879.0),
        (-10561.79, 12875.45),
        ('NPC-20260901-212600-622',),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'user_entity_location_capture'),
                ('capture_id', 'NPC-20260901-212600-622'),
                ('scope', 'Oola level-1 Beacon target and player approach geometry.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Same Beacon name, model 5916, NPC kind, and canonical encoded identity; Oola occurrence '
                    'geometry remains distinct.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_2.19087_-19809',
        'eotn.npc.beacon_of_droknar',
        579,
        "Oola's Lab (level 2)",
        (19087.0, -19809.0),
        (18970.0, -19785.0),
        (),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'preserved_oola_source'),
                (
                    'scope',
                    'Target geometry and established player approach retained from the installed Oola ' 'composition.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Same Beacon name, model 5916, NPC kind, and canonical encoded identity; Oola map, role, '
                    'target, and player approach remain occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_2.16475_-13937',
        'eotn.npc.beacon_of_droknar',
        579,
        "Oola's Lab (level 2)",
        (16475.0, -13937.0),
        (16471.38, -13898.24),
        ('USER-20261123-OOLA-L2-BEACON', 'ROUTE-20261123-182840-895'),
        'reviewed',
        (
            (('source_type', 'user_chat_capture'), ('capture_id', 'USER-20261123-OOLA-L2-BEACON')),
            (
                ('source_type', 'recorded_route_capture'),
                ('capture_id', 'ROUTE-20261123-182840-895'),
                ('scope', 'Player route points and player stand-off only; target geometry remains interaction-only.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Exact encoded identity, visible name, model 5916, and NPC kind match the reviewed canonical '
                    'Beacon identity; Oola map, role, target, and player approach remain occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_2.3347_-9203',
        'eotn.npc.beacon_of_droknar',
        579,
        "Oola's Lab (level 2)",
        (3347.0, -9203.0),
        (3336.64, -9283.1),
        ('USER-20261123-OOLA-L2-BEACON-3347_-9203',),
        'reviewed',
        (
            (
                ('source_type', 'user_chat_capture'),
                ('capture_id', 'USER-20261123-OOLA-L2-BEACON-3347_-9203'),
                ('scope', 'Exact Beacon target and player stand-off geometry on Oola level 2.'),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.oola_level_2.16475_-13937'),
                (
                    'scope',
                    'Exact encoded identity, visible name, model 5916, and NPC kind match the reviewed Oola '
                    'Beacon occurrence; target, stand-off, and route role remain occurrence-specific.',
                ),
            ),
        ),
    ),
    (
        'eotn.npc.beacon_of_droknar.oola_level_3.-14843_8081',
        'eotn.npc.beacon_of_droknar',
        580,
        "Oola's Lab (level 3)",
        (-14843.0, 8081.0),
        (-14720.0, 8085.0),
        (),
        'reviewed_identity_with_occurrence_geometry',
        (
            (
                ('source_type', 'preserved_oola_source'),
                (
                    'scope',
                    'Target geometry and established player approach retained from the installed Oola ' 'composition.',
                ),
            ),
            (
                ('source_type', 'identity_reuse'),
                ('reference_occurrence', 'eotn.npc.beacon_of_droknar.frostmaw_level_1.-16179_17596'),
                (
                    'scope',
                    'Same Beacon name, model 5916, NPC kind, and canonical encoded identity; Oola map, role, '
                    'target, and player approach remain occurrence-specific.',
                ),
            ),
        ),
    ),
)
