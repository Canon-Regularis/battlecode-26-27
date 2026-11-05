#include "phase_profile.h"
#include <cassert>
#include <initializer_list>
int main() {
    for(unsigned actor_id : {17u,4294967295u}) {
        ppfx::profiler={};cambc::self_calls=0;
        cambc::round_calls=0;cambc::fuel_calls=0;cambc::fuel_step=0;
        cambc::actor.handle=static_cast<cambc::handle_champion_t>(actor_id);
        cambc::round=1;cambc::fuel=100000;
        ppfx::safe_point();assert(cambc::self_calls==0); // no accepted scopes
        assert(cambc::round_calls==0 && cambc::fuel_calls==0);
        {
            ppfx::Profiler<ppfx::SDKClock>::Scope scope(ppfx::profiler,ppfx::observe);
            for(unsigned round : {0u,1u,99u,100u}) {
                cambc::round=round;
                auto samples=cambc::fuel_calls;
                ppfx::safe_point();
                assert(cambc::fuel_calls==samples+1); // one existing clock sample
                assert(cambc::round_calls==2*cambc::fuel_calls);
                assert(cambc::self_calls==0 && ppfx::profiler.size==1);
                assert(!ppfx::profiler.closed && ppfx::profiler.head==0);
                assert(ppfx::profiler.summary_index==0 && ppfx::profiler.cross_index==0);
            }
            // The runner requires this marker before any production output.
            std::printf("WINDOW_END %u\n",actor_id);
            cambc::round=101;cambc::fuel=90000;
        }
        assert(cambc::self_calls==0); // identity is never sampled in a scope
        cambc::fuel=39999;
        ppfx::safe_point();
        assert(cambc::self_calls==1 && ppfx::profiler.size==2);
        // Verify safe_point itself closes admission even without a crossed exit.
        ppfx::profiler.closed=false;
        cambc::fuel=40001;cambc::fuel_step=1;
        ppfx::safe_point();
        assert(cambc::self_calls==2 && ppfx::profiler.closed);
        assert(ppfx::profiler.size==1 && ppfx::profiler.head==1);
        assert(ppfx::profiler.summary_index==0); // 40000 emits; 39999 stops
        cambc::fuel_step=0;
        cambc::fuel=100000;
        ppfx::safe_point();
        assert(cambc::self_calls==3 && ppfx::profiler.summary_index==6);
        assert(!ppfx::profiler.final_sent); // exactly eight records in this drain
        ppfx::safe_point();
        assert(cambc::self_calls==4 && ppfx::profiler.final_sent);
        auto samples=cambc::fuel_calls;
        ppfx::safe_point();assert(cambc::self_calls==4); // final-sent early return
        assert(cambc::fuel_calls==samples);
    }
}
