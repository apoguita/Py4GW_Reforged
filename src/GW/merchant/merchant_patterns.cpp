#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

#include "GW/merchant/merchant.h"

namespace GW::merchant {

using TransactItemFn = void(__cdecl*)(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv);
using RequestQuoteFn = void(__cdecl*)(Constants::TransactionType type, uint32_t unknown, QuoteInfo give, QuoteInfo recv);

extern TransactItemFn g_transact_item_func;
extern RequestQuoteFn g_request_quote_func;

bool ResolveTransactItemFunction() {
    CrashContextScope context("startup", "merchant", "resolve_transact_item");
    return PY4GW::Patterns::Resolve("merchant.transact_item_func", &g_transact_item_func);
}

bool ResolveRequestQuoteFunction() {
    CrashContextScope context("startup", "merchant", "resolve_request_quote");
    return PY4GW::Patterns::Resolve("merchant.request_quote_func", &g_request_quote_func);
}

}  // namespace GW::merchant
