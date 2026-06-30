#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/constants.h"
#include "GW/common/game_pos.h"
#include "GW/common/gw_array.h"
#include "GW/common/gw_list.h"
#include "GW/context/pathing.h"

#include <cstdint>

namespace GW::Context {

    struct AreaInfo;

    struct MapDimensions {
        uint32_t unk;
        uint32_t start_x;
        uint32_t start_y;
        uint32_t end_x;
        uint32_t end_y;
        uint32_t unk1;
    };

    struct InstanceInfo {
        MapDimensions* terrain_info1;
        GW::Constants::InstanceType instance_type;
        AreaInfo* current_map_info;
        uint32_t terrain_count;
        MapDimensions* terrain_info2;
    };

    struct MapTypeInstanceInfo {
        uint32_t request_instance_map_type;
        bool is_outpost;
        Constants::RegionType map_region_type;
    };

    struct MissionMapIcon { // total: 0x28/40
        /* +h0000 */ uint32_t index;
        /* +h0004 */ float X;
        /* +h0008 */ float Y;
        /* +h000C */ uint32_t h000C; // = 0
        /* +h0010 */ uint32_t h0010; // = 0
        /* +h0014 */ uint32_t option; // Affilitation/color. gray = 0, blue, red, yellow, teal, purple, green, gray
        /* +h0018 */ uint32_t h0018; // = 0
        /* +h001C */ uint32_t model_id; // Model of the displayed icon in the Minimap
        /* +h0020 */ uint32_t h0020; // = 0
        /* +h0024 */ uint32_t h0024; // May concern the name
    };
    static_assert(sizeof(MissionMapIcon) == 0x28, "MissionMapIcon size mismatch");

    using MissionMapIconArray = GW::GWArray<MissionMapIcon>;

    enum Region : uint32_t {
        Region_Kryta,
        Region_Maguuma,
        Region_Ascalon,
        Region_NorthernShiverpeaks,
        Region_HeroesAscent,
        Region_CrystalDesert,
        Region_FissureOfWoe,
        Region_Presearing,
        Region_Kaineng,
        Region_Kurzick,
        Region_Luxon,
        Region_ShingJea,
        Region_Kourna,
        Region_Vaabi,
        Region_Desolation,
        Region_Istan,
        Region_DomainOfAnguish,
        Region_TarnishedCoast,
        Region_DepthsOfTyria,
        Region_FarShiverpeaks,
        Region_CharrHomelands,
        Region_BattleIslands,
        Region_TheBattleOfJahai,
        Region_TheFlightNorth,
        Region_TheTenguAccords,
        Region_TheRiseOfTheWhiteMantle,
        Region_Swat,
        Region_DevRegion
    };

    struct AreaInfo { // total: 0x7C/124
        /* +h0000 */ Constants::Campaign campaign;
        /* +h0004 */ Constants::Continent continent;
        /* +h0008 */ Region region;
        /* +h000C */ Constants::RegionType type;
        /* +h0010 */ uint32_t flags;
        /* +h0014 */ uint32_t thumbnail_id;
        /* +h0018 */ uint32_t min_party_size;
        /* +h001C */ uint32_t max_party_size;
        /* +h0020 */ uint32_t min_player_size;
        /* +h0024 */ uint32_t max_player_size;
        /* +h0028 */ uint32_t controlled_outpost_id;
        /* +h002C */ uint32_t fraction_mission;
        /* +h0030 */ uint32_t min_level;
        /* +h0034 */ uint32_t max_level;
        /* +h0038 */ uint32_t needed_pq;
        /* +h003C */ uint32_t mission_maps_to;
        /* +h0040 */ uint32_t x; // icon position on map.
        /* +h0044 */ uint32_t y;
        /* +h0048 */ uint32_t icon_start_x;
        /* +h004C */ uint32_t icon_start_y;
        /* +h0050 */ uint32_t icon_end_x;
        /* +h0054 */ uint32_t icon_end_y;
        /* +h0058 */ uint32_t icon_start_x_dupe;
        /* +h005C */ uint32_t icon_start_y_dupe;
        /* +h0060 */ uint32_t icon_end_x_dupe;
        /* +h0064 */ uint32_t icon_end_y_dupe;
        /* +h0068 */ uint32_t file_id;
        /* +h006C */ uint32_t mission_chronology;
        /* +h0070 */ uint32_t ha_map_chronology;
        /* +h0074 */ uint32_t name_id;
        /* +h0078 */ uint32_t description_id;

        uint32_t file_id1() const { return ((file_id - 1) % 0xff00) + 0x100; }
        uint32_t file_id2() const { return ((file_id - 1) / 0xff00) + 0x100; }


        bool GetHasEnterButton()         const { return (flags & 0x100) != 0 || (flags & 0x40000) != 0; }
        bool GetIsOnWorldMap()           const { return (flags & 0x20) == 0; }
        bool GetIsPvP()                  const { return (flags & 0x40001) != 0; } // 0x40000 = Explorable, 0x1 = Outpost
        bool GetIsGuildHall()            const { return (flags & 0x800000) != 0; }
        bool GetIsVanquishableArea()     const { return (flags & 0x10000000) != 0; }
        bool GetIsUnlockable()           const { return (flags & 0x10000) != 0; }
        bool GetHasMissionMapsTo()       const { return (flags & 0x8000000) != 0; }
    };
    static_assert(sizeof(AreaInfo) == 0x7C, "AreaInfo size mismatch");

    struct MissionMapSubContext {
        uint32_t h0000[0xE];
    };

    struct MissionMapSubContext2 {
        uint32_t h0000;
        GW::Vec2f player_mission_map_pos;
        uint32_t h000c;
        GW::Vec2f mission_map_size;
        float unk;
        GW::Vec2f mission_map_pan_offset;
        GW::Vec2f mission_map_pan_offset2;
        float unk2[2];
        uint32_t unk3[9];
    };
    static_assert(sizeof(MissionMapSubContext2) == 0x58, "MissionMapSubContext2 size mismatch");

    struct MissionMapContext {
        GW::Vec2f size;
        uint32_t h0008;
        GW::Vec2f last_mouse_location;
        uint32_t frame_id;
        GW::Vec2f player_mission_map_pos;
        GW::GWArray<MissionMapSubContext*> h0020;
        uint32_t h0030;
        uint32_t h0034;
        uint32_t h0038;
        MissionMapSubContext2* h003c;
        uint32_t h0040;
        uint32_t h0044;
    };
    static_assert(sizeof(MissionMapContext) == 0x48, "MissionMapContext size mismatch");

    struct WorldMapContext {
        uint32_t frame_id;
        uint32_t h0004;
        uint32_t h0008;
        float h000c;
        float h0010;
        uint32_t h0014;
        float h0018;
        float h001c;
        float h0020;
        float h0024;
        float h0028;
        float h002c;
        float h0030;
        float h0034;
        float zoom;
        GW::Vec2f top_left;
        GW::Vec2f bottom_right;
        uint32_t h004c[7];
        float h0068;
        float h006c;
        uint32_t params[0x6D];
    };
    static_assert(sizeof(WorldMapContext) == 0x224, "WorldMapContext size mismatch");

    struct PropsContext {
        /* +h0000 */ uint32_t pad1[0x1b];
        /* +h006C */ GW::GWArray<GwList<PropByType>> propsByType;
        /* +h007C */ uint32_t h007C[0xa];
        /* +h00A4 */ GW::GWArray<PropModelInfo> propModels;
        /* +h00B4 */ uint32_t h00B4[0x38];
        /* +h0194 */ GW::GWArray<MapProp*> propArray;
    };
    static_assert(sizeof(PropsContext) == 0x1A4, "PropsContext size mismatch");

    struct MapContext {
        /* +h0000 */ float map_boundaries[5];
        /* +h0014 */ uint32_t h0014[6];
        /* +h002C */ GW::GWArray<void*> spawns1; // Seem to be arena spawns. struct is X,Y,unk 4 byte value,unk 4 byte value.
        /* +h003C */ GW::GWArray<void*> spawns2; // Same as above
        /* +h004C */ GW::GWArray<void*> spawns3; // Same as above
        /* +h005C */ float h005C[6]; // Some trapezoid i think.
        /* +h0074 */ struct sub1 {
            struct sub2 {
                uint32_t pad1[6];
                PathingMapArray pmaps;
            } *sub2;
            /* +h0004 */ GW::GWArray<uint32_t> pathing_map_block;
            /* +h0018 */ uint32_t total_trapezoid_count;
            /* +h0018 */ uint32_t h0014[0x12];
            /* +h0060 */ GW::GWArray<GwList<void*>> something_else_for_props;
            //... Bunch of arrays and shit
        } *sub1;
        /* +h0078 */ uint8_t pad1[4];
        /* +h007C */ PropsContext* props;
        /* +h0080 */ uint32_t h0080;
        /* +h0084 */ void* terrain;
        /* +h0088 */ uint32_t h0088[42];
        /* +h0130 */ void* zones;
        //... Player coords and shit beyond this point if they are desirable :p
    };

    static_assert(offsetof(MapContext, sub1) == 0x74, "MapContext::sub1 offset mismatch");
    static_assert(offsetof(MapContext, props) == 0x7C, "MapContext::props offset mismatch");
    static_assert(offsetof(MapContext, terrain) == 0x84, "MapContext::terrain offset mismatch");
    static_assert(offsetof(MapContext, zones) == 0x130, "MapContext::zones offset mismatch");

    GW::Constants::ServerRegion* GetRegionIdPtr();
    AreaInfo* GetAreaInfoArray();
    MapTypeInstanceInfo* GetMapTypeInstanceInfos();
    uint32_t GetMapTypeInstanceInfosSize();
    uintptr_t GetInstanceInfoPtr();
    InstanceInfo* GetInstanceInfo();

}  // namespace GW::Context
