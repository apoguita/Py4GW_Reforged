#include "base/error_handling.h"

#include "GW/merchant/merchant.h"

#include "GW/context/context.h"
#include "GW/context/world.h"

namespace GW::merchant {

using TransactItemFn = void(__cdecl*)(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv);
using RequestQuoteFn = void(__cdecl*)(Constants::TransactionType type, uint32_t unknown, QuoteInfo give, QuoteInfo recv);

extern TransactItemFn g_transact_item_func;
extern RequestQuoteFn g_request_quote_func;

bool TransactItems(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv) {
    if (g_transact_item_func) {
        g_transact_item_func(type, gold_give, give, gold_recv, recv);
        return true;
    }
    return false;
}

bool RequestQuote(Constants::TransactionType type, QuoteInfo give, QuoteInfo recv) {
    if (g_request_quote_func) {
        g_request_quote_func(type, 0, give, recv);
        return true;
    }
    return false;
}

}  // namespace GW::merchant
