"""Static interaction catalog partitions."""

from . import cantha_eotn_entry as cantha_eotn_entry
from . import cantha_missions as cantha_missions
from . import cantha_vanquish as cantha_vanquish
from . import eotn_dungeons as eotn_dungeons
from . import eotn_norn as eotn_norn
from . import eotn_oola as eotn_oola
from . import eotn_tarnished_coast as eotn_tarnished_coast
from . import eotn_vanguard as eotn_vanguard
from . import mission_ledger_encounters as mission_ledger_encounters
from . import mission_runner_canonical_cleanup as mission_runner_canonical_cleanup
from . import nightfall_abaddons_gate as nightfall_abaddons_gate
from . import nightfall_blacktide as nightfall_blacktide
from . import nightfall_dasha as nightfall_dasha
from . import nightfall_desolation as nightfall_desolation
from . import nightfall_grand_court as nightfall_grand_court
from . import nightfall_pogahn as nightfall_pogahn
from . import nightfall_realm_of_torment as nightfall_realm_of_torment
from . import nightfall_sunspear as nightfall_sunspear
from . import prophecies_abaddons_mouth as prophecies_abaddons_mouth
from . import prophecies_althea as prophecies_althea
from . import prophecies_augury_rock as prophecies_augury_rock
from . import prophecies_bloodstone as prophecies_bloodstone
from . import prophecies_dragons_lair as prophecies_dragons_lair
from . import prophecies_elona_reach as prophecies_elona_reach
from . import prophecies_frost_gate as prophecies_frost_gate
from . import prophecies_ice_caves as prophecies_ice_caves
from . import prophecies_iron_mines as prophecies_iron_mines
from . import prophecies_thirsty_river as prophecies_thirsty_river

PARTITIONS = (
    nightfall_dasha,
    nightfall_pogahn,
    nightfall_desolation,
    nightfall_grand_court,
    eotn_norn,
    eotn_dungeons,
    eotn_oola,
    eotn_tarnished_coast,
    eotn_vanguard,
    nightfall_sunspear,
    nightfall_blacktide,
    nightfall_realm_of_torment,
    cantha_missions,
    cantha_eotn_entry,
    cantha_vanquish,
    prophecies_althea,
    prophecies_bloodstone,
    nightfall_abaddons_gate,
    prophecies_frost_gate,
    prophecies_elona_reach,
    prophecies_augury_rock,
    prophecies_dragons_lair,
    prophecies_thirsty_river,
    prophecies_ice_caves,
    prophecies_abaddons_mouth,
    prophecies_iron_mines,
    mission_runner_canonical_cleanup,
    mission_ledger_encounters,
)
