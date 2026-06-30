#pragma once

#include "base/hook_types.h"
#include "GW/common/constants/constants.h"
#include "GW/context/item.h"
#include "GW/ui/ui.h"

#include <cstdint>

namespace GW::merchant {

using MerchItemArray = Context::MerchItemArray;
using TransactionInfo = Context::MerchantTransactionInfo;
using QuoteInfo = Context::MerchantQuoteInfo;

bool Initialize();
void Shutdown();

bool TransactItems(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv);
bool RequestQuote(Constants::TransactionType type, QuoteInfo give, QuoteInfo recv);

}  // namespace GW::merchant

namespace GW {
namespace Merchants = merchant;
}
