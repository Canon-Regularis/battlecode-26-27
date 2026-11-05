// Only environment boundaries are scripted. run_retreat.py extracts both retreat
// bodies, incoming_at, move_checked, cheb and TurnBudget verbatim from real sources.
#include "model.h"
#include <cassert>
#include <iostream>
#include <random>
#include <stdexcept>
#include <tuple>
#include <vector>
using lp::Memory;
using lp::Config;
struct vec2 { int x=0,y=0; bool operator==(const vec2&) const = default; };
int incoming_calls=0;
int epoch=10, polls=0, enumerations=0, invalidations=0, attempts=0, safe_calls=0;
int change_on=0, fail_vision_on=0, getter_event=0;
bool movable=true, restricted=false;
vec2 destination{-1,-1};
unsigned round_number(){++polls;return epoch;}
unsigned fuel_remaining(){return 1000000;}
namespace cambc {
enum class error_code {invalid_action_move_bad_destination, other, visibility};
struct error : std::runtime_error {
    error_code value;
    explicit error(error_code v):std::runtime_error("scripted SDK failure"),value(v){}
    error_code code() const{return value;}
};
}
using cambc::error_code;
namespace buff_restrictions {constexpr int move=1;}
struct Restrictions {bool contains(int) const{return restricted;}};
enum class Move {success, rejected, bad_destination, unexpected};
Move move_result=Move::success;
struct champion {
    vec2 p;int range=1;float power=0;
    vec2 position() const{return p;}
    int attack_range() const{return range;}
    float strength() const{return power;}
    bool can_move() const{return movable;}
    Restrictions restrictions() const{return {};}
    bool move_absolute(vec2 p) const {
        ++attempts;destination=p;
        if(move_result==Move::bad_destination)throw cambc::error(error_code::invalid_action_move_bad_destination);
        if(move_result==Move::unexpected)throw cambc::error(error_code::other);
        return move_result==Move::success;
    }
};
champion me;
namespace cambc {champion& self(){return me;}}
using cambc::self;
struct camp {
    vec2 p;int range;float power;bool alive=true,awake=true;
    bool is_alive() const{return alive;}
    bool is_awake() const{return awake;}
    float strength() const{return power;}
    vec2 position() const {
        // Injection occurs in a live geometry getter, after positive strength.
        if(enumerations==change_on) {
            if(getter_event==0)epoch=11;
            if(getter_event==1)movable=false;
            if(getter_event==2)restricted=true;
        }
        return p;
    }
    int attack_range() const{return range;}
};
std::vector<camp> camps;
namespace vision {
std::vector<camp> camps(){
    ++enumerations;
    if(enumerations==fail_vision_on)throw cambc::error(error_code::visibility);
    return ::camps;
}
}
struct bitboard {
    std::vector<vec2> tiles;
    std::vector<vec2> positions() const{return tiles;}
    bitboard reachable_tiles(vec2 p,int radius) const {
        assert((p==vec2{3,3})&&radius==1);return *this;
    }
};
enum class team {ally};
bitboard spawn;
namespace map {bitboard spawn_region(team){return spawn;}}
struct Snapshot {vec2 pos{3,3};bitboard blocked;std::vector<champion> foes;};
Snapshot snapshot;
const Snapshot& observe(){return snapshot;}
void invalidate_observations(){++invalidations;}
enum class RouteStatus {at_goal,moved,wait,deferred,no_route_now,invalid_goals};
RouteStatus safe_result=RouteStatus::no_route_now;
bool stale_after_safe=false, unavailable_after_safe=false;
Memory after_safe;
// Deliberate pathfinding substitution: validate call arguments; model its Memory
// effects, but never run or rewrite its field/dash/yield implementation.
template<class Budget>
RouteStatus move_to(bitboard goals,bool safe,Budget&,Memory& mem) {
    ++safe_calls;assert(safe&&goals.tiles==spawn.tiles);
    if(safe_result==RouteStatus::no_route_now||safe_result==RouteStatus::invalid_goals)++mem.blocked;
    if(safe_result==RouteStatus::moved){mem.blocked=0;mem.last_distance=7;}
    if(stale_after_safe)epoch=11;
    if(unavailable_after_safe)movable=false;
    after_safe=mem;return safe_result;
}
#include "retreat-under-test.h"
// Compare every actual Memory member, avoiding padding-byte comparisons.
auto memory_values(const Memory& m) {
    return std::tuple{m.state,m.task,m.altar,m.task_started,m.progressed,m.protection_started,
        m.bag_since,m.prior_bag,m.life,m.bank_bag,m.bank_score,m.shop_phase,m.shop_target,
        m.blocked,m.last_created,m.rally_retry,m.carrier,m.carrier_seen,m.protection_until,
        m.guidance_seen,m.exploration,m.exploration_started,m.last_distance,m.pending_altar,
        m.queue_started,m.recovering,m.was_alive,m.owned};
}
struct Result {
    bool moved;int ranks,attempts,polls,invalidations;vec2 dest;int thrown;
    bool operator==(const Result&) const = default;
};
void reset() {
    epoch=10;incoming_calls=polls=enumerations=invalidations=attempts=safe_calls=0;
    change_on=fail_vision_on=getter_event=0;movable=true;restricted=false;
    destination={-1,-1};move_result=Move::success;
    safe_result=RouteStatus::no_route_now;stale_after_safe=unavailable_after_safe=false;
    spawn.tiles={{0,0}};snapshot={};camps.clear();
}
void two_improvements() {
    reset();camps={{{4,3},1,20},{{3,4},1,60}};
    // Walls occupy other neighboring tiles; camps occupy (4,3),(3,4).
    // Both specified candidates are adjacent and unoccupied, as is origin.
    snapshot.blocked.tiles={{3,3},{2,3},{2,2}};
}
Result run(bool original) {
    epoch=10;incoming_calls=polls=enumerations=invalidations=attempts=safe_calls=0;
    movable=true;restricted=false;destination={-1,-1};
    Memory mem;mem.blocked=4;mem.task=13;mem.owned=12345;
    TurnBudget budget{10};bool moved=false;int thrown=-1;
    try {moved=original?parent::retreat(budget,mem):candidate::retreat(budget,mem);}
    catch(const cambc::error& e){thrown=int(e.code());}
    assert(safe_calls==1);
    assert(incoming_calls==enumerations);
    assert(memory_values(mem)==memory_values(after_safe));
    return {moved,enumerations,attempts,polls,invalidations,destination,thrown};
}
int cases=0,total_parent=0,total_candidate=0;
void fixed(int improvements,vec2 expected,bool moved=true) {
    // Geometry boundary: candidate list is ordered by fixture, never sorted.
    // All entities and candidates occupy distinct legal tiles (origin may recur).
    for(auto p:snapshot.blocked.tiles) {
        assert(cheb(p,snapshot.pos)<=1);
        for(auto c:camps)if(c.alive)assert(p!=c.p);
        for(auto e:snapshot.foes)assert(p!=e.p);
    }
    auto old=run(true),now=run(false);
    total_parent+=old.ranks;total_candidate+=now.ranks;
    int n=int(snapshot.blocked.tiles.size());
    if(old.ranks!=1+n+improvements||now.ranks!=1+n)std::cerr<<"case "<<cases<<": parent="<<old.ranks<<", candidate="<<now.ranks<<", expected improvements="<<improvements<<"\n";
    assert(old.ranks==1+n+improvements&&now.ranks==1+n);
    assert(old.moved==now.moved&&old.dest==now.dest&&old.thrown==now.thrown);
    assert(now.moved==moved&&now.dest==expected);
    assert(old.attempts==now.attempts&&old.invalidations==now.invalidations);
    assert(now.polls==old.polls+(moved?1:0));++cases;
}
int main() {
    two_improvements();
    assert(parent::incoming_impl::incoming_at({3,3},snapshot.foes)==80);
    assert(parent::incoming_impl::incoming_at({2,3},snapshot.foes)==60);
    assert(parent::incoming_impl::incoming_at({2,2},snapshot.foes)==0);
    fixed(2,{2,2});
    std::cout<<"two improvements including origin: parent 6 / candidate 4 incoming_at + camp enumerations; destination (2,2)\n";
    two_improvements();snapshot.blocked.tiles={{2,3},{2,2}};fixed(2,{2,2});
    std::cout<<"two improvements without origin: parent 5 / candidate 3 incoming_at + camp enumerations\n";
    reset();spawn.tiles={{3,3}};snapshot.blocked.tiles={{3,3},{2,2}};fixed(0,{-1,-1},false);
    reset();spawn.tiles={{0,3}};snapshot.blocked.tiles={{2,2},{2,3}};fixed(1,{2,2}); // strict equal tie
    reset();snapshot.blocked.tiles={{3,3},{4,4}};fixed(0,{-1,-1},false); // no enemies, worse spawn distance
    reset();snapshot.blocked.tiles={{2,3},{2,2}};snapshot.foes={{{5,3},0,20}};
    spawn.tiles={{7,3}};fixed(1,{2,3}); // nearest enemy wins despite farther spawn
    reset();snapshot.blocked.tiles={{2,3},{2,2}};snapshot.foes={{{5,3},0,20}};
    spawn.tiles={{0,0}};fixed(2,{2,2}); // equal nearest enemy; spawn distance wins
    two_improvements();camps[0].power=.25f;camps[1].power=.75f;
    snapshot.foes={{{5,4},2,.125f}};fixed(2,{2,2}); // mixed fractional risk
    reset();snapshot.blocked.tiles={};fixed(0,{-1,-1},false);
    // Broader fixed-state differential cases. Keep entity/addition order intact.
    std::mt19937 rng(20261105);
    for(int trial=0;trial<1000;++trial) {
        two_improvements();
        camps[0].power=float(rng()%100)/8;camps[1].power=float(rng()%100)/8;
        camps.push_back({{4,4},int(rng()%4),float(rng()%30)/16, bool(rng()%2),bool(rng()%2)});
        snapshot.foes={{{5,3},int(rng()%4),float(rng()%100)/32},{{1,5},int(rng()%3),float(rng()%40)/16}};
        std::shuffle(snapshot.blocked.tiles.begin(),snapshot.blocked.tiles.end(),rng);
        auto old=run(true),now=run(false);
        total_parent+=old.ranks;total_candidate+=now.ranks;
        assert(now.ranks==4&&old.ranks>=4&&old.ranks<=6);
        assert(old.moved==now.moved&&old.dest==now.dest&&old.attempts==now.attempts&&old.invalidations==now.invalidations);
        assert(old.thrown==now.thrown);++cases;
    }
    for(auto status:{RouteStatus::wait,RouteStatus::deferred,RouteStatus::no_route_now,RouteStatus::invalid_goals,RouteStatus::at_goal}) {
        two_improvements();safe_result=status;fixed(2,{2,2});
    }
    for(bool original:{true,false}) {
        two_improvements();safe_result=RouteStatus::moved;auto r=run(original);
        assert(r.moved&&r.ranks==0&&r.polls==0&&r.attempts==0);
        for(int exit=0;exit<3;++exit) {
            two_improvements();
            if(exit==0)stale_after_safe=true;
            if(exit==1)unavailable_after_safe=true;
            if(exit==2)spawn.tiles.clear();
            r=run(original);assert(!r.moved&&r.ranks==0&&r.attempts==0&&r.invalidations==0);
        }
        // Parent stale movement is recorded, deliberately not preserved.
        for(int crossing:{1,3}) {
            two_improvements();change_on=crossing;r=run(original);
            assert(r.ranks==(original?6:4));
            assert(r.moved==original&&r.attempts==(original?1:0));
            assert(r.invalidations==(original?2:0));
        }
        // Stale no-improvement path retains its original no-move return,
        // with only the existing early epoch poll.
        reset();spawn.tiles={{3,3}};camps={{{6,6},0,1}};
        snapshot.blocked.tiles={{3,3},{2,2}};change_on=1;r=run(original);
        assert(!r.moved&&r.attempts==0&&r.ranks==3&&r.polls==1&&r.invalidations==0);
        // State changes after retreat's early can_move check reach real helper.
        for(int event:{1,2}) {
            two_improvements();change_on=3;getter_event=event;r=run(original);
            assert(!r.moved&&r.attempts==0&&r.invalidations==1);
        }
        for(auto result:{Move::success,Move::rejected,Move::bad_destination,Move::unexpected}) {
            two_improvements();move_result=result;r=run(original);
            assert(r.attempts==1&&r.dest==(vec2{2,2}));
            assert(r.moved==(result==Move::success));
            assert(r.invalidations==(result==Move::unexpected?0:2));
            assert(r.thrown==(result==Move::unexpected?int(error_code::other):-1));
        }
        for(int fail:{1,3}) {
            two_improvements();fail_vision_on=fail;r=run(original);
            assert(r.thrown==int(error_code::visibility)&&r.ranks==fail&&r.attempts==0&&r.invalidations==0);
        }
    }
    std::cout<<"fixed-state incoming_at calls / camp enumerations totals: parent "<<total_parent<<" / candidate "<<total_candidate<<"\n";
    std::cout<<"PASS: "<<cases<<" fixed-state comparisons; safe/early exits, rollover in origin/later geometry getter, helper restrictions, rejection/errors, Memory and invalidation assertions\n";
}
