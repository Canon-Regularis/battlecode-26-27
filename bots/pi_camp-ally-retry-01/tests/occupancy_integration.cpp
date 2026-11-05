// Actual production bodies, explicit host SDK adapters. No engine/replay claims.
#include "model.h"
#include "ally_occupancy.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <optional>
#include <queue>
#include <stdexcept>
#include <tuple>
#include <vector>
namespace lp {}
namespace cambc=lp;
namespace lp {
struct vec2 {int x=0,y=0;bool operator==(const vec2&) const=default;};
int cheb(vec2 a,vec2 b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
struct bitboard {
    std::uint64_t bits=0;
    int width()const{return 8;}int height()const{return 8;}
    bool is_set(vec2 p)const{return p.x>=0&&p.x<8&&p.y>=0&&p.y<8&&(bits&(1ULL<<(p.y*8+p.x)));}
    void set(vec2 p,bool value=true){assert(p.x>=0&&p.x<8&&p.y>=0&&p.y<8);auto mask=1ULL<<(p.y*8+p.x);if(value)bits|=mask;else bits&=~mask;}
    bool is_empty()const{return !bits;}
    std::vector<vec2> positions()const{std::vector<vec2> out;for(int y=0;y<8;++y)for(int x=0;x<8;++x)if(is_set({x,y}))out.push_back({x,y});return out;}
    bitboard reachable_tiles(vec2 p,int range)const{bitboard out;for(int y=0;y<8;++y)for(int x=0;x<8;++x)if(cheb(p,{x,y})<=range&&!is_set({x,y}))out.set({x,y});return out;}
    friend bitboard operator~(bitboard b){return {~b.bits};}
    friend bitboard operator|(bitboard a,bitboard b){return {a.bits|b.bits};}
    friend bitboard operator&(bitboard a,bitboard b){return {a.bits&b.bits};}
    bitboard& operator|=(bitboard b){bits|=b.bits;return *this;}bitboard& operator&=(bitboard b){bits&=b.bits;return *this;}
};
bitboard around(vec2 p,int r){bitboard b;for(int y=0;y<8;++y)for(int x=0;x<8;++x)if(cheb(p,{x,y})<=r)b.set({x,y});return b;}
int host_round=20,fields=0,moves=0,roll_field=0,roll_collection=0,collection_calls=0,position_calls=0,alive_calls=0;
int round_calls=0,roll_round=0,roll_position=0,roll_revision_field=0;
std::vector<bitboard> field_masks;
unsigned revision=1;bool valid_cache=false,move_allowed=true;bitboard physical,visible_allies,visible_mask;vec2 origin{1,1};
unsigned round_number(){if(++round_calls==roll_round)++host_round;return host_round;}unsigned fuel_remaining(){return 100000;}unsigned observation_version(){return revision;}
#include "invalidate-under-test.h"
struct ability_dash{int range=2;};
struct ability {bool is_dash()const{return false;}template<class T>T get()const{return {};}bool use(vec2)const{return false;}};
bool ready(const ability&){return false;}
enum class error_code {api_not_in_vision,api_not_found,unexpected,invalid_action_move_bad_destination};
struct error:std::runtime_error {error_code value;explicit error(error_code c):std::runtime_error("host SDK failure"),value(c){}error_code code()const{return value;}};
int hidden_error=-1,move_error=-1,move_attempts=0,rejections=0;
bool restricted=false,reject_hidden=false;vec2 ally_position{2,1};
struct buff_restrictions {static constexpr int move=1;bool contains(int)const{return restricted;}};
struct champion {
    int identity=1;bool is_alive()const{++alive_calls;if(identity==2&&visible_allies.is_empty()&&hidden_error>=0)throw error(static_cast<error_code>(hidden_error));return true;}bool can_move()const{return move_allowed;}bool can_cast()const{return false;}
    buff_restrictions restrictions()const{return {};}
    bool move_absolute(vec2 p)const;
    vec2 position()const{if(++position_calls==roll_position)++host_round;assert(identity==1||visible_allies.is_set(ally_position));return identity==1?origin:ally_position;}
    float health()const{return 100;}float max_health()const{return 100;}int gem_count()const{return 0;}int attack_range()const{return 1;}
    float strength()const{return 0;}std::vector<ability> abilities()const{return {};}
};
champion& self(){static champion me;return me;}int id(const champion& c){return c.identity;}bool channel(const champion&){return false;}
struct Camp {bool is_alive()const{return true;}bool is_awake()const{return false;}int strength()const{return 0;}vec2 position()const{return {6,1};}int attack_range()const{return 1;}vec2 spawn_position()const{return {6,1};}};
namespace team {constexpr int ally=0,enemy=1;}
namespace map {bitboard spawn_region(int){return {};}}
namespace vision {
bitboard visible_tiles(){return visible_mask;}
bitboard champion_tiles(int side){return side==team::ally?visible_allies:bitboard{};}
bitboard champion_tiles(){return visible_allies;}bitboard camp_tiles(){return {};}bitboard teleport_tiles(){return {};}
champion champion_at(vec2){if(++collection_calls==roll_collection)++host_round;return {2};}
std::vector<champion> champions(int){return {};}std::vector<Camp> camps(){return {};}
}
struct Snapshot {occupancy::Batch allies_owned;int round=0;vec2 pos{};float hp=0,max_hp=1,incoming=0;int bag=0,enemies=0,friends=1;bool alive=false,spawn=false,camp_hit=false;bitboard visible,blocked,risk;std::vector<champion> foes,allies;};
Snapshot cached; // production observe body uses these names
occupancy::Cache camp_occupancy;
std::vector<champion> occupancy_roster{{1},{2}};
#include "prepare-under-test.h"
bitboard static_blocked(){return physical;}float incoming_at(vec2,const std::vector<champion>&){return 0;}
#include "observe-under-test.h"
bool champion::move_absolute(vec2 p)const {
    ++move_attempts;assert(!physical.is_set(p));assert(host_round==cached.round);
    if(move_error>=0)throw error(static_cast<error_code>(move_error));
    if(reject_hidden&&p==ally_position) {
        ++rejections;reject_hidden=false;visible_allies.set(p);visible_mask.set(p);return false;
    }
    origin=p;++moves;move_allowed=false;return true;
}
#include "move-checked-under-test.h"
#include "navigation-types-under-test.h"
struct distance_field {
    int distances[64];
    void compute_to(bitboard blocked,bitboard goals,bitboard,bitboard& reached){
        ++fields;field_masks.push_back(blocked);for(auto& d:distances)d=65535;std::queue<vec2> q;
        for(auto p:goals.positions()){distances[p.y*8+p.x]=0;q.push(p);reached.set(p);}
        while(!q.empty()){auto p=q.front();q.pop();for(auto n:blocked.reachable_tiles(p,1).positions())if(distances[n.y*8+n.x]==65535){distances[n.y*8+n.x]=get(p)+1;reached.set(n);q.push(n);}}
        if(roll_field)++host_round;
        if(roll_revision_field)invalidate_observations();
    }
    int get(vec2 p)const{return distances[p.y*8+p.x];}
};
#include "move-under-test.h"
struct Group{std::vector<Camp> camps()const{return {Camp{}};}};
struct Objective{int lifecycle=1,seen=20;bitboard tiles;Group group;};
struct World{std::vector<Objective> camps{Objective{}};void refresh(const Snapshot&,Memory&) {}};
bitboard requested_goals;bitboard camp_goals(const Objective&,const Snapshot&){return requested_goals;}
bool fight(World&,int){return false;}
}
using namespace lp;
class Bot {public:World world;Memory memory;struct {int moves=0,defers=0;}stats;void abandon(int){memory.task=-1;}Facts facts(const Snapshot&,bool){return {};}void camp_action(TurnBudget&);};
#include "camp-action-under-test.h"
void fresh(int r){host_round=r;valid_cache=false;invalidate_observations();move_allowed=true;}
void setup(){
    camp_occupancy=occupancy::Cache{};camp_occupancy.configure({1,2},1);camp_occupancy.reset({0,0,20});
    restricted=reject_hidden=false;move_error=-1;move_attempts=rejections=0;ally_position={2,1};
    physical={};visible_mask={};visible_allies={};origin={1,1};fields=moves=0;field_masks.clear();roll_field=roll_collection=collection_calls=0;round_calls=roll_round=roll_position=position_calls=roll_revision_field=0;fresh(20);
}
// Only source selection differs in the parent control, never the policy body.
#ifdef PARENT_RETRY
constexpr bool parent_retry=true;
#else
constexpr bool parent_retry=false;
#endif
void hidden_transition() {
    setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
    ally_position={2,0};reject_hidden=true;
    physical.bits=~0ULL;
    for(auto p:std::vector<vec2>{{1,1},{2,1},{2,0},{3,1}})physical.set(p,false);
    requested_goals=around({3,1},0);
}
int main(){
    // Same hidden rejection for populated, empty-but-present, and ordinary plans.
    for(int plan=0;plan<3;++plan) {
        hidden_transition();auto attempt=prepare_camp_occupancy(observe(),true);
        assert(attempt.current&&attempt.uncertain.size()==1);
        bitboard overlay;if(plan==0)overlay.set({2,1});
        Memory route;route.last_distance=50;TurnBudget b{21};
        auto result=move_to(requested_goals,false,b,route,false,plan==2?nullptr:&overlay);
        assert(rejections==1&&!visible_mask.is_set({2,1}));
        assert(!field_masks[0].is_set({2,0})&&field_masks[0].is_set({2,1})==(plan==0));
        if(!parent_retry&&plan!=2) {
            assert(result==RouteStatus::deferred&&fields==1&&b.fields==1&&moves==0);
            assert(route.blocked==1&&route.last_distance==50);
        } else if(plan==0) {
            assert(result==RouteStatus::no_route_now&&fields==2&&moves==0&&route.last_distance==50);
            assert(field_masks[1].is_set({2,1})&&field_masks[1].is_set({2,0}));
        } else {
            assert(result==RouteStatus::moved&&fields==2&&moves==1&&origin==vec2(2,1));
            assert(route.blocked==0&&route.last_distance==1);
        }
        const auto& published=observe();assert(published.blocked.is_set({2,0}));
        assert(!published.visible.is_set({2,1})); // X stays hidden: identity contradiction only.
        assert(prepare_camp_occupancy(published,true).uncertain.empty());
        if(plan==0) {
            fresh(22);auto next=prepare_camp_occupancy(observe(),true);
            assert(next.current&&next.uncertain.empty()&&cached.blocked.is_set({2,0}));
            bitboard empty;TurnBudget nb{22};
            assert(move_to(requested_goals,false,nb,route,false,&empty)==RouteStatus::moved);
            assert(origin==vec2(2,1)&&moves==1&&fields==(parent_retry?3:2));
            assert(!field_masks.back().is_set({2,1})&&field_masks.back().is_set({2,0}));
        }
    }
    // The actual caller publishes the new Y sighting after the deferred attempt,
    // leaves progress untouched, and rebuilds a fresh plan on the next round.
    hidden_transition();Bot retry;retry.memory.task=0;
    retry.memory.task_started=retry.memory.progressed=20;retry.memory.last_distance=50;
    TurnBudget rb{21};retry.camp_action(rb);
    assert(fields==(parent_retry?2:1)&&moves==0&&retry.stats.defers==(parent_retry?0:1));
    assert(retry.memory.progressed==20&&retry.memory.last_distance==50&&retry.memory.task_started==20);
    assert(cached.blocked.is_set({2,0})&&!cached.visible.is_set({2,1}));
    fresh(22);TurnBudget rb2{22};retry.camp_action(rb2);
    assert(moves==1&&origin==vec2(2,1)&&retry.memory.progressed==22);
    assert(retry.memory.task==0&&retry.memory.task_started==20);
    // No failure-deletion on deferred rejection: preserve a still-hidden X.
    // Exercise actual move_checked restrictions and expected bad-destination handling.
    for(int failure=0;failure<2;++failure) {
        setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
        restricted=failure==0;
        move_error=failure==1?int(error_code::invalid_action_move_bad_destination):-1;
        Bot rejected;rejected.memory.task=0;rejected.memory.task_started=rejected.memory.progressed=20;
        rejected.memory.last_distance=50;requested_goals=around({6,1},0);TurnBudget t{21};
        rejected.camp_action(t);
        assert(moves==0&&rejected.memory.progressed==20&&rejected.memory.last_distance==50);
        assert(fields==(parent_retry?Config::max_fields:1));
        assert(rejected.stats.defers==(parent_retry?0:1));
        fresh(22);assert(prepare_camp_occupancy(observe(),true).uncertain.size()==1);
    }
    // Actual caller schedules failed-version X, then observation publication of Y
    // supersedes it before the next normal attempt can apply pending deletion.
    setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
    physical.bits=~0ULL;for(int x=1;x<=6;++x)physical.set({x,1},false);
    Bot pending;pending.memory.task=0;pending.memory.task_started=pending.memory.progressed=20;
    pending.memory.last_distance=50;requested_goals=around({6,1},0);TurnBudget pb{21};pending.camp_action(pb);
    assert(fields==1&&moves==0&&pending.memory.progressed==20);
    ally_position={2,0};visible_allies.set(ally_position);visible_mask.set(ally_position);
    invalidate_observations();observe();visible_allies={};visible_mask={};fresh(22);
    auto protected_version=prepare_camp_occupancy(observe(),true);
    assert(protected_version.uncertain.size()==1&&protected_version.uncertain[0].position==occupancy::Position(2,0));
    assert(pending.memory.progressed==20&&pending.memory.last_distance==50);
    // Exact helper semantics: unavailable/restricted do not call the SDK or invalidate;
    // expected bad destination invalidates, unrelated errors propagate unchanged.
    for(int failure=0;failure<4;++failure) {
        setup();observe();auto before=observation_version();
        move_allowed=failure!=0;restricted=failure==1;
        if(failure>=2)move_error=int(failure==2?error_code::invalid_action_move_bad_destination:error_code::unexpected);
        bool threw=false;try {assert(!move_checked({2,0}));}catch(const error& e){threw=true;assert(e.code()==error_code::unexpected);}
        assert(threw==(failure==3)&&moves==0&&move_attempts==(failure>=2?1:0));
        assert(observation_version()==before+(failure==2?1:0));
    }
    // Successful populated and empty overlays retain one-field distance accounting.
    for(bool populated:{false,true}) {
        setup();bitboard overlay;if(populated)overlay.set({2,1});Memory success;
        success.blocked=2;TurnBudget sb{20};
        assert(move_to(around({3,1},0),false,sb,success,false,&overlay)==RouteStatus::moved);
        assert(fields==1&&moves==1&&origin==vec2(2,0)&&success.blocked==0&&success.last_distance==1);
    }
    std::cout<<"PASS retry additions: 3 plan boundaries, 1 caller continuation, 2 no-deletion caller cases, 1 pending-version caller case, 4 helper cases, 2 successful overlay cases (13 scenarios)\n";

    setup();visible_allies.set({2,1});observe();assert(cached.allies_owned.positives.size()==1);
    visible_allies={};fresh(21);auto a=prepare_camp_occupancy(observe(),true);assert(a.uncertain.size()==1);int alive_before=alive_calls;
    prepare_camp_occupancy(observe(),true);assert(alive_before==alive_calls); // no new probe on reuse
    // Actual SDK adapter preserves expected hidden-query failures as unknown, other errors propagate.
    for(auto failure:{error_code::api_not_in_vision,error_code::api_not_found,error_code::unexpected}) {
        setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);hidden_error=int(failure);
        bool threw=false;try {observe();}catch(const error&){threw=true;}
        assert(threw==(failure==error_code::unexpected));hidden_error=-1;
        assert(prepare_camp_occupancy(observe(),true).uncertain.size()==1);
    }
    // Collection crosses a round: no owned partial batch and no stale movement.
    setup();visible_allies.set({2,1});roll_collection=1;TurnBudget stale{20};auto& s=observe();assert(!s.allies_owned.complete&&s.allies_owned.positives.empty());
    Memory m;auto goal=around({6,1},0);bitboard uncertain;assert(move_to(goal,false,stale,m,false,&uncertain)==RouteStatus::wait&&moves==0);
    // Before collection rollover discards owned values; after collection rollover fails publication too.
    for(int crossing:{1,2}) {
        setup();visible_allies.set({2,1});roll_position=crossing;TurnBudget epoch{20};observe();
        assert(!prepare_camp_occupancy(cached,true).current);
        assert(move_to(goal,false,epoch,m,false,&uncertain)==RouteStatus::wait&&moves==0);
    }
    // A revision change during a completed field is stale, not a no-route inference.
    setup();roll_revision_field=1;TurnBudget changed{20};assert(move_to(goal,false,changed,m,false,&uncertain)==RouteStatus::deferred&&moves==0);roll_revision_field=0;
    // Actual camp_action: uncertain cut vertex fails once, next normal round opens path.
    setup();visible_allies.set({2,1});observe();visible_allies={};
    physical.bits=~0ULL;for(int x=1;x<=6;++x)physical.set({x,1},false);requested_goals=around({6,1},0);
    Bot bot;bot.memory.task=0;bot.memory.task_started=bot.memory.progressed=20;bot.memory.last_distance=50;
    fresh(21);TurnBudget b{21};bot.camp_action(b);assert(fields==1&&moves==0&&bot.memory.progressed==20&&bot.memory.last_distance==50);
    TurnBudget same{21};bot.camp_action(same);assert(moves==0&&fields==2); // no relaxation in failed round
    fresh(22);TurnBudget next{22};bot.camp_action(next);assert(moves==1&&fields==3&&bot.memory.progressed==22);
    assert(task_expired(30,20,22)&&!task_expired(29,20,22));assert(task_expired(110,20,109));
    // Overlay-empty vs already-empty; empty goals never credit progress.
    for(bool empty:{false,true}){
        setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
        Bot x;x.memory.task=0;x.memory.task_started=x.memory.progressed=20;x.memory.last_distance=50;
        requested_goals=empty?bitboard{}:around({2,1},0);TurnBudget t{21};x.camp_action(t);assert(fields==0&&moves==0&&x.memory.progressed==20);
        fresh(22);auto retained=prepare_camp_occupancy(observe(),true);assert(retained.uncertain.empty()==!empty);
    }
    // Field rollover returns deferred without deletion, stale move, or progress credit.
    setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);roll_field=1;
    Bot d;d.memory.task=0;d.memory.task_started=d.memory.progressed=20;requested_goals=around({6,1},0);TurnBudget db{21};d.camp_action(db);
    assert(moves==0&&fields==1&&d.stats.defers==1&&d.memory.progressed==20);roll_field=0;fresh(23);assert(prepare_camp_occupancy(observe(),true).uncertain.size()==1);
    // Field admission exhaustion is deferred, not occupancy evidence.
    TurnBudget exhausted{23,Config::max_fields};bitboard mask=around({2,1},0);assert(move_to(requested_goals,false,exhausted,d.memory,false,&mask)==RouteStatus::deferred);
    // Necessary backtracking uses ordinary decreasing fields, including previous tile.
    setup();origin={3,1};physical.bits=~0ULL;for(auto p:std::vector<vec2>{{3,1},{2,1},{1,2},{1,3},{2,4},{3,4},{4,4}})physical.set(p,false);
    requested_goals=around({4,4},0);TurnBudget back{20};assert(move_to(requested_goals,false,back,m)==RouteStatus::moved&&origin==vec2(2,1));
    // Ordinary navigation ignores retained hidden ally evidence.
    setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);TurnBudget ordinary{21};assert(move_to(around({2,1},0),false,ordinary,m)==RouteStatus::moved&&origin==vec2(2,1));
    // Actual camp_action at_goal and wait do not schedule relaxation or credit progress.
    for(bool wait:{false,true}) {
        setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
        Bot idle;idle.memory.task=0;idle.memory.task_started=idle.memory.progressed=20;
        requested_goals=around(origin,0);move_allowed=!wait;TurnBudget ib{21};idle.camp_action(ib);
        assert(moves==0&&fields==0&&idle.memory.progressed==20);
        fresh(22);assert(prepare_camp_occupancy(observe(),true).uncertain.size()==1);
    }
    // Actual reward and absent-task paths clear applicability; reward navigation is ordinary.
    for(int lifecycle:{-1,2,3}) {
        setup();visible_allies.set({2,1});observe();visible_allies={};fresh(21);
        Bot cleared;cleared.memory.task=lifecycle<0?-1:0;cleared.memory.task_started=20;
        cleared.world.camps[0].lifecycle=lifecycle;requested_goals=around({2,1},0);
        TurnBudget cb{21};cleared.camp_action(cb);
        assert(prepare_camp_occupancy(observe(),true).uncertain.empty());
        if(lifecycle==2)assert(moves==1);
    }
    // Current blockers survive uncertainty relaxation.
    setup();physical.set({2,1});TurnBudget current{20};assert(move_to(around({2,1},0),false,current,m,false,&uncertain)==RouteStatus::invalid_goals&&moves==0);
    std::cout<<"PASS production observe/move_to/camp_action/task_expired: rollover, field count, progress, backtracking and scope\n";
}
