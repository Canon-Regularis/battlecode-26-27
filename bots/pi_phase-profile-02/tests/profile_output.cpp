#include "phase_profile.h"
#include <cassert>
#include <initializer_list>
int main() {
    for(unsigned actor_id : {17u,4294967295u}) {
        ppfx::profiler={};cambc::self_calls=0;
        cambc::actor.handle=static_cast<cambc::handle_champion_t>(actor_id);
        cambc::round=1;cambc::fuel=100000;
        ppfx::safe_point();assert(cambc::self_calls==0); // no accepted scopes
        {
            ppfx::Profiler<ppfx::SDKClock>::Scope scope(ppfx::profiler,ppfx::observe);
            cambc::round=101;cambc::fuel=90000;
        }
        assert(cambc::self_calls==0); // identity is never sampled in a scope
        cambc::fuel=39999;
        ppfx::safe_point();
        assert(cambc::self_calls==1 && ppfx::profiler.size==2);
        cambc::fuel=100000;
        ppfx::safe_point();
        assert(cambc::self_calls==2 && ppfx::profiler.summary_index==5);
        assert(!ppfx::profiler.final_sent); // exactly eight records in first drain
        ppfx::safe_point();
        assert(cambc::self_calls==3 && ppfx::profiler.final_sent);
        ppfx::safe_point();assert(cambc::self_calls==3); // final-sent early return
    }
}
