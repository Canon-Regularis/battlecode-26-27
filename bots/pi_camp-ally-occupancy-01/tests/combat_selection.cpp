// Runs the entire extracted production fight, including action execution, against
// controlled SDK-shaped values. The reference differs only in the prior camp loop.
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <vector>

namespace lp {
struct Counts {
    int hp=0, attack_masks=0, ability_masks=0, readiness=0, abilities=0;
    int visible=0, alive=0, invalidations=0, owned_actions=0;
};
Counts queries;
struct Record { float hp=120; bool visible=true, alive=true; };
std::vector<Record> records;
std::vector<std::string> actions;
std::set<const void*> live_wrappers, group_wrappers;
struct vec2 { int x=0,y=0; };
struct unit {
    int handle;
    explicit unit(int h=0):handle(h) { live_wrappers.insert(this); }
    unit(const unit& u):handle(u.handle) { live_wrappers.insert(this); }
    unit& operator=(const unit& u) { handle=u.handle; return *this; }
    virtual ~unit() { assert(live_wrappers.erase(this)==1); }
    void check() const { assert(live_wrappers.count(this)); }
    virtual float health() const {
        check(); assert(records.at(handle).visible); ++queries.hp;
        return records.at(handle).hp;
    }
    bool is_visible() const { check(); ++queries.visible; return records.at(handle).visible; }
    vec2 position() const { check(); return {handle,0}; }
};
struct camp:unit {
    using unit::unit;
    bool is_alive() const {
        check(); assert(records.at(handle).visible); ++queries.alive;
        return records.at(handle).alive;
    }
};
std::set<int> basic_tiles, spell_tiles;
struct mask {
    const std::set<int>& tiles;
    bool is_set(vec2 p) const { return tiles.count(p.x); }
};
bool attack_allowed=true, cast_allowed=false, spell_ready=true;
bool has_spell=false, channeling=false;
struct ability_aoe_damage { float radius=0; };
struct ability {
    bool is_damage() const { return true; }
    bool is_aoe_damage() const { return false; }
    bool is_cc() const { return false; }
    bool is_attack_reset() const { return false; }
    bool can_target_enemies() const { return true; }
    bool can_target_camps() const { return true; }
    bool can_target_ground() const { return false; }
    mask valid_tiles() const { ++queries.ability_masks; return {spell_tiles}; }
    float damage_amount() const { return 40; }
    float damage_amount(const unit&) const { return 40; }
    template<class T> T get() const { return {}; }
    bool use() const { assert(false); return false; }
    bool use(vec2) const { assert(false); return false; }
    bool use(const unit& u) const;
};
void record_action(const std::string& kind,const unit& u) {
    u.check();
    // A camp action must use the retained owning optional, never the loop element.
    if(u.handle<100) { assert(!group_wrappers.count(&u)); ++queries.owned_actions; }
    actions.push_back(kind+std::to_string(u.handle));
}
bool ability::use(const unit& u) const {
    record_action("cast:",u); cast_allowed=false; return true;
}
struct champion:unit {
    using unit::unit;
    bool can_attack() const { return attack_allowed; }
    bool can_cast() const { return cast_allowed; }
    mask attack_tiles() const { ++queries.attack_masks; return {basic_tiles}; }
    std::vector<ability> abilities() const {
        ++queries.abilities; return has_spell?std::vector<ability>{ability{}}:std::vector<ability>{};
    }
    int attack_range() const { return 3; }
    float strength() const { return 40; }
    void attack(const unit& u) const { record_action("attack:",u); attack_allowed=false; }
};
champion player{200};
champion& self() { return player; }
bool channel(const champion&) { return channeling; }
bool ready(const ability&) { ++queries.readiness; return spell_ready; }
struct Snapshot { int round=37; vec2 pos{}; std::vector<champion> foes; } snapshot;
const Snapshot& observe() { return snapshot; }
// Defense is outside this experiment. It has no effects in these fixtures.
bool defend_cast(const Snapshot&) { return false; }
int round_number() { return 37; }
int fuel_remaining() { return 100000; }
struct Config { static constexpr int reserve=5000; };
void invalidate_observations() { ++queries.invalidations; }
int cheb(vec2 a,vec2 b) { return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y)); }
struct Group {
    std::vector<camp> members;
    std::span<const camp> camps() const { return members; }
};
struct CampInfo { Group group; };
struct World { std::vector<CampInfo> camps; };
// Preserve the inherited action body verbatim, including its compact formatting.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmisleading-indentation"
#include "fight-under-test.h"
#include "fight-reference.h"
#pragma GCC diagnostic pop
}

struct Fixture {
    std::string name;
    std::vector<lp::Record> members;
    std::set<int> basic, spell;
    std::vector<std::string> expected;
    bool attack=true, cast=false, ready=true, enemy=false, travel=false, channel=false;
    int task=0;
};
struct Result { bool acted; lp::Counts counts; std::vector<std::string> trace; };
Result run(const Fixture& f,bool reference) {
    using namespace lp;
    queries={}; actions.clear(); records=f.members; records.resize(201);
    basic_tiles=f.basic; spell_tiles=f.spell;
    attack_allowed=f.attack; cast_allowed=f.cast; spell_ready=f.ready;
    has_spell=f.cast; channeling=f.channel;
    snapshot.foes.clear(); snapshot.pos=f.enemy?vec2{100,0}:vec2{};
    if(f.enemy) snapshot.foes.emplace_back(100);
    World world; world.camps.resize(1);
    for(size_t i=0;i<f.members.size();++i) world.camps[0].group.members.emplace_back(int(i));
    group_wrappers.clear();
    for(const auto& c:world.camps[0].group.members) group_wrappers.insert(&c);
    const auto live_before=live_wrappers;
    bool acted=reference?fight_reference(world,f.task,f.travel):fight(world,f.task,f.travel);
    // All temporary/copy wrappers have been released; source handles survive.
    assert(live_wrappers==live_before);
    assert(actions==f.expected);
    assert(acted==!actions.empty());
    group_wrappers.clear();
    return {acted,queries,actions};
}
int main() {
    using lp::Record;
    int scenarios=0;
    auto check=[&](const Fixture& f) {
        auto old=run(f,true), now=run(f,false);
        assert(old.acted==now.acted && old.trace==now.trace);
        std::cout<<f.name<<" prior -> dp01: HP "<<old.counts.hp<<" -> "<<now.counts.hp
                 <<", attack masks "<<old.counts.attack_masks<<" -> "<<now.counts.attack_masks
                 <<", ability lists "<<old.counts.abilities<<" -> "<<now.counts.abilities
                 <<", readiness "<<old.counts.readiness<<" -> "<<now.counts.readiness
                 <<", ability masks "<<old.counts.ability_masks<<" -> "<<now.counts.ability_masks<<'\n';
        ++scenarios;
        return std::pair{old.counts,now.counts};
    };
    Fixture equal; equal.name="49 equal reachable"; equal.members.resize(49);
    for(int i=0;i<49;++i) equal.basic.insert(i);
    equal.expected={"attack:0"};
    auto [old_equal,new_equal]=check(equal);
    assert(old_equal.attack_masks==50 && new_equal.attack_masks==2);
    assert(old_equal.hp==51 && new_equal.hp==50);
    Fixture late=equal; late.name="42x120 + late80"; late.members.resize(43);
    late.members.back().hp=80; late.expected={"attack:42"};
    auto [old_late,new_late]=check(late);
    assert(old_late.attack_masks==44 && new_late.attack_masks==3);
    assert(old_late.hp==46 && new_late.hp==44);
    Fixture low; low.name="unreachable low does not replace";
    low.members={{120},{40},{80}}; low.basic={0,2}; low.expected={"attack:2"};
    check(low);
    Fixture first=low; first.name="first two unreachable"; first.basic={2}; check(first);
    Fixture all=low; all.name="all unreachable, extra HP work"; all.basic.clear(); all.expected.clear();
    auto [old_all,new_all]=check(all);
    assert(old_all.hp==0 && new_all.hp==3);
    Fixture hidden=low; hidden.name="hidden and dead before live";
    hidden.members={{1,false,true},{1,true,false},{80}}; hidden.basic={0,1,2};
    auto [old_hidden,new_hidden]=check(hidden);
    assert(old_hidden.alive==2 && new_hidden.alive==2);
    assert(old_hidden.hp==3 && new_hidden.hp==2); // hidden/dead HP would assert/count incorrectly
    Fixture ties=low; ties.name="strict lower tie keeps first";
    ties.members={{120},{80},{80}}; ties.basic={0,1,2}; ties.expected={"attack:1"}; check(ties);
    Fixture none=equal; none.name="no attack or cast"; none.attack=false; none.expected.clear();
    auto [old_none,new_none]=check(none);
    assert(old_none.hp==0 && new_none.hp==0 && new_none.attack_masks==0);
    Fixture cast=late; cast.name="cast only late80"; cast.attack=false; cast.cast=true;
    cast.spell=cast.basic; cast.expected={"cast:42"};
    auto [old_cast,new_cast]=check(cast);
    assert(old_cast.readiness==44 && new_cast.readiness==3);
    assert(old_cast.ability_masks==44 && new_cast.ability_masks==3);
    assert(old_cast.abilities==44 && new_cast.abilities==3);
    Fixture mixed=cast; mixed.name="basic then cast"; mixed.attack=true;
    mixed.expected={"attack:42","cast:42"}; check(mixed);
    Fixture cooling=cast; cooling.name="cast unavailable readiness"; cooling.ready=false; cooling.expected.clear();
    auto [old_cooling,new_cooling]=check(cooling);
    assert(old_cooling.hp==0 && new_cooling.hp==43);
    Fixture enemy=low; enemy.name="enemy priority"; enemy.enemy=true; enemy.basic.insert(100);
    enemy.expected={"attack:100"};
    auto [old_enemy,new_enemy]=check(enemy);
    assert(old_enemy.visible==1 && new_enemy.visible==1); // only post-action enemy check
    Fixture travel=low; travel.name="travel skips camps"; travel.travel=true; travel.expected.clear();
    auto [old_travel,new_travel]=check(travel); assert(old_travel.hp==0 && new_travel.hp==0);
    enemy.name="travel still attacks enemy"; enemy.travel=true; check(enemy);
    Fixture no_task=travel; no_task.name="no assigned task"; no_task.travel=false; no_task.task=-1; check(no_task);
    Fixture channel=equal; channel.name="channel preserved"; channel.channel=true; channel.expected.clear(); check(channel);
    Fixture special=ties; special.name="NaN never ranks";
    special.members={{std::numeric_limits<float>::quiet_NaN()},{80},{80}}; check(special);
    special.name="positive infinity never ranks"; special.members[0].hp=std::numeric_limits<float>::infinity(); check(special);
    special.name="signed zero tie"; special.members={{120},{0.f},{-0.f}}; check(special);
    std::cout<<scenarios<<" production fight/reference scenarios passed\n";
}
