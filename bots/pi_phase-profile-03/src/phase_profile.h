#pragma once
// Research only. Default OFF: no SDK/header dependencies, state, or expressions.
#ifndef PPFX_ENABLED
#define PPFX_ENABLED 0
#endif
#if PPFX_ENABLED
#ifndef PPFX_PHASE_MASK
#define PPFX_PHASE_MASK 0x7ffu
#endif
#include <cstdint>
#include <exception>
namespace ppfx {
enum Phase : unsigned { play_turn, world_init, observe, world_refresh, shop,
    choose_camp, camp_action, fight, defend_cast, move_to, retreat, phase_count };
struct Stamp { unsigned round=0, after=0; std::uint64_t fuel=0; bool valid=false; };
// Numeric wire event: kind, scope, parent, phase, start round, end round,
// start fuel, end fuel, flags. Kinds: 0 entry, 1 exit, 2 retained cross copy.
// Flags: 1 crossed, 2 unwinding, 4 invalid clock/fuel increase, 8 cutoff-open.
struct Event { unsigned kind=0,id=0,parent=0,phase=0,start=0,end=0;
    std::uint64_t first=0,last=0; unsigned flags=0; };
struct Totals { unsigned calls=0, same=0, cross=0, invalid=0, open=0;
    std::uint64_t sum=0, maximum=0; unsigned hist[18]{}; };
template<class Clock, unsigned Capacity=512, unsigned CrossCapacity=128>
struct Profiler {
    static_assert(Capacity>0 && CrossCapacity>0);
    Event queue[Capacity]{}, crosses[CrossCapacity]{};
    Totals totals[phase_count]{};
    unsigned head=0,size=0,cross_size=0,dropped=0,cross_dropped=0;
    unsigned next=0,parent=0,clock_errors=0; bool closed=false;
    unsigned summary_index=0,cross_index=0; bool final_sent=false;
    void push(Event e) noexcept {
        if(size==Capacity){++dropped;return;}
        queue[(head+size)%Capacity]=e;++size;
    }
    bool pop(Event& e) noexcept {
        if(!size)return false;
        e=queue[head];head=(head+1)%Capacity;--size;return true;
    }
    struct Scope {
        Profiler& p; Stamp start{}; unsigned id=0,prior=0,phase=0; int exceptions=0;
        Scope(Profiler& owner,unsigned tag) noexcept : p(owner),phase(tag) {
            if(p.closed || !(PPFX_PHASE_MASK & (1u<<tag)))return;
            start=Clock::sample();
            if(!start.valid){++p.clock_errors;return;}
            if(start.round>100){p.closed=true;return;}
            // Draft is excluded by dispatch; gameplay rounds 0..100 are accepted.
            id=++p.next;prior=p.parent;p.parent=id;exceptions=std::uncaught_exceptions();
            ++p.totals[phase].calls;++p.totals[phase].open;
            p.push({0,id,prior,phase,start.round,start.after,start.fuel,start.fuel,0});
        }
        Scope(const Scope&)=delete;Scope& operator=(const Scope&)=delete;
        ~Scope() noexcept {
            if(!id)return;
            Stamp end=Clock::sample();p.parent=prior;
            auto& t=p.totals[phase];--t.open;
            unsigned flags=std::uncaught_exceptions()>exceptions?2u:0u;
            bool cross=start.round!=start.after || end.round!=end.after || start.round!=end.round;
            if(!end.valid){flags|=4;++p.clock_errors;++t.invalid;}
            else if(cross){flags|=1;++t.cross;}
            else if(end.fuel>start.fuel){flags|=4;++t.invalid;}
            else {
                auto cost=start.fuel-end.fuel;++t.same;t.sum+=cost;
                if(cost>t.maximum)t.maximum=cost;
                unsigned bin=0;auto v=cost;while(v>1 && bin<17){v>>=1;++bin;}
                ++t.hist[bin];
            }
            if(end.valid && end.after>100){p.closed=true;flags|=8;}
            Event e{1,id,prior,phase,start.round,end.after,start.fuel,end.fuel,flags};p.push(e);
            if(flags&1){e.kind=2;if(p.cross_size<CrossCapacity)p.crosses[p.cross_size++]=e;else ++p.cross_dropped;}
        }
    };
};
}
#ifndef PPFX_TEST
#include <cambc.h>
#include <cstdio>
namespace ppfx {
struct SDKClock {
    static Stamp sample() noexcept {
        try { auto r=cambc::round_number();auto f=cambc::fuel_remaining();
            auto after=cambc::round_number();return {r,after,f,true}; }
        catch(...) { return {}; }
    }
};
inline Profiler<SDKClock> profiler;
inline void emit(unsigned actor_id,const Event& e) noexcept {
    std::printf("PPFX %u [%u,%u,%u,%u,%u,%u,%llu,%llu,%u]\n",actor_id,e.kind,e.id,e.parent,e.phase,e.start,e.end,
        (unsigned long long)e.first,(unsigned long long)e.last,e.flags);
}
// Existing main-loop boundary only. At most 8 records per dispatch, each admitted
// separately at >=40k fuel, only after round 100. Never wraps an action.
inline void safe_point() noexcept {
    if(!profiler.next || profiler.final_sent)return;
    // Reuse the exception-safe clock; no actor/formatting/output during collection.
    const auto window=SDKClock::sample();
    if(!window.valid || window.after<=100)return;
    profiler.closed=true;
    const auto actor_id=static_cast<unsigned>(static_cast<cambc::handle_champion_t>(cambc::self()));
    for(unsigned n=0;n<8;++n) {
        auto now=SDKClock::sample();if(!now.valid || now.fuel<40000)return;
        if(now.after>100)profiler.closed=true;
        Event e;
        if(profiler.pop(e)){emit(actor_id,e);continue;}
        if(!profiler.closed)return;
        if(profiler.cross_index<profiler.cross_size){emit(actor_id,profiler.crosses[profiler.cross_index++]);continue;}
        if(profiler.summary_index<phase_count) {
            unsigned i=profiler.summary_index++;const auto& t=profiler.totals[i];
            std::printf("PPFX %u [3,%u,%u,%u,%u,%u,%u,%llu,%llu",actor_id,i,t.calls,t.same,t.cross,t.invalid,t.open,
                (unsigned long long)t.sum,(unsigned long long)t.maximum);
            for(auto h:t.hist)std::printf(",%u",h);
            std::printf("]\n");continue;
        }
        std::printf("PPFX %u [4,%u,%u,%u,%u,%u]\n",actor_id,profiler.next,profiler.dropped,profiler.cross_dropped,profiler.clock_errors,profiler.parent);
        profiler.final_sent=true;return;
    }
}
}
#define PPFX_SCOPE(phase) ::ppfx::Profiler<::ppfx::SDKClock>::Scope ppfx_scope(::ppfx::profiler,::ppfx::phase);
#define PPFX_SAFE_POINT() ::ppfx::safe_point();
#endif
#else
#define PPFX_SCOPE(phase)
#define PPFX_SAFE_POINT()
#endif
