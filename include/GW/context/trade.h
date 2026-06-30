#pragma once

#include "base/error_handling.h"

#include "GW/common/gw_array.h"

#include <cstddef>
#include <cstdint>

namespace GW::Context {

    struct TradeItem {
        uint32_t item_id;
        uint32_t quantity;
    };
    static_assert(sizeof(TradeItem) == 0x8, "TradeItem size mismatch");

    struct TradePlayer {
        uint32_t gold;
        GW::GWArray<TradeItem> items;
    };
    static_assert(sizeof(TradePlayer) == 0x14, "TradePlayer size mismatch");

    struct TradeContext {
        static constexpr uint32_t TRADE_CLOSED = 0;
        static constexpr uint32_t TRADE_INITIATED = 1;
        static constexpr uint32_t TRADE_OFFER_SEND = 2;
        static constexpr uint32_t TRADE_ACCEPTED = 4;

        /* +h0000 */ uint32_t flags; // this is actually a flags
        /* +h0004 */ uint32_t h0004[3]; // Seemingly 3 null dwords
        /* +h0010 */ TradePlayer player;
        /* +h0024 */ TradePlayer partner;

        // bool GetPartnerAccepted();
        // bool GetPartnerOfferSent();

        bool GetIsTradeOffered() const { return (flags & TRADE_OFFER_SEND) != 0; }
        bool GetIsTradeInitiated() const { return (flags & TRADE_INITIATED) != 0; }
        bool GetIsTradeAccepted()  const { return (flags & TRADE_ACCEPTED) != 0; }
    };

    static_assert(sizeof(TradeContext) == 0x38, "TradeContext size mismatch");

}  // namespace GW::Context
