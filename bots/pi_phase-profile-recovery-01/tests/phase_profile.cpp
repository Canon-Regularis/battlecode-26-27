#include "phase_profile.h"
#include <cassert>
#include <stdexcept>
#include <string>
#include <vector>
using namespace lp::ppfx;
namespace fake {
int r=1,tag_calls=0,round_calls=0,fuel_calls=0;
std::int64_t f=100000;
bool round_throw=false,fuel_throw=false,tag_throw=false,emit_throw=false;
std::vector<int> rounds;unsigned next=0;
std::vector<std::string> lines;
void reset(){store=Store{};r=1;f=100000;tag_calls=round_calls=fuel_calls=0;rounds.clear();next=0;lines.clear();round_throw=fuel_throw=tag_throw=emit_throw=false;}
}
namespace lp::ppfx {
int round(){++fake::round_calls;if(fake::round_throw)throw std::runtime_error("clock");if(fake::next<fake::rounds.size())return fake::rounds[fake::next++];return fake::r;}
std::int64_t fuel(){++fake::fuel_calls;if(fake::fuel_throw)throw std::runtime_error("fuel");return fake::f;}
int actor(){++fake::tag_calls;if(fake::tag_throw)throw std::runtime_error("tag");return 73;}
void output(const char* line){if(fake::emit_throw)throw std::runtime_error("emit");fake::lines.emplace_back(line);}
}
void early(){Scope s(1);fake::f-=300;return;}
int main(){
    fake::reset();
    {Scope outer(0);fake::f-=100;{Scope inner(2);fake::f-=200;}fake::f-=50;}
    assert(store.scopes[0].cost.sum==350&&store.scopes[2].cost.sum==200);
    assert(store.scopes[0].entries==1&&store.scopes[0].completed==1&&store.active==0);
    assert(store.entry_fuel.n==1&&store.entry_fuel.sum==100000);
    Metric buckets;for(U v:{0ull,1000ull,4000ull,16000ull,40000ull,100000ull,250000ull,1000000ull})buckets.add(v);
    for(auto count:buckets.hist)assert(count==1);
    early();assert(store.scopes[1].exit[returned]==1&&store.scopes[1].cost.min==300);
    try {Scope s(5);throw std::runtime_error("underlying");}catch(const std::runtime_error& e){assert(std::string(e.what())=="underlying");}
    assert(store.scopes[5].exit[other]==1);
    for(Exit e:{halt,sdk,other}){Scope s(6);s.close(e);} // explicit catch interface used by production
    assert(store.scopes[6].exit[halt]==1&&store.scopes[6].exit[sdk]==1);
    fake::reset();
    {Scope s(0);fake::r=7;fake::f=900000;}
    assert(store.scopes[0].crossed==1&&store.scopes[0].cost.n==0);
    assert(store.used==1&&store.examples[0].begin.r==1&&store.examples[0].end.r==7);
    fake::reset();
    {Scope s(0);fake::r=0;}assert(store.scopes[0].invalid==1);
    fake::reset();{Scope s(0);++fake::f;}assert(store.scopes[0].invalid==1);
    fake::reset();fake::rounds={1,2,2,2};{Scope s(0);}assert(store.scopes[0].invalid==1);
    fake::reset();fake::rounds={1,1,1,2};{Scope s(0);}assert(store.scopes[0].invalid==1&&store.sample_invalid==1);
    fake::reset();fake::f=-1;{Scope s(0);}assert(store.scopes[0].invalid==1);
    fake::reset();
    try {Scope s(0);fake::fuel_throw=true;throw 42;}catch(int v){assert(v==42);}
    assert(store.scopes[0].invalid==1&&store.scopes[0].exit[other]==1&&store.active==0);
    fake::reset();fake::round_throw=true;{Scope s(0);}assert(store.active==0&&store.sample_invalid==1);
    fake::reset();
    for(int i=0;i<example_limit+5;++i){fake::r=1;Scope s(4);fake::r=5;}
    assert(store.used==example_limit&&store.dropped==5&&store.scopes[4].crossed==21);
    store.context[cells].sum=std::numeric_limits<U>::max();add(cells,1);assert(store.overflow==1);
    fake::reset();
    for(fake::r=1;fake::r<=100;++fake::r)drain();
    assert(fake::tag_calls==0&&fake::lines.empty());
    fake::r=100;
    {Scope s(8);fake::r=104;drain();assert(fake::lines.empty()&&fake::tag_calls==0);}
    assert(store.scopes[8].crossed==1&&store.scopes[8].completed==1);
    fake::f=39999;drain();assert(fake::lines.empty()&&fake::tag_calls==0);
    fake::f=40000;drain();assert(fake::lines.size()==2&&fake::tag_calls==1);
    {Scope s(0);assert(!s.admitted);} // admission closed; previous crossing remains
    for(int i=0;i<100;++i){auto before=fake::lines.size();drain();assert(fake::lines.size()-before<=2);}
    assert(store.done&&store.active==0&&fake::tag_calls==1);
    int trailers=0;for(auto& line:fake::lines){assert(line.find("actor=73 source=ase01-d378591a profile=1")!=std::string::npos);assert(line.find("window=1..100")!=std::string::npos);trailers+=line.find("phase=complete ")!=std::string::npos;}
    assert(trailers==1);auto size=fake::lines.size();drain();assert(fake::lines.size()==size);
    fake::reset();fake::r=101;fake::tag_throw=true;drain();assert(fake::lines.empty()&&!store.done&&store.output_failures==1);
    fake::tag_throw=false;fake::emit_throw=true;drain();assert(store.cursor==2&&store.output_failures==3);
    fake::emit_throw=false;for(int i=0;i<100;++i)drain();assert(store.done);
    fake::reset();fake::r=101;{Scope s(0);assert(!s.admitted);}fake::r=99;{Scope s(0);assert(!s.admitted);}
    // Mask hooks execute real scope constructors only when their bit is enabled.
    fake::reset();
    {PPFX_0(Scope s0(0);) PPFX_1(Scope s1(1);) PPFX_2(Scope s2(2);)
     PPFX_3(Scope s3(3);) PPFX_4(Scope s4(4);) PPFX_5(Scope s5(5);)
     PPFX_6(Scope s6(6);) PPFX_7(Scope s7(7);) PPFX_8(Scope s8(8);)}
    for(int i=0;i<9;++i)assert(store.scopes[i].entries==bool(PPFX_PHASE_MASK&(1u<<i)));
    std::puts("PASS: profiler scripted clock, inclusive/crossed/invalid/exception/storage/drain/mask interface");
}
