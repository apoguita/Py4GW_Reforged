#pragma once

#include "GW/context/trade.h"
#include "GW/item/item.h"
#include "GW/ui/ui.h"

#include <cstdint>

namespace GW::trade {

using TradeItem = Context::TradeItem;

bool Initialize();
void Shutdown();

bool OpenTradeWindow(uint32_t agent_id);
bool AcceptTrade();
bool CancelTrade();
bool ChangeOffer();
bool SubmitOffer(uint32_t gold);
bool RemoveItem(uint32_t slot);
TradeItem* IsItemOffered(uint32_t item_id);
bool OfferItem(uint32_t item_id, uint32_t quantity = 0);

}  // namespace GW::trade

namespace GW {
namespace Trade = trade;
}
