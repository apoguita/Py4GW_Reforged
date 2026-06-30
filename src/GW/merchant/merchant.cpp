#include "base/error_handling.h"

#include "GW/merchant/merchant.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/logger.h"
#include "base/scanner.h"

#include <array>
#include <atomic>

namespace GW::merchant {

using TransactItemFn = void(__cdecl*)(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv);
using RequestQuoteFn = void(__cdecl*)(Constants::TransactionType type, uint32_t unknown, QuoteInfo give, QuoteInfo recv);

bool ResolveTransactItemFunction();
bool ResolveRequestQuoteFunction();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();
void __cdecl OnTransactItem(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv);
void __cdecl OnRequestQuote(Constants::TransactionType type, uint32_t unknown, QuoteInfo give, QuoteInfo recv);
void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam);

TransactItemFn g_transact_item_func = nullptr;
TransactItemFn g_transact_item_original = nullptr;
RequestQuoteFn g_request_quote_func = nullptr;
RequestQuoteFn g_request_quote_original = nullptr;
PY4GW::HookEntry g_ui_message_entry;
const std::array<ui::UIMessage, 2> g_ui_messages_to_hook = {
    ui::UIMessage::kSendMerchantTransactItem,
    ui::UIMessage::kSendMerchantRequestQuote
};
std::atomic<bool> g_initialized = false;

void __cdecl OnTransactItem(Constants::TransactionType type, uint32_t gold_give, TransactionInfo give, uint32_t gold_recv, TransactionInfo recv) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendMerchantTransactItem packet = { type, gold_give, give, gold_recv, recv };
    ui::SendUIMessage(ui::UIMessage::kSendMerchantTransactItem, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnRequestQuote(Constants::TransactionType type, uint32_t unknown, QuoteInfo give, QuoteInfo recv) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendMerchantRequestQuote packet = { type, unknown, give, recv };
    ui::SendUIMessage(ui::UIMessage::kSendMerchantRequestQuote, &packet);
    PY4GW::HookBase::LeaveHook();
}

void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void* lparam) {
    if (status && status->blocked) {
        return;
    }

    switch (message_id) {
    case ui::UIMessage::kSendMerchantTransactItem: {
        if (g_transact_item_original && wparam) {
            const auto* packet = static_cast<ui::packet::kSendMerchantTransactItem*>(wparam);
            g_transact_item_original(packet->type, packet->gold_give, packet->give, packet->gold_recv, packet->recv);
        }
        break;
    }
    case ui::UIMessage::kSendMerchantRequestQuote: {
        if (g_request_quote_original && wparam) {
            const auto* packet = static_cast<ui::packet::kSendMerchantRequestQuote*>(wparam);
            g_request_quote_original(packet->type, packet->unknown, packet->give, packet->recv);
        }
        break;
    }
    default:
        break;
    }
}

bool Init() {
    CrashContextScope context("startup", "merchant", "init");
    if (!ResolveTransactItemFunction() || !ResolveRequestQuoteFunction()) {
        return false;
    }

    const bool transact_item_ok = Logger::AssertHook(
        "TransactItem_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_transact_item_func),
            reinterpret_cast<void*>(&OnTransactItem),
            reinterpret_cast<void**>(&g_transact_item_original)),
        "merchant");
    const bool request_quote_ok = Logger::AssertHook(
        "RequestQuote_Func",
        PY4GW::HookBase::CreateHook(
            reinterpret_cast<void**>(&g_request_quote_func),
            reinterpret_cast<void*>(&OnRequestQuote),
            reinterpret_cast<void**>(&g_request_quote_original)),
        "merchant");
    return transact_item_ok && request_quote_ok;
}

void EnableHooks() {
    CrashContextScope context("runtime", "merchant", "enable_hooks");
    if (g_transact_item_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_transact_item_func));
    }
    if (g_request_quote_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_request_quote_func));
    }
    for (const auto ui_message : g_ui_messages_to_hook) {
        ui::RegisterUIMessageCallback(&g_ui_message_entry, ui_message, &OnUIMessage, 0x1);
    }
}

void DisableHooks() {
    CrashContextScope context("shutdown", "merchant", "disable_hooks");
    if (g_transact_item_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_transact_item_func));
    }
    if (g_request_quote_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_request_quote_func));
    }
    ui::RemoveUIMessageCallback(&g_ui_message_entry);
}

void Exit() {
    CrashContextScope context("shutdown", "merchant", "exit");
    if (g_transact_item_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_transact_item_func));
    }
    if (g_request_quote_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_request_quote_func));
    }

    g_transact_item_func = nullptr;
    g_transact_item_original = nullptr;
    g_request_quote_func = nullptr;
    g_request_quote_original = nullptr;
}

bool Initialize() {
    CrashContextScope context("startup", "merchant", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());
    PY4GW::HookBase::Initialize();
    if (!Init()) {
        Exit();
        PY4GW::HookBase::Deinitialize();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "merchant", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::merchant
