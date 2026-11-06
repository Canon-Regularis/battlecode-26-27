#include "economic_scene_sdk.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <tuple>
namespace lp {
namespace {
using economic::Point;
Point point(vec2 p){return {p.x,p.y};}
vec2 tile(Point p){return {p.x,p.y};}
int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
struct SceneCapacity:std::runtime_error {SceneCapacity():runtime_error("economic scene capacity/metadata"){};};
int integer_range(float value,int maximum) {
    return std::isfinite(value)&&value>=0&&value<=maximum&&std::floor(value)==value?int(value):-1;
}
void nonnegative(float value){if(!std::isfinite(value)||value<0)throw SceneCapacity{};}
bool coordinate_less(vec2 a,vec2 b){return std::tie(a.y,a.x)<std::tie(b.y,b.x);}
bool contains(const std::vector<vec2>& values,Point p){return std::binary_search(values.begin(),values.end(),tile(p),coordinate_less);}
std::uint64_t combine(std::uint64_t state,std::uint64_t value) {
    return (state^value)*1099511628211ull;
}
}
void EconomicCapture::prepare(World& world,LiveTurn& turn) {
    if(initialized)return;
    if(world.camps.size()>128||world.width<=0||world.height<=0||world.width>16384/world.height)throw SceneCapacity{};
    std::vector<Descriptor> next;
    std::vector<std::pair<camp_type,camp_stats>> designs;
    const auto epoch=turn.epoch();
    auto next_geometry=std::make_shared<economic::Geometry>();
    next_geometry->groups.reserve(world.camps.size());
    for(int group=0;group<int(world.camps.size());++group) {
        const auto& objective=world.camps[group];
        economic::GroupGeometry metadata;
        metadata.anchor=point(objective.anchor);metadata.gems=objective.group.gem_value();metadata.gold=objective.group.gold_value();
        metadata.spawn.reserve(objective.group.camps().size());
        for(const auto& c:objective.group.camps()) {
            if(next.size()>=256)throw SceneCapacity{};
            auto known=std::find_if(designs.begin(),designs.end(),[&](auto d){return d.first==c.kind();});
            camp_stats stats;
            if(known==designs.end()){stats=turn.read([&]{return c.base_stats();});designs.push_back({c.kind(),stats});}
            else stats=known->second;
            nonnegative(stats.base_health);
            // Only positively nonattacking cluster profiles receive a passive proof.
            const bool cluster=c.kind()==camp_type::gem_cluster||c.kind()==camp_type::gold_cluster;
            bool passive=cluster&&stats.base_strength==0&&stats.strength_growth==0;
            if(stats.base_attack_range<0||stats.base_attack_range>16384)throw SceneCapacity{};
            next.push_back({c,unsigned(static_cast<handle_camp_t>(c)),group,stats.base_attack_range,
                point(c.spawn_position()),stats.base_health,passive});
            metadata.spawn.push_back(point(c.spawn_position()));
        }
        next_geometry->groups.push_back(std::move(metadata));
    }
    std::vector<Identity> sorted;
    for(unsigned i=0;i<next.size();++i)sorted.push_back({next[i].key,i});
    std::sort(sorted.begin(),sorted.end(),[](auto a,auto b){return a.key<b.key;});
    for(unsigned i=1;i<sorted.size();++i)if(sorted[i-1].key==sorted[i].key)throw SceneCapacity{};
    // Static metadata publishes as one complete owned topology. A cold
    // interrupted build cannot leave an initialized partial geometry.
    turn.check();if(turn.epoch()!=epoch)throw TurnExpired{};
    auto next_lifecycle=std::vector<economic::Life>(world.camps.size(),economic::Life::unknown);
    auto next_cycles=std::vector<int>(world.camps.size(),0);
    turn.check();if(turn.epoch()!=epoch)throw TurnExpired{};
    descriptors=std::move(next);identities=std::move(sorted);
    lifecycle=std::move(next_lifecycle);cycles=std::move(next_cycles);geometry=std::move(next_geometry);
    initialized=true;
}
economic::Scene EconomicCapture::capture(World& world,LiveTurn& turn,int selected_group) {
    using namespace economic;
    turn.check();const auto start=turn.epoch();Scene out;
    if(turn.ledger().captures==UINT32_MAX)throw SceneCapacity{};
    ++turn.ledger().captures;
    if(world.camps.size()>128||world.width<=0||world.height<=0||world.width>16384/world.height)throw SceneCapacity{};
    auto& me=self();auto read=[&](auto f){return turn.read(f);};
    out.width=world.width;out.height=world.height;
    champion_state state;auto& own=out.economy.self;own.epoch=start;
    turn.capture_reads([&](auto& batch) {
        state=batch.read([&]{return me.state();});
        own.bag=batch.read([&]{return me.gem_count();});own.gold=batch.read([&]{return me.gold_count();});
        own.score=batch.read([]{return global_submitted_gems(team::ally);});
    });
    own.alive=state.contains(champion_state::alive);own.completed=state.contains(champion_state::completed_turn);
    out.economy.has_altars=!world.altars.empty();
    turn.ledger().channel_history(state.contains(champion_state::recall_started),
        state.contains(champion_state::recall_cancelled),state.contains(champion_state::submit_gems_started));
    if(!own.alive) {
        if(turn.epoch()!=start)throw TurnExpired{};
        out.economy.complete=true;return out;
    }
    turn.capture_reads([&](auto& batch) {
        own.pos=point(batch.read([&]{return me.position();}));own.hp=batch.read([&]{return me.health();});
        own.max_hp=batch.read([&]{return me.max_health();});
    });nonnegative(own.hp);nonnegative(own.max_hp);
    if(!out.inside(own.pos)||own.max_hp<=0)throw SceneCapacity{};
    own.channel=state.contains(champion_state::submitting_gems)?Channel::submit:
        state.contains(champion_state::teleporting)?Channel::teleport:
        state.contains(champion_state::recalling)?Channel::recall:Channel::none;
    if(own.channel!=Channel::none)own.channel_timer=read([&]{return me.remaining_channel_time();});
    if(own.channel!=Channel::none) {
        turn.check();if(turn.epoch()!=start)throw TurnExpired{};
        out.economy.complete=true;return out;
    }
    prepare(world,turn);
    out.geometry=geometry;
    auto next_cycles=cycles;
    const auto restrictions=read([&]{return me.restrictions();});
    own.stunned=read([&]{return me.buffs().has_stun();});
    out.move_restricted=restrictions.contains(buff_restrictions::move);
    out.attack_restricted=restrictions.contains(buff_restrictions::attack);
    out.cast_restricted=restrictions.contains(buff_restrictions::cast);
    out.consumable_restricted=restrictions.contains(buff_restrictions::consumable);
    out.ward_restricted=restrictions.contains(buff_restrictions::ward);
    out.can_move=state.contains(champion_state::can_move)&&!out.move_restricted;
    out.can_attack=state.contains(champion_state::can_attack)&&!out.attack_restricted;
    out.can_cast=state.contains(champion_state::can_cast)&&!out.cast_restricted&&turn.ledger().casts==0;
    enum_map<item_type> inventory;
    turn.capture_reads([&](auto& batch) {
        out.attack_range=batch.read([&]{return me.attack_range();});out.move_range=batch.read([&]{return me.base_stats();}).base_move_speed;
        out.basic=batch.read([&]{return me.strength();});inventory=batch.read([&]{return me.item_count();});
    });
    out.ranged=out.attack_range>1;nonnegative(out.basic);
    float monster=1;
    for(auto item:{item_type::monster_emblem_of_strength,item_type::monster_emblem_of_focus,item_type::monster_emblem_of_health}) {
        if(inventory[item]) {
            const auto metadata=read([&]{return item.info();});nonnegative(metadata.passive_magnitude);
            if(metadata.passive!=item_passive::monster)throw SceneCapacity{};
            monster=1+metadata.passive_magnitude;nonnegative(monster);break;
        }
    }
    const auto own_type=read([&]{return me.champion_name();});
    if(own_type==champion_type::heart_of_ruin)
        out.basic*=1+constants::passive_abilities::heart_of_ruin_missing_health_damage_max_bonus*
            std::clamp(1-own.hp/own.max_hp,0.0f,1.0f);
    out.basic*=monster;nonnegative(out.basic);
    const auto abilities=me.abilities();if(abilities.size()>2)throw SceneCapacity{};
    for(unsigned slot=0;slot<abilities.size();++slot) {
        auto a=abilities[slot];auto& v=out.abilities[slot];v.slot=int(slot);
        if(!a.info())continue;
        v.cooldown=read([&]{return a.cooldown();});
        v.camps=a.can_target_camps();v.enemies=a.can_target_enemies();v.allies=a.can_target_allies();
        v.self=a.can_target_self();v.ground=a.can_target_ground();
        v.exclusive=std::visit([](auto p){return p.exclusive_with_movement;},*a.info());
        if(a.is_attack_reset()){v.kind=AbilityKind::reset;v.supported=true;}
        else if(a.is_damage()) {v.kind=AbilityKind::damage;v.range=integer_range(a.get<ability_damage>().range,16384);}
        else if(a.is_cc()){v.kind=AbilityKind::cc;v.range=integer_range(a.get<ability_cc>().range,16384);v.stunning=true;}
        else if(a.is_dash()) {
            auto d=a.get<ability_dash>();v.kind=AbilityKind::dash;
            v.range=integer_range(d.range,2);v.radius=integer_range(d.radius,1);
            v.supported=v.range>=1&&v.radius>=0&&!v.exclusive&&d.duration>=0;
            v.damaging=d.modifier>0;v.stunning=d.duration>0;
        } else if(a.is_shield()){v.kind=AbilityKind::shield;v.supported=true;}
        else if(a.is_heal()){v.kind=AbilityKind::heal;v.range=integer_range(a.get<ability_heal>().range,16384);}
        else v.kind=AbilityKind::unsupported;
        if(v.kind==AbilityKind::damage||v.kind==AbilityKind::cc||v.kind==AbilityKind::heal)v.supported=v.range>=0;
        if(v.kind==AbilityKind::damage||v.kind==AbilityKind::cc||(v.kind==AbilityKind::dash&&v.damaging)) {
            v.amount=read([&]{return a.damage_amount();})*monster;nonnegative(v.amount);
        }
        if(v.kind==AbilityKind::heal) {v.amount=read([&]{return a.heal_amount();});nonnegative(v.amount);}
    }
    out.carried_locks=read([&]{return me.consumables()[consumable_type::altar_lock].count();});
    bitboard window;read([&]{window.draw_chebyshev(tile(own.pos),3);return true;});
    const auto visible=read([]{return vision::visible_tiles();});
    auto local_visible=read([&]{return (visible&window).positions();});
    const auto camp_tiles=read([]{return vision::camp_tiles();});
    const auto camp_positions=read([&]{return camp_tiles.positions();});
    auto awake_positions=read([]{return vision::awake_camp_tiles().positions();});
    auto asleep_positions=read([]{return vision::asleep_camp_tiles().positions();});
    const auto ally_positions=read([]{return vision::champion_tiles(team::ally).positions();});
    const auto enemy_positions=read([]{return vision::champion_tiles(team::enemy).positions();});
    const auto teleports=read([&]{return (vision::teleport_tiles()&window).positions();});
    const auto local_blocked=read([&]{return (static_blocked()&window).positions();});
    if(local_visible.size()>49||local_blocked.size()>49||teleports.size()>49||
        camp_positions.size()>256||awake_positions.size()>256||asleep_positions.size()>256||ally_positions.size()>32||enemy_positions.size()>32)throw SceneCapacity{};
    auto sorted_camps=camp_positions;std::sort(sorted_camps.begin(),sorted_camps.end(),coordinate_less);
    std::sort(awake_positions.begin(),awake_positions.end(),coordinate_less);
    std::sort(asleep_positions.begin(),asleep_positions.end(),coordinate_less);
    for(unsigned i=1;i<sorted_camps.size();++i)if(sorted_camps[i]==sorted_camps[i-1])throw SceneCapacity{};
    std::vector<vec2> living=awake_positions;
    living.insert(living.end(),asleep_positions.begin(),asleep_positions.end());
    std::sort(living.begin(),living.end(),coordinate_less);
    if(living!=sorted_camps)throw SceneCapacity{};
    for(auto p:local_visible){int i=out.local(point(p));if(i<0||!out.inside(point(p)))throw SceneCapacity{};out.visible[i]=1;}
    auto mark=[&](const auto& values,auto& mask){for(auto p:values){int i=out.local(point(p));if(!out.inside(point(p)))throw SceneCapacity{};if(i>=0)mask[i]=1;}};
    mark(local_blocked,out.blocked);mark(camp_positions,out.occupied);mark(ally_positions,out.occupied);
    mark(enemy_positions,out.occupied);mark(teleports,out.occupied);
    out.occupied[out.local(own.pos)]=0;
    own.spawn=read([&]{return map::spawn_region(team::ally).is_set(tile(own.pos));});
    // Carry HP only across a positively identified stationary self/reset or
    // single-target basic effect, with unchanged local vision/occupancy and
    // identical actor/life/round. No permission or threat Strength is leased.
    const auto& receipt=turn.ledger().pending;
    bool patch=cached&&previous.self.epoch==receipt.request.epoch&&
        start.same_turn(receipt.request.epoch)&&receipt.stop==action::Stop::accepted&&
        receipt.reduced&&!receipt.after_observed&&own.pos==previous.self.pos&&
        own.hp==previous.self.hp&&out.visible==previous.visible&&
        descriptors.size()==previous.members.size();
    const bool known_kit=own_type==champion_type::heart_of_ruin||own_type==champion_type::marcella||
        own_type==champion_type::vesper_vale||own_type==champion_type::ren||own_type==champion_type::vendetta;
    const bool basic_patch=receipt.request.op==action::Op::basic&&receipt.request.service&&known_kit;
    bool self_patch=false;
    if(receipt.request.target.slot>=0&&receipt.request.target.slot<2) {
        const auto kind=out.abilities[receipt.request.target.slot].kind;
        self_patch=(receipt.request.op==action::Op::reset&&kind==AbilityKind::reset)||
                   (receipt.request.op==action::Op::shield&&kind==AbilityKind::shield);
    }
    patch&=basic_patch||self_patch;
    int changed=-1;bool changed_dead=false;
    if(patch&&basic_patch) {
        for(unsigned i=0;i<descriptors.size();++i)if(descriptors[i].key==unsigned(receipt.request.target.key)&&
            descriptors[i].group==receipt.request.target.task)changed=int(i);
        if(changed<0||!previous.members[changed].visible||!previous.members[changed].hp_known)patch=false;
        if(patch)for(const auto& d:descriptors)if(d.group==descriptors[changed].group&&!d.passive)patch=false;
        if(patch) {
            try {changed_dead=read([&]{return descriptors[changed].handle.state();}).is_dead();}
            catch(const cambc::error& e) {
                if(e.code()!=error_code::api_not_found&&e.code()!=error_code::api_not_in_vision)throw;
                turn.check();patch=false;
            }
        }
    }
    if(patch) {
        std::vector<vec2> expected;
        for(unsigned i=0;i<previous.members.size();++i)if(previous.members[i].visible&&previous.members[i].alive&&
            !(int(i)==changed&&changed_dead))expected.push_back(tile(previous.members[i].pos));
        std::sort(expected.begin(),expected.end(),coordinate_less);
        patch=expected==sorted_camps;
        auto expected_occupancy=previous.occupied;
        if(changed>=0&&changed_dead) {
            int local=out.local(previous.members[changed].pos);
            if(local>=0)expected_occupancy[local]=0;
        }
        patch&=out.occupied==expected_occupancy;
        auto same_champions=[&](const auto& positions,const auto& old,bool allied) {
            std::vector<vec2> a=positions,b;
            if(allied)b.push_back(tile(own.pos));
            for(const auto& c:old)b.push_back(tile(c.pos));
            std::sort(a.begin(),a.end(),coordinate_less);std::sort(b.begin(),b.end(),coordinate_less);
            return a==b;
        };
        patch&=same_champions(ally_positions,previous.allies,true)&&same_champions(enemy_positions,previous.enemies,false);
    }
    out.members.reserve(descriptors.size());
    // A sorted coordinate -> dense row join replaces a member scan for every
    // visible camp. Patch proof above establishes exactly this coordinate set.
    struct VisibleIdentity {vec2 pos;unsigned index;};
    std::vector<VisibleIdentity> prior_visible;
    if(patch) {
        for(unsigned i=0;i<previous.members.size();++i) {
            const auto& member=previous.members[i];
            if(member.visible&&member.alive)prior_visible.push_back({tile(member.pos),i});
        }
        std::sort(prior_visible.begin(),prior_visible.end(),[](auto a,auto b){return coordinate_less(a.pos,b.pos);});
    }
    if(patch) {
        out.members=previous.members;
        for(auto& row:out.members)row.unchanged_event=receipt.event;
    } else for(const auto& d:descriptors)
        out.members.push_back({d.key,d.group,d.range,d.last,0,0,d.prior_hp,false,false,false,false,d.passive,false,{},{},0});
    std::vector<bool> mapped(descriptors.size(),false);
    for(auto p:camp_positions) {
        // At most three public getters; scalar joins are bounded by256 rows.
        turn.capture_reads([&](auto& batch) {
        std::optional<camp> handle;
        unsigned key=0;
        if(patch) {
            auto known=std::lower_bound(prior_visible.begin(),prior_visible.end(),p,
                [](auto row,auto pos){return coordinate_less(row.pos,pos);});
            if(known==prior_visible.end()||known->pos!=p)throw SceneCapacity{};
            key=previous.members[known->index].key;
        } else {handle=batch.read([&]{return vision::camp_at(p);});key=unsigned(static_cast<handle_camp_t>(*handle));}
        auto match=std::lower_bound(identities.begin(),identities.end(),key,[](auto a,auto b){return a.key<b;});
        if(match==identities.end()||match->key!=key||mapped[match->index])throw SceneCapacity{};
        mapped[match->index]=true;auto& row=out.members[match->index];
        if(!handle)handle=descriptors[match->index].handle;
        row.pos=point(p);row.visible=row.known=row.alive=true;row.awake=contains(awake_positions,row.pos);
        row.state_epoch=start;
        if(!patch||int(match->index)==changed) {
            row.hp=batch.read([&]{return handle->health();});nonnegative(row.hp);row.hp_known=true;row.hp_epoch=start;
            row.unchanged_event=0;
        }
        if(!row.passive){row.strength=batch.read([&]{return handle->strength();});nonnegative(row.strength);}
        });
    }
    for(unsigned i=0;i<descriptors.size();++i)if(!mapped[i]) {
        const auto& d=descriptors[i];
        if(patch&&int(i)==changed&&changed_dead) {
            auto& row=out.members[i];row.visible=false;row.known=true;row.alive=false;row.awake=false;
            row.hp=0;row.hp_known=true;row.hp_epoch=row.state_epoch=start;row.unchanged_event=0;continue;
        }
        if((!d.passive&&distance(d.last,own.pos)<=d.range+5)||d.group==selected_group) {
            try {
                auto status=read([&]{return d.handle.state();});
                if(status.is_dead()){out.members[i].known=true;out.members[i].alive=false;out.members[i].hp_known=true;
                    out.members[i].hp_epoch=out.members[i].state_epoch=start;}
            } catch(const cambc::error& e) {
                if(e.code()!=error_code::api_not_found&&e.code()!=error_code::api_not_in_vision)throw;
                turn.check();
            }
        }
    }
    auto champions=[&](const auto& positions,bool enemy,std::vector<Champion>& rows) {
        for(auto p:positions) {
            auto c=read([&]{return vision::champion_at(p);});
            if(id(c)==id(me)) {
                if(enemy||point(p)!=own.pos)throw SceneCapacity{};
                continue;
            }
            for(const auto& row:rows)if(row.key==id(c))throw SceneCapacity{};
            champion_state flags;Champion row;
            // Seven getters at most, including the optional channel timer.
            turn.capture_reads([&](auto& batch) {
            flags=batch.read([&]{return c.state();});
            row.key=id(c);row.pos=point(p);row.alive=flags.contains(champion_state::alive);
            row.hp=batch.read([&]{return c.health();});row.max_hp=batch.read([&]{return c.max_health();});
            row.range=batch.read([&]{return c.attack_range();});
            row.move_range=batch.read([&]{return c.base_stats();}).base_move_speed;
            row.channel=flags.contains(champion_state::recalling)||flags.contains(champion_state::teleporting)||flags.contains(champion_state::submitting_gems);
            row.departing=flags.contains(champion_state::recalling)||flags.contains(champion_state::teleporting);
            if(row.channel)row.timer=batch.read([&]{return c.remaining_channel_time();});
            if(!enemy)row.bag=batch.read([&]{return c.gem_count();});
            if(enemy)row.strength=batch.read([&]{return c.strength();});
            });
            nonnegative(row.hp);nonnegative(row.max_hp);nonnegative(row.strength);
            if(row.range<0||row.move_range<0||row.range>16384||row.move_range>16384)throw SceneCapacity{};
            rows.push_back(row);
        }
    };
    champions(enemy_positions,true,out.enemies);champions(ally_positions,false,out.allies);
    out.groups.resize(geometry->groups.size());
    out.economy.groups.reserve(geometry->groups.size());
    for(unsigned g=0;g<world.camps.size();++g) {
        const auto& objective=world.camps[g];auto& group=out.groups[g];
        const auto& metadata=geometry->groups[g];
        auto& row=group.observation;row.object=int(g);row.cycle=cycles[g];
        bool visible_spawn=false;
        for(auto p:metadata.spawn) {
            visible_spawn|=out.seen(p);
            if(p==own.pos)row.self_occupant=true;
        }
        if(visible_spawn) {
            try {
                auto status=read([&]{return objective.group.state();});
                row.life=std::holds_alternative<map::camp_group_alive>(status)?Life::living:
                    std::holds_alternative<map::camp_group_reward_available>(status)?Life::reward:Life::respawning;
                if(lifecycle[g]==Life::respawning&&row.life!=Life::respawning)++next_cycles[g];
                row.cycle=next_cycles[g];row.fresh=true;
                if(row.life==Life::reward) {
                    const auto capture=read([&]{return objective.group.capture_state();});row.capture_timer=capture.timer;
                    row.contested=capture.state==map::camp_group_capture_type::contested||capture.state==map::camp_group_capture_type::enemy_capturing;
                    int latest=0;bool holder_without_departure=false;
                    std::uint64_t fact=combine(1469598103934665603ull,unsigned(row.cycle));
                    for(const auto& a:out.allies)if(a.alive&&std::find(metadata.spawn.begin(),metadata.spawn.end(),a.pos)!=metadata.spawn.end()) {
                        row.allied_holder=true;holder_without_departure|=!a.departing;
                        if(a.departing)latest=std::max(latest,a.timer);
                        fact=combine(fact,unsigned(a.key));fact=combine(fact,unsigned(a.departing));
                    }
                    row.holder_departing=row.allied_holder&&!holder_without_departure;
                    row.earliest_departure=latest;row.role_fact=fact;
                }
            }catch(const cambc::error& e) {
                if(e.code()!=error_code::api_not_in_vision&&e.code()!=error_code::api_not_found)throw;
                turn.check();row.life=Life::unknown;row.fresh=false;
            }
        }
        out.economy.groups.push_back(row);
    }
    const auto locks=read([]{return vision::altar_locks();});
    if(locks.size()>world.altars.size())throw SceneCapacity{};
    for(const auto& lock:locks) {
        const auto p=lock.position();
        if(std::find(world.altars.begin(),world.altars.end(),p)==world.altars.end()||
            lock.hits_remaining()<=0||unsigned(lock.hits_remaining())>constants::altar_lock_hits)throw SceneCapacity{};
        for(const auto& existing:out.locks)if(existing.pos==point(p))throw SceneCapacity{};
        out.locks.push_back({point(p),lock.team()==team::ally,unsigned(lock.hits_remaining())});
    }
    for(auto p:world.altars)out.altars.push_back(point(p));
    float incoming=0;int enemies=0,friends=1;bool camp_hit=false;
    for(const auto& e:out.enemies)if(e.alive) {
        if(distance(e.pos,own.pos)<=6)++enemies;
        if(distance(e.pos,own.pos)<=e.range)incoming+=e.strength;
    }
    for(const auto& a:out.allies)if(a.alive&&!a.channel&&distance(a.pos,own.pos)<=4)++friends;
    for(const auto& c:out.members)if(c.known&&c.alive&&c.awake&&!c.passive&&distance(c.pos,own.pos)<=c.range) {
        incoming+=c.strength;camp_hit=true;
    }
    own.danger=(enemies>0&&(enemies>friends||own.hp<=own.max_hp*Config::recovery_low))||
        (camp_hit&&own.hp<=own.max_hp*Config::recovery_low)||incoming>=own.hp;
    // Complete potentially allocating history copies before the publication
    // guard; prior/frozen Scenes and the old patch history stay independent.
    History next_history{own,out.visible,out.occupied,out.members,out.allies,out.enemies};
    turn.check();if(turn.epoch()!=start)throw TurnExpired{};
    // Publish dynamic cache changes only after the entire scene is coherent.
    for(unsigned i=0;i<descriptors.size();++i)if(out.members[i].visible)descriptors[i].last=out.members[i].pos;
    for(unsigned g=0;g<out.groups.size();++g)if(out.groups[g].observation.fresh)lifecycle[g]=out.groups[g].observation.life;
    cycles=std::move(next_cycles);
    out.economy.complete=true;previous=std::move(next_history);cached=true;return out;
}
}
