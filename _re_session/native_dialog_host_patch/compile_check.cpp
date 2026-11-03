// Compile check for native_dialog_host.h (32-bit target; __thiscall requires x86).
#include "native_dialog_host.h"

int main() {
    using namespace Py4GW::Ui::DialogHost;
    static_assert(kInstanceSize == 0xD4);
    static_assert(kLayoutOffset == 0x08);
    (void)Ready();
    (void)FindHost(0);
    (void)ReserveHost(1);
    (void)InstanceFrom(nullptr);
    return 0;
}
