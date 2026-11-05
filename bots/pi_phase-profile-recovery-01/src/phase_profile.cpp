#include "phase_profile.h"
#if PPFX_ENABLED
#include <cambc.h>
namespace lp::ppfx {
int round(){return int(cambc::round_number());}
std::int64_t fuel(){return std::int64_t(cambc::fuel_remaining());}
int actor(){return int(static_cast<cambc::handle_champion_t>(cambc::self()));}
void output(const char* text){std::printf("%s",text);}
}
#endif
