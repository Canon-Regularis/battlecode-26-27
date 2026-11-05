#pragma once
#ifndef PPFX_ENABLED
#define PPFX_ENABLED 0
#endif
#ifndef PPFX_PHASE_MASK
#define PPFX_PHASE_MASK 0x7ffu
#endif

#if PPFX_ENABLED
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
namespace lp::ppfx {
// Actor-local WASM instance storage; never contains SDK handles.
int round();
std::int64_t fuel();
int actor();
void output(const char*);
constexpr int phases=9, example_limit=16;
using U=std::uint64_t;
inline void overflowed() noexcept;
struct Metric {
    U n=0,sum=0,min=std::numeric_limits<U>::max(),max=0,hist[8]{};
    void add(U v) noexcept {
        if(n==std::numeric_limits<U>::max())overflowed();else ++n;
        if(v>std::numeric_limits<U>::max()-sum){sum=std::numeric_limits<U>::max();overflowed();}else sum+=v;if(v<min)min=v;if(v>max)max=v;
        unsigned b=0;constexpr U edges[]={1000,4000,16000,40000,100000,250000,1000000};
        while(b<7&&v>=edges[b])++b;
        ++hist[b];
    }
};
inline void invalid_sample() noexcept;
struct Sample {int r=0;std::int64_t f=0;bool valid=false;};
inline Sample sample() noexcept {
    Sample s;
    // One bounded round/fuel/round attempt. Retrying would amplify observer cost.
    try {s.r=round();s.f=fuel();s.valid=round()==s.r&&s.r>=1&&s.f>=0;}
    catch(...) {s.valid=false;}
    if(!s.valid)invalid_sample();
    return s;
}
enum Exit {returned,halt,sdk,other};
struct Summary {
    U entries=0,completed=0,invalid=0,crossed=0,exit[4]{},halt_status[12]{};
    Metric cost;
};
enum Context {member_cold,member_warm,terrain_cold,terrain_warm,cells,static_members,
    visible_camps,mapped_camps,known,alive,awake,enemies,queries,plan_raw,plan_risk,
    plan_unknown,plan_actions,result,moves,dashes,recalls,captures,cancellations,defenses,
    prepare_status,capture_status,halt_status,context_count};
inline constexpr const char* context_names[]={"member_cold","member_warm","terrain_cold","terrain_warm",
    "cells","static_members","visible_camps","mapped_camps","relevant_known","relevant_alive","relevant_awake",
    "enemies","guarded_wrapper_queries","plan_raw","plan_risk","plan_unknown","plan_actions","recovery_status",
    "moves","dashes","recalls","captures","cancellations","defenses","prepare_status","capture_status","halt_status"};
struct Example {int phase;Sample begin,end;};
struct Store {
    Summary scopes[phases]{};Metric context[context_count]{},entry_fuel;
    // Status values have dedicated distributions as well as numeric context summaries.
    U statuses[4][12]{};
    Example examples[example_limit]{};unsigned used=0;
    U dropped=0,overflow=0,active=0,output_failures=0,sample_invalid=0;
    unsigned cursor=0;bool closed=false,done=false,tagged=false,recovery_admitted=false;int tag=0;
};
inline Store store;
inline void overflowed() noexcept {++store.overflow;}
inline void invalid_sample() noexcept {++store.sample_invalid;}
struct RecoveryAdmission {
    bool previous;
    explicit RecoveryAdmission(bool admitted) noexcept:previous(store.recovery_admitted){store.recovery_admitted=admitted;}
    ~RecoveryAdmission() noexcept {store.recovery_admitted=previous;}
};
inline void add(Context c,U v) noexcept {store.context[c].add(v);}
inline void status(Context c,int v) noexcept {
    add(c,U(v));int row=c==prepare_status?0:c==capture_status?1:c==halt_status?2:3;
    if(v>=0&&v<12)++store.statuses[row][v];else ++store.overflow;
}
struct Scope {
    int phase;Sample begin;bool admitted=false,finished=false;Exit reason=returned;int exceptions;
    explicit Scope(int p) noexcept:phase(p),exceptions(std::uncaught_exceptions()) {
        if(store.closed)return;
        begin=sample();
        if(begin.r>100){store.closed=true;return;}
        if(begin.r<1)return;
        admitted=true;++store.active;++store.scopes[p].entries;
        if(p==0&&begin.valid)store.entry_fuel.add(U(begin.f));
    }
    Scope(const Scope&)=delete;
    void close(Exit why=returned,int detail=-1) noexcept {
        if(!admitted||finished)return;
        finished=true;auto end=sample();auto& s=store.scopes[phase];
        ++s.completed;++s.exit[why];--store.active;
        if(why==halt&&detail>=0&&detail<12)++s.halt_status[detail];
        if(!begin.valid||!end.valid||end.r<begin.r||(end.r==begin.r&&end.f>begin.f))++s.invalid;
        else if(end.r==begin.r)s.cost.add(U(begin.f-end.f));
        else {
            ++s.crossed;
            if(store.used<example_limit)store.examples[store.used++]={phase,begin,end};
            else ++store.dropped;
        }
    }
    ~Scope() noexcept {close(std::uncaught_exceptions()>exceptions?other:reason);}
    template<class T> T ret(T value) noexcept {
        if(admitted) {
            if(phase==1)status(prepare_status,int(value));
            if(phase==2)status(capture_status,int(value));
        }
        return value;
    }
};
// Holds references only to existing scalar locals, never SDK handles. Destruction
// is before their lifetimes end, including on exception/early return.
struct QueryCount {Scope& scope;int& value;~QueryCount() noexcept {if(scope.admitted)add(queries,U(value));}};
inline constexpr const char* names[]={"recovery","prepare","capture","self_geometry","members","plan","defense","issue","play_turn"};
inline void metric(char* b,std::size_t n,const Metric& m) noexcept {
    std::snprintf(b,n,"n=%llu,sum=%llu,min=%llu,max=%llu,h=%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu",
        (unsigned long long)m.n,(unsigned long long)m.sum,(unsigned long long)(m.n?m.min:0),(unsigned long long)m.max,
        (unsigned long long)m.hist[0],(unsigned long long)m.hist[1],(unsigned long long)m.hist[2],(unsigned long long)m.hist[3],
        (unsigned long long)m.hist[4],(unsigned long long)m.hist[5],(unsigned long long)m.hist[6],(unsigned long long)m.hist[7]);
}
inline void drain() noexcept {
    if(store.done)return;
    try {
        for(int records=0;records<2;++records) {
            // Check before actor lookup, formatting, and each individual output.
            auto now=sample();
            if(!now.valid||now.r<=100||now.f<40000||store.active)return;
            store.closed=true;
            if(!store.tagged){store.tag=actor();store.tagged=true;}
            char body[1024]{},m[384]{},line[1280]{};unsigned i=store.cursor;
            if(i<phases) {
                auto& s=store.scopes[i];metric(m,sizeof m,s.cost);
                std::snprintf(body,sizeof body,"phase=%s entries=%llu completed=%llu returned=%llu halt=%llu sdk=%llu other=%llu invalid=%llu crossed=%llu inclusive={%s} halt_bins=%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu",
                    names[i],(unsigned long long)s.entries,(unsigned long long)s.completed,(unsigned long long)s.exit[0],
                    (unsigned long long)s.exit[1],(unsigned long long)s.exit[2],(unsigned long long)s.exit[3],
                    (unsigned long long)s.invalid,(unsigned long long)s.crossed,m,
                    (unsigned long long)s.halt_status[0],(unsigned long long)s.halt_status[1],(unsigned long long)s.halt_status[2],
                    (unsigned long long)s.halt_status[3],(unsigned long long)s.halt_status[4],(unsigned long long)s.halt_status[5],
                    (unsigned long long)s.halt_status[6],(unsigned long long)s.halt_status[7],(unsigned long long)s.halt_status[8],
                    (unsigned long long)s.halt_status[9],(unsigned long long)s.halt_status[10],(unsigned long long)s.halt_status[11]);
            } else if(i<phases+context_count+1) {
                unsigned c=i-phases;metric(m,sizeof m,c==context_count?store.entry_fuel:store.context[c]);
                std::snprintf(body,sizeof body,"phase=context key=%s {%s}",c==context_count?"recovery_entry_fuel":context_names[c],m);
            } else if(i<phases+context_count+5) {
                unsigned row=i-phases-context_count-1;auto* s=store.statuses[row];
                std::snprintf(body,sizeof body,"phase=status row=%u bins=%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu/%llu",row,
                    (unsigned long long)s[0],(unsigned long long)s[1],(unsigned long long)s[2],(unsigned long long)s[3],
                    (unsigned long long)s[4],(unsigned long long)s[5],(unsigned long long)s[6],(unsigned long long)s[7],
                    (unsigned long long)s[8],(unsigned long long)s[9],(unsigned long long)s[10],(unsigned long long)s[11]);
            } else if(i<phases+context_count+5+store.used) {
                auto& e=store.examples[i-phases-context_count-5];
                std::snprintf(body,sizeof body,"phase=cross scope=%s start=%d/%lld end=%d/%lld",names[e.phase],e.begin.r,(long long)e.begin.f,e.end.r,(long long)e.end.f);
            } else {
                std::snprintf(body,sizeof body,"phase=complete dropped_cross=%llu overflow=%llu output_failures=%llu active=%llu sample_invalid=%llu",
                    (unsigned long long)store.dropped,(unsigned long long)store.overflow,(unsigned long long)store.output_failures,(unsigned long long)store.active,(unsigned long long)store.sample_invalid);
                store.done=true;
            }
            std::snprintf(line,sizeof line,"PPFX actor=%d source=ase01-d378591a profile=1 mask=%x window=1..100 %s\n",store.tag,unsigned(PPFX_PHASE_MASK),body);
            ++store.cursor; // A failed output is lost, never retried/duplicated.
            try {output(line);}catch(...){++store.output_failures;}
            if(store.done)return;
        }
    } catch(...) {++store.output_failures;}
}
}
#define PPFX(...) __VA_ARGS__
#else
#define PPFX(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 0))
#define PPFX_0(...) __VA_ARGS__
#else
#define PPFX_0(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 1))
#define PPFX_1(...) __VA_ARGS__
#else
#define PPFX_1(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 2))
#define PPFX_2(...) __VA_ARGS__
#else
#define PPFX_2(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 3))
#define PPFX_3(...) __VA_ARGS__
#else
#define PPFX_3(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 4))
#define PPFX_4(...) __VA_ARGS__
#else
#define PPFX_4(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 5))
#define PPFX_5(...) __VA_ARGS__
#else
#define PPFX_5(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 6))
#define PPFX_6(...) __VA_ARGS__
#else
#define PPFX_6(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 7))
#define PPFX_7(...) __VA_ARGS__
#else
#define PPFX_7(...)
#endif

#if PPFX_ENABLED && (PPFX_PHASE_MASK & (1u << 8))
#define PPFX_8(...) __VA_ARGS__
#else
#define PPFX_8(...)
#endif
#if PPFX_ENABLED && (PPFX_PHASE_MASK & 0x1cu)
#define PPFX_CAPTURE(...) __VA_ARGS__
#else
#define PPFX_CAPTURE(...)
#endif
#if PPFX_ENABLED && (PPFX_PHASE_MASK & 2u)
#define PPFX_STATUS_1(value) pp.ret(value)
#else
#define PPFX_STATUS_1(value) value
#endif
#if PPFX_ENABLED && (PPFX_PHASE_MASK & 4u)
#define PPFX_STATUS_2(value) pp.ret(value)
#else
#define PPFX_STATUS_2(value) value
#endif
