// Compile with -fno-access-control: test-only access to the actual private Bot::facts.
// Real SDK wrappers; controlled host responses, not an engine simulation.
#include "bot.h"
#include <cstdlib>
#include <iostream>
#include <tuple>
using namespace lp;
namespace host {
std::uint32_t gold=300, score=0;
int state=1, gold_queries=0;
}
namespace cambc::detail {
extern "C" {
std::int32_t sdk_get_settings(game_settings* p){*p={};return 0;}
std::int32_t sdk_bc_metadata(metadata* p){*p={32,32,4,4,4,128,2048};return 0;}
std::int32_t sdk_my_champion(){return 0;}
std::int32_t sdk_my_team(){return 0;}
std::int32_t sdk_shared_memory_size(std::uint32_t* p){*p=8;return 0;}
std::int32_t sdk_draft_memory_size(std::uint32_t* p){*p=0;return 0;}
std::int32_t sdk_read_draft_memory(std::int32_t,void*,std::uint32_t){std::abort();}
std::int32_t sdk_bc_map_symmetry(std::int32_t* p){*p=0;return 0;}
std::int32_t sdk_Bitboard_Zero(std::uint64_t* p){std::memset(p,0,128);return 0;}
std::int32_t sdk_bc_map_mask(std::int32_t,std::uint64_t* p){return sdk_Bitboard_Zero(p);}
std::int32_t sdk_spawn_region(std::int32_t,aabb* p){*p={};return 0;}
std::int32_t sdk_Bitboard_Set(std::uint64_t*,std::int32_t,std::int32_t,std::int32_t){std::abort();}
std::int32_t sdk_Bitboard_Test(const std::uint64_t*,std::int32_t,std::int32_t,std::int32_t*){std::abort();}
std::int32_t sdk_item_info(std::uint32_t,item_info* p){*p={};return 0;}
std::int32_t sdk_consumable_info(std::uint32_t,consumable_info* p){*p={};return 0;}
std::int32_t sdk_champion_design(std::int32_t,champion_design* p){*p={};return 0;}
std::int32_t sdk_champion_ability_props(std::uint32_t,std::uint32_t,ability_props* p){*p={};return 0;}
std::int32_t sdk_champion(std::uint32_t,champion_info* p){*p={};p->state=host::state;return 0;}
std::int32_t sdk_champion_identity(std::uint32_t,champion_identity* p){*p={};return 0;}
std::int32_t sdk_champion_gold(std::uint32_t,std::uint32_t* p){++host::gold_queries;*p=host::gold;return 0;}
std::int32_t sdk_bc_submitted_gems(std::uint32_t,std::uint32_t* p){*p=host::score;return 0;}
std::int32_t sdk_bc_get_last_error(char*,std::uint32_t){return 0;}
}
}
static int checks=0;
static void check(bool ok,const char* name){++checks;if(!ok){std::cerr<<"FAIL "<<name<<'\n';std::exit(1);}}
static auto history(const Memory& m){return std::tuple{m.bag_since,m.prior_bag,m.life,m.altar,m.bank_bag,m.bank_score,m.task,m.task_started,m.progressed,m.owned,m.queue_started,m.pending_altar,m.carrier};}
static Snapshot quiet(){Snapshot s;s.alive=true;s.hp=760;s.max_hp=1000;s.bag=14;s.round=516;s.pos={17,9};return s;}
static Facts facts(Bot& b,const Snapshot& s){
    auto before=history(b.memory);int bag=s.bag;
    auto f=b.facts(s,false);
    check(history(b.memory)==before&&s.bag==bag,"facts preserves bag/life/altar/bank/task history");return f;
}
static void expect(Bot& b,const Snapshot& s,State expected,const char* name){check(decide(facts(b,s),b.memory)==expected,name);}
int main(){
    // Full admission matrix includes bag zero as the unchanged reference behavior.
    for(int bag:{0,14,35})for(unsigned gold:{300u,299u,372u})for(bool spawn:{false,true})for(bool foe:{false,true}){
        Bot b;auto s=quiet();s.bag=bag;s.spawn=spawn;if(foe)s.foes.push_back(self());
        b.memory.bag_since=400;b.memory.prior_bag=bag;b.memory.life=3;b.memory.altar=2;b.memory.bank_bag=bag;b.memory.bank_score=17;
        host::gold=gold;host::gold_queries=0;host::state=1;host::score=0;
        auto f=facts(b,s);check(f.recovery==(!spawn&&!foe&&gold>=300),"gold recovery admission matrix");
        check(host::gold_queries==int(!spawn&&!foe),"remaining gold query short-circuit order");
        check(f.bank_needed==(bag>0),"pending altar demand remains intact");
    }
    Bot b;auto s=quiet();host::gold=372;
    expect(b,s,State::recall,"original pre-turn516 controlled trigger");
    s.bag=2;host::score=998;check(facts(b,s).bank_needed,"winning bag demand exists");
    expect(b,s,State::recall,"gold recovery precedes winning-bag banking");
    host::score=0;s.round=1999;check(facts(b,s).bank_needed,"late bag demand exists");
    expect(b,s,State::recall,"gold recovery precedes late-bag banking");
    host::gold=299;expect(b,s,State::prepare_bank,"late bag banks when gold below threshold");
    s=quiet();b.memory.bag_since=400;expect(b,s,State::prepare_bank,"aged bag still banks");
    b.memory.bag_since=-1;s.bag=Config::bank_bag;expect(b,s,State::prepare_bank,"size threshold still banks");
    s=quiet();b.memory.altar=1;expect(b,s,State::prepare_bank,"pending altar still banks");b.memory.altar=-1;
    host::gold=300;host::state=1|(1<<2);s.incoming=1000;expect(b,s,State::bank,"active tribute beats danger and recovery");
    host::state=1|(1<<12);expect(b,s,State::bank,"active teleport beats danger and recovery");
    host::state=1;s.spawn=true;expect(b,s,State::defend,"spawn defense beats danger");
    s.spawn=false;expect(b,s,State::escape,"danger beats gold recovery");
    s=quiet();host::gold=299;host::state=1|(1<<1);expect(b,s,State::recall,"quiet active recall continues");
    s.foes.push_back(self());expect(b,s,State::escape,"visible foe interrupts active recall without nearby-danger count");
    s.foes.clear();s.camp_hit=true;expect(b,s,State::escape,"camp hit interrupts active recall");
    host::state=1;host::gold=300;expect(b,s,State::escape,"camp hit beats admitted gold recovery");
    s=quiet();s.spawn=true;expect(b,s,State::healing,"spawn healing precedes banking");
    s.hp=s.max_hp;expect(b,s,State::explore,"full spawn does not gold recall");
    s=quiet();s.hp=350;s.foes.push_back(self());host::gold=0;host::gold_queries=0;
    auto f=facts(b,s);check(f.recovery&&b.memory.recovering,"health recovery works with visible enemies");
    check(!f.danger&&decide(f,b.memory)==State::escape,"health recovery alone escapes enemy vision");
    check(host::gold_queries==0,"health recovery bypasses gold query");
    s.enemies=1;s.incoming=20;expect(b,s,State::escape,"low health and nearby enemy retain danger priority");s.enemies=0;s.incoming=0;
    s.foes.clear();s.hp=500;expect(b,s,State::recall,"health hysteresis continues below high threshold");
    s.spawn=true;expect(b,s,State::healing,"spawn healing during health recovery");
    s.spawn=false;s.hp=550;check(!facts(b,s).recovery&&!b.memory.recovering,"health hysteresis clears at high threshold");
    s.alive=false;host::gold_queries=0;expect(b,s,State::dead,"dead facts exit before recovery");check(host::gold_queries==0,"dead facts avoid gold query");
    std::cout<<"PASS actual Bot::facts and decide: "<<checks<<" checks\n";
}
