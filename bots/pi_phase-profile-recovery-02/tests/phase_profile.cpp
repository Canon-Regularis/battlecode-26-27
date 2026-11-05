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
std::vector<std::int64_t> fuels;unsigned next_fuel=0;
std::vector<std::string> lines;
void reset(){store=Store{};r=1;f=100000;tag_calls=round_calls=fuel_calls=0;rounds.clear();next=0;fuels.clear();next_fuel=0;lines.clear();round_throw=fuel_throw=tag_throw=emit_throw=false;}
}
namespace lp::ppfx {
int round(){++fake::round_calls;if(fake::round_throw)throw std::runtime_error("clock");if(fake::next<fake::rounds.size())return fake::rounds[fake::next++];return fake::r;}
std::int64_t fuel(){++fake::fuel_calls;if(fake::fuel_throw)throw std::runtime_error("fuel");if(fake::next_fuel<fake::fuels.size())return fake::fuels[fake::next_fuel++];return fake::f;}
int actor(){++fake::tag_calls;if(fake::tag_throw)throw std::runtime_error("tag");return 73;}
void output(const char* line){if(fake::emit_throw)throw std::runtime_error("emit");fake::lines.emplace_back(line);}
}
void early(){Scope s(1);fake::f-=300;return;}

// Parse the actual drain output; expectations never read back stored examples.
void emitted_crossings(int count){
    fake::reset();
    struct Expected {int phase,start,end;long long begin_fuel,end_fuel;};
    std::vector<Expected> expected;
    for(int i=0;i<count;++i){
        Expected e{i%phases,1+3*i,2+3*i,900000+101*i,700000+211*i};
        fake::r=e.start;fake::f=e.begin_fuel;
        {Scope scope(e.phase);fake::r=e.end;fake::f=e.end_fuel;}
        if(i<example_limit)expected.push_back(e);
    }
    assert(store.used==expected.size());
    assert(store.dropped==U(count-int(expected.size())));
    fake::r=101;fake::f=40000;
    for(int calls=0;!store.done;++calls){
        assert(calls<100);
        auto before=fake::lines.size();drain();
        assert(fake::lines.size()>before&&fake::lines.size()-before<=2);
    }
    assert(fake::tag_calls==1);
    const std::string scope_names[]={"recovery","prepare","capture","self_geometry","members","plan","defense","issue","play_turn"};
    const std::string contexts[]={"member_cold","member_warm","terrain_cold","terrain_warm","cells","static_members",
        "visible_camps","mapped_camps","relevant_known","relevant_alive","relevant_awake","enemies","guarded_wrapper_queries",
        "plan_raw","plan_risk","plan_unknown","plan_actions","recovery_status","moves","dashes","recalls","captures",
        "cancellations","defenses","prepare_status","capture_status","halt_status","recovery_entry_fuel"};
    char prefix[160];std::snprintf(prefix,sizeof prefix,
        "PPFX actor=73 source=ase01-d378591a profile=1 mask=%x window=1..100 ",unsigned(PPFX_PHASE_MASK));
    std::vector<std::string> bodies;
    int trailers=0;
    for(const auto& line:fake::lines){
        assert(line.rfind(prefix,0)==0&&line.back()=='\n'&&line.find('\n')==line.size()-1);
        bodies.push_back(line.substr(std::string(prefix).size()));
        trailers+=bodies.back().rfind("phase=complete ",0)==0;
    }
    // 9 scopes, 28 contexts (entry fuel last), 4 statuses, crossings, trailer.
    assert(bodies.size()==42+expected.size()&&trailers==1);
    unsigned pos=0;
    for(const auto& name:scope_names)assert(bodies[pos++].rfind("phase="+name+" entries=",0)==0);
    for(const auto& name:contexts)assert(bodies[pos++].rfind("phase=context key="+name+" {",0)==0);
    for(int row=0;row<4;++row)assert(bodies[pos++].rfind("phase=status row="+std::to_string(row)+" bins=",0)==0);
    assert(pos==41);
    for(const auto& e:expected){
        char scope[32]{};int start=0,end=0,consumed=0;long long begin_fuel=0,end_fuel=0;
        const auto& body=bodies[pos++];
        assert(std::sscanf(body.c_str(),"phase=cross scope=%31s start=%d/%lld end=%d/%lld%n",
            scope,&start,&begin_fuel,&end,&end_fuel,&consumed)==5);
        assert(body.substr(consumed)=="\n");
        assert(scope==scope_names[e.phase]&&start==e.start&&end==e.end&&begin_fuel==e.begin_fuel&&end_fuel==e.end_fuel);
    }
    assert(bodies[pos++]=="phase=complete dropped_cross="+std::to_string(count-int(expected.size()))+
        " overflow=0 output_failures=0 active=0 sample_invalid=0\n");
    assert(pos==bodies.size());
    auto size=fake::lines.size();int tags=fake::tag_calls,rounds=fake::round_calls,fuels=fake::fuel_calls;
    for(int i=0;i<5;++i)drain();
    assert(fake::lines.size()==size&&fake::tag_calls==tags&&fake::round_calls==rounds&&fake::fuel_calls==fuels);
}
void per_record_guards(){
    // Exhaust fuel or re-enter collection window between the two output slots.
    for(bool low_fuel:{false,true}){
        fake::reset();fake::r=101;
        if(low_fuel)fake::fuels={40000,39999};else fake::rounds={101,101,100,100};
        drain();assert(fake::lines.size()==1&&store.cursor==1&&fake::tag_calls==1);
        fake::r=100;drain();assert(fake::lines.size()==1&&fake::tag_calls==1);
        fake::r=101;fake::f=39999;drain();assert(fake::lines.size()==1&&fake::tag_calls==1);
        fake::f=40000;drain();assert(fake::lines.size()==3&&fake::tag_calls==1);
    }
}

int main(){
    for(int count:{0,1,16,21})emitted_crossings(count);
    per_record_guards();
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
