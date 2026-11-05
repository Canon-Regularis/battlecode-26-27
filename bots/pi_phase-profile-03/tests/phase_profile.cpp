#define PPFX_TEST
#include "phase_profile.h"
#include <cassert>
#include <stdexcept>
#if PPFX_ENABLED && defined(PPFX_MASK_TEST)
struct Clock {
    static inline unsigned calls=0;
    static ppfx::Stamp sample() noexcept {++calls;return {1,1,100,true};}
};
int main() {
    ppfx::Profiler<Clock> p;
    {decltype(p)::Scope s(p,ppfx::observe);}
    assert(Clock::calls==0 && p.next==0);
    {decltype(p)::Scope s(p,ppfx::play_turn);}
    assert(Clock::calls==2 && p.next==1);
}
#elif PPFX_ENABLED
struct FakeClock {
    static inline ppfx::Stamp now{1,1,100,true};
    static ppfx::Stamp sample() noexcept {return now;}
};
using P=ppfx::Profiler<FakeClock,4,1>;
int main() {
    P p;
    {
        P::Scope outer(p,ppfx::play_turn);
        FakeClock::now.fuel=90;
        {P::Scope inner(p,ppfx::observe);FakeClock::now.fuel=70;}
        assert(p.parent==1);
        FakeClock::now.fuel=60;
    }
    assert(p.parent==0 && p.size==4 && p.totals[0].sum==40);
    assert(p.totals[2].sum==20 && p.totals[2].hist[4]==1);
    ppfx::Event e;p.pop(e);assert(e.kind==0 && e.id==1 && e.parent==0);
    p.pop(e);assert(e.id==2 && e.parent==1);
    while(p.pop(e)){}
    try {P::Scope s(p,ppfx::fight);throw std::runtime_error("test");}catch(...){}
    p.pop(e);p.pop(e);assert(e.flags==2 && p.parent==0);
    {P::Scope s(p,ppfx::retreat);FakeClock::now={2,2,200,true};}
    assert(p.totals[10].cross==1 && p.totals[10].same==0 && p.cross_size==1);
    {P::Scope s(p,ppfx::retreat);FakeClock::now={3,3,300,true};}
    assert(p.cross_dropped==1);
    {P::Scope s(p,ppfx::fight);FakeClock::now.fuel=301;}
    assert(p.totals[7].invalid==1);
    assert(p.size==4 && p.dropped==2);
    FakeClock::now={100,100,100,true};
    {P::Scope s(p,ppfx::play_turn);FakeClock::now={101,101,100,true};}
    assert(p.closed && p.totals[0].cross==1);
    auto calls=p.next;{P::Scope s(p,ppfx::play_turn);}assert(p.next==calls);
    P q;FakeClock::now={101,101,100,true};{P::Scope s(q,ppfx::play_turn);}assert(q.closed && q.next==0);
    P unstable;FakeClock::now={9,10,100,true};
    {P::Scope s(unstable,ppfx::observe);FakeClock::now={10,10,90,true};}
    assert(unstable.totals[2].cross==1 && unstable.totals[2].same==0);
    P invalid;FakeClock::now.valid=false;{P::Scope s(invalid,ppfx::observe);}
    assert(invalid.clock_errors==1 && invalid.next==0);
    P open;FakeClock::now={1,1,100,true};
    {P::Scope s(open,ppfx::observe);assert(open.totals[2].open==1);}
    assert(open.totals[2].open==0);
}
#else
int main() {
    // Undefined tokens must disappear without evaluating/instantiating anything.
    PPFX_SCOPE(undefined_phase);
    PPFX_SAFE_POINT();
}
#endif
