#include "recovery_sdk.h"
#include "recovery_tiles.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>
namespace lp {
namespace {
using namespace recovery;
Point point(vec2 p){return {p.x,p.y};}
vec2 tile(Point p){return {p.x,p.y};}
// LOCAL DIAGNOSTIC EXPERIMENT: preserve the original public enumeration scope.
struct CampPairs {
    std::vector<camp> handles;
    std::vector<Point> positions;
    bool overflow=false;
};
CampPairs visible_camp_pairs() {
    CampPairs out;
    const auto coordinates=vision::camp_tiles().positions();
    const auto capacity=std::min(coordinates.size(),std::size_t(Limits::camps));
    out.handles.reserve(capacity);out.positions.reserve(capacity);
    for(auto p:coordinates) {
        auto handle=vision::camp_at(p);
        // Complete every public lookup/metadata load even beyond capacity.
        if(out.handles.size()<Limits::camps){out.handles.push_back(handle);out.positions.push_back(point(p));}
        else out.overflow=true;
    }
    return out;
}
std::uint32_t camp_key(const camp& c){return static_cast<std::uint32_t>(static_cast<handle_camp_t>(c));}
struct CampLookup {std::uint32_t key;unsigned index;};
// Ephemeral identity lookup only. No dynamic observations survive capture.
struct CampJoin {
    const std::vector<camp>& camps;
    std::array<std::uint16_t,512> first;
    std::array<CampLookup,Limits::camps> sorted;
    bool hashed=true,sorted_ready=false;
    static unsigned bucket(std::uint32_t key){return (key*0x9e3779b9u)>>23;}
    explicit CampJoin(const std::vector<camp>& values):camps(values) {
        if(camps.empty())return;
        first.fill(0);
        for(unsigned i=0;i<camps.size();++i) {
            auto key=camp_key(camps[i]);unsigned slot=bucket(key);bool inserted=false;
            for(unsigned probe=0;probe<8;++probe) {
                auto ordinal=first[slot];
                if(!ordinal){first[slot]=std::uint16_t(i+1);inserted=true;break;}
                if(camp_key(camps[ordinal-1])==key){inserted=true;break;}
                slot=(slot+1)&511u;
            }
            if(!inserted){hashed=false;break;}
        }
    }
    void sort() {
        if(sorted_ready)return;
        for(unsigned i=0;i<camps.size();++i)sorted[i]={camp_key(camps[i]),i};
        std::sort(sorted.begin(),sorted.begin()+camps.size(),[](auto a,auto b){
            return a.key<b.key||(a.key==b.key&&a.index<b.index);
        });
        sorted_ready=true;
    }
    int at(std::uint32_t key) {
        if(camps.empty())return -1;
        if(hashed) {
            unsigned slot=bucket(key);
            for(unsigned probe=0;probe<8;++probe) {
                auto ordinal=first[slot];if(!ordinal)return -1;
                if(camp_key(camps[ordinal-1])==key)return int(ordinal)-1;
                slot=(slot+1)&511u;
            }
            // Never omit a result on overflow: switch this whole join to the
            // original exact sorted algorithm, including first-visible ties.
            hashed=false;
        }
        sort();auto end=sorted.begin()+camps.size();
        auto found=std::lower_bound(sorted.begin(),end,key,[](auto entry,auto value){return entry.key<value;});
        return found==end||found->key!=key?-1:int(found->index);
    }
};
struct LiveBackend final:Backend {
    World& world;Memory& memory;TurnBudget& budget;RecoveryRuntime& cache;LiveTurn& dispatch;
    Epoch turn;int queries=0;
    LiveBackend(World& w,Memory& m,TurnBudget& b,RecoveryRuntime& c,LiveTurn& d):world(w),memory(m),budget(b),cache(c),dispatch(d) {
        turn={id(self()),m.life,b.round,observation_version()};
    }
    Epoch epoch()override{return {id(self()),memory.life,int(round_number()),observation_version()};}
    bool current(Epoch e)override{return epoch()==e;}
    void check(){if(!budget.current()||id(self())!=turn.actor||memory.life!=turn.life)throw Halt{Status::stale};
        if(fuel_remaining()<Config::reserve)throw Halt{Status::incomplete};}
    template<class F> auto query(F f) {
        check();if(++queries>Limits::queries)throw Halt{Status::incomplete};
        auto value=dispatch.read(f);check();return value;
    }
    std::vector<unsigned char> scalar(const bitboard& board,int width,int height) {
        check();const Epoch conversion=epoch();
        scalar_cells(width,height); // Reject unsupported dimensions before any export.
        auto coordinates=query([&]{return board.positions();});
        auto bytes=scalar_tiles(width,height,coordinates);
        check();if(!current(conversion))throw Halt{Status::stale};
        return bytes;
    }
    Status prepare(Epoch)override {
        check();
        if(!cache.initialized) {
            // Public cached World groups own membership. This makes no camp_group() calls.
            if(world.camps.size()>Limits::groups)return Status::incomplete;
            std::vector<RecoveryRuntime::Member> members;
            std::vector<std::pair<camp_type,int>> ranges;
            for(int g=0;g<int(world.camps.size());++g)for(auto c:world.camps[g].group.camps()) {
                if(members.size()>=Limits::camps)return Status::incomplete;
                auto found=std::find_if(ranges.begin(),ranges.end(),[&](auto entry){return entry.first==c.kind();});
                int range;
                if(found==ranges.end()){range=query([&]{return c.attack_range();});ranges.push_back({c.kind(),range});}
                else range=found->second;
                members.push_back({c,g,c.spawn_position(),range});
            }
            cache.members=std::move(members);cache.initialized=true;
        }
        if(!cache.terrain) {
            scalar_cells(world.width,world.height);
            if(!budget.admit())return Status::initialization_deferred;
            auto terrain=std::make_shared<Terrain>();terrain->width=world.width;terrain->height=world.height;
            auto blocked=query([]{return static_blocked();});auto spawn=query([]{return map::spawn_region(team::ally);});
            terrain->blocked=scalar(blocked,world.width,world.height);
            terrain->spawn=scalar(spawn,world.width,world.height);
            // Full static field and export may resume next round: retain only completed static work.
            ++budget.fields;distance_field field;bitboard visited;
            field.compute(blocked,spawn,visited);
            terrain->home=field.export_linear_buffer();
            if(terrain->home.size()!=std::size_t(scalar_cells(world.width,world.height)))throw Halt{Status::incomplete};
            cache.terrain=std::move(terrain);
            check();
        }
        return Status::ready;
    }
    Status capture(Scene& s)override {
        check();
        if(budget.ledger.recovery_captures>=Limits::captures)return Status::incomplete;
        ++budget.ledger.recovery_captures;++budget.ledger.captures;
        queries=0;check();s.epoch=epoch();s.terrain=cache.terrain;
        auto& me=self();auto state=query([&]{return me.state();});
        s.alive=state.contains(champion_state::alive);
        if(!s.alive)return Status::defensive_wait;
        s.completed=state.contains(champion_state::completed_turn);
        s.can_move=state.contains(champion_state::can_move);s.can_cast=state.contains(champion_state::can_cast)&&budget.ledger.casts==0;
        s.recalling=state.contains(champion_state::recalling);s.tribute=state.contains(champion_state::submitting_gems);
        s.teleport=state.contains(champion_state::teleporting);
        s.pos=point(query([&]{return me.position();}));s.hp=query([&]{return me.health();});s.max_hp=query([&]{return me.max_health();});
        auto restrictions=query([&]{return me.restrictions();});
        s.move_restricted=restrictions.contains(buff_restrictions::move);s.cast_restricted=restrictions.contains(buff_restrictions::cast);
        s.stunned=query([&]{return me.buffs().has_stun();});
        if(s.recalling)s.timer=query([&]{return me.remaining_channel_time();});
        budget.ledger.channel_history(state.contains(champion_state::recall_started),state.contains(champion_state::recall_cancelled),state.contains(champion_state::submit_gems_started));
        s.recall_started=budget.ledger.recall_attempted;
        s.recall_cancelled=budget.ledger.cancel_attempted;
        s.movement_spent=budget.ledger.steps>0;
        s.step_attempted=budget.ledger.step_attempted;s.dash_attempted=budget.ledger.dash_attempted;
        auto visible=query([]{return vision::visible_tiles();});s.visible=scalar(visible,s.terrain->width,s.terrain->height);
        auto occupancy=query([]{return vision::champion_tiles()|vision::camp_tiles()|vision::teleport_tiles();});
        s.occupied=scalar(occupancy,s.terrain->width,s.terrain->height);
        const auto cells=s.terrain->width*s.terrain->height;
        if(!s.terrain->inside(s.pos)||int(s.visible.size())!=cells||int(s.occupied.size())!=cells)return Status::incomplete;
        s.occupied[s.terrain->index(s.pos)]=0;
        auto enemies=query([]{return vision::champions(team::enemy);});
        if(enemies.size()>Limits::enemies)return Status::incomplete;
        for(auto e:enemies) {
            Threat t;t.pos=point(query([&]{return e.position();}));t.range=query([&]{return e.attack_range();});t.strength=query([&]{return e.strength();});
            s.enemies.push_back(t);
        }
        auto abilities=query([&]{return me.abilities();});int ready_dashes=0;
        if(abilities.size()>Limits::abilities)return Status::incomplete;
        for(int slot=0;slot<int(abilities.size());++slot) {
            auto a=abilities[slot];if(!a.is_dash())continue;
            auto data=query([&]{return a.get<ability_dash>();});auto cooldown=query([&]{return a.cooldown();});
            bool supported=!data.exclusive_with_movement&&std::isfinite(data.range)&&data.range>=1&&data.range<=2&&
                std::floor(data.range)==data.range&&std::isfinite(data.radius)&&data.radius>=0&&data.radius<=Limits::effect_radius&&
                std::floor(data.radius)==data.radius&&std::isfinite(data.modifier)&&data.modifier>=0&&data.duration>=0;
            if(cooldown==0&&supported) {
                if(++ready_dashes>1)return Status::incomplete;
                s.dash={true,true,data.modifier>0,data.duration>0,int(data.range),int(data.radius),slot};
            }
        }
        auto pairs=query([]{return visible_camp_pairs();});if(pairs.overflow)return Status::incomplete;
        const auto& camps=pairs.handles;const auto& positions=pairs.positions;
        s.groups=int(world.camps.size());
        // Capture positions once, then scalar membership/relevance. No per-endpoint SDK work.
        std::vector<int> visible_member(cache.members.size(),-1);
        // The removed first position query checked again after enumeration's
        // postcheck tail. Preserve that barrier before publishing member.last.
        if(!camps.empty())check();
        CampJoin lookup(camps);
        std::vector<bool> effect_groups(s.groups,false);unsigned mapped=0;
        for(unsigned i=0;i<cache.members.size();++i) {
            auto key=camp_key(cache.members[i].handle);
            int v=lookup.at(key);if(v<0)continue;
            ++mapped;visible_member[i]=v;
            cache.members[i].last=tile(positions[v]);
            if(s.dash.available&&(s.dash.damage||s.dash.stun)&&distance(positions[v],s.pos)<=5)
                effect_groups[cache.members[i].group]=true;
        }
        if(mapped!=camps.size())return Status::incomplete;
        for(unsigned i=0;i<cache.members.size();++i) {
            auto& member=cache.members[i];Camp c;c.pos=point(member.last);c.group=member.group;c.range=member.range;
            bool relevant=distance(c.pos,s.pos)<=member.range+5||effect_groups[c.group];
            if(visible_member[i]>=0&&relevant) {
                auto handle=camps[visible_member[i]];
                auto state=query([&]{return handle.state();});c.known=true;c.alive=state.is_alive();c.awake=state.is_awake();
                if(c.alive)c.strength=query([&]{return handle.strength();});
            } else if(relevant&&s.terrain->inside(c.pos)&&s.visible[s.terrain->index(c.pos)]) {
                // A remembered tile being visible is necessary; a moved hidden member remains unknown.
                try {auto state=query([&]{return member.handle.state();});if(state.is_dead())c.known=true;}
                catch(const cambc::error& e){check();if(e.code()!=error_code::api_not_in_vision&&e.code()!=error_code::api_not_found)throw;}
            }
            s.camps.push_back(c);
        }
        check();if(!current(s.epoch))return Status::stale;
        auto& pending=budget.ledger.pending;
        if(pending.event&&!pending.after_observed)
            budget.ledger.observe(pending.event,dispatch.epoch(),s.tribute);
        if(!budget.current())return Status::stale;
        return Status::ready;
    }
    // Re-query exact permission flags directly before every issuance, including after cancellation.
    bool preflight(const Scene& s,Kind kind) {
        check();if(!current(s.epoch))throw Halt{Status::stale};
        auto& me=self();auto state=query([&]{return me.state();});
        if(!state.contains(champion_state::alive)||state.contains(champion_state::completed_turn)||
            state.contains(champion_state::submitting_gems)||state.contains(champion_state::teleporting))return false;
        bool recalling=state.contains(champion_state::recalling);
        if(query([&]{return me.buffs().has_stun();}))return false;
        if(kind==Kind::cancel)return recalling&&!state.contains(champion_state::recall_cancelled);
        if(recalling)return false;
        auto r=query([&]{return me.restrictions();});
        if(kind==Kind::step)return state.contains(champion_state::can_move)&&!r.contains(buff_restrictions::move);
        if(kind==Kind::dash)return state.contains(champion_state::can_cast)&&!r.contains(buff_restrictions::move)&&!r.contains(buff_restrictions::cast);
        if(kind==Kind::recall)return !state.contains(champion_state::recall_started)&&!state.contains(champion_state::recall_cancelled);
        return true;
    }
    action::Request request(const Scene& s,action::Op op) {
        return {{s.epoch.actor,s.epoch.life,s.epoch.round,s.epoch.revision},op,{}};
    }
    bool issue(const Scene& s,Action selected)override {
        auto& me=self();std::optional<ability> dash;
        auto op=selected.kind==Kind::step?action::Op::step:
            selected.kind==Kind::dash?action::Op::dash:
            selected.kind==Kind::cancel?action::Op::cancel_recall:action::Op::recall;
        auto r=request(s,op);r.target.x=selected.target.x;r.target.y=selected.target.y;r.target.slot=selected.slot;
        auto result=dispatch.perform(r,[&] {
            if(!preflight(s,selected.kind))return false;
            if(selected.kind!=Kind::dash)return true;
            auto abilities=query([&]{return me.abilities();});
            if(selected.slot<0||selected.slot>=int(abilities.size()))return false;
            auto candidate=abilities[selected.slot];if(!candidate.is_dash())return false;
            auto data=query([&]{return candidate.get<ability_dash>();});
            auto cooldown=query([&]{return candidate.cooldown();});
            if(cooldown||data.exclusive_with_movement||!s.dash.supported)return false;
            dash=candidate;check();return true;
        },[&] {
            if(selected.kind==Kind::step)return me.move_absolute(tile(selected.target));
            if(selected.kind==Kind::dash)return dash->use(tile(selected.target));
            if(selected.kind==Kind::cancel){me.cancel_recall();return true;}
            me.recall();return true;
        });
        return result.accepted();
    }
    bool defend(const Scene& s)override {
        if(!preflight(s,Kind::stay))return false;
        auto& me=self();
        // A bounded primitive adapter: preserve shield and ally-heal priorities, then one enemy basic attack.
        auto abilities=query([&]{return me.abilities();});
        if(abilities.size()>Limits::abilities)throw Halt{Status::incomplete};
        if(s.can_cast&&!s.cast_restricted&&query([&]{return me.can_cast();}))for(auto a:abilities) {
            if(!query([&]{return ready(a);}))continue;
            float exposure=0;for(auto e:s.enemies)if(distance(e.pos,s.pos)<=e.range)exposure+=e.strength;
            for(auto c:s.camps)if(c.known&&c.alive&&c.awake&&distance(c.pos,s.pos)<=c.range)exposure+=c.strength;
            if(a.is_shield()&&exposure>0&&s.hp<s.max_hp*0.7f) {
                if(!preflight(s,Kind::stay))return false;
                return dispatch.perform(request(s,action::Op::shield),
                    [&]{return preflight(s,Kind::stay);},[&]{return a.use();}).accepted();
            }
            if(a.is_heal()) {
                auto allies=query([]{return vision::champions(team::ally);});if(allies.size()>Limits::enemies)throw Halt{Status::incomplete};
                auto tiles=query([&]{return a.valid_tiles();});auto valid=scalar(tiles,s.terrain->width,s.terrain->height);
                std::optional<champion> target;float best=0;
                for(auto ally:allies)if(id(ally)!=id(me)) {
                    auto p=point(query([&]{return ally.position();}));float hp=query([&]{return ally.health();});float max=query([&]{return ally.max_health();});
                    if(valid[s.terrain->index(p)]&&hp<max*0.75f) {
                        float value=query([&]{return a.heal_amount(ally);});float incoming=0;
                        for(auto e:s.enemies)if(distance(e.pos,p)<=e.range)incoming+=e.strength;
                        for(auto c:s.camps)if(c.known&&c.alive&&c.awake&&distance(c.pos,p)<=c.range)incoming+=c.strength;
                        if(incoming>=hp)value+=10000;
                        if(value>best){best=value;target=ally;}
                    }
                }
                if(target)return dispatch.perform(request(s,action::Op::heal),
                    [&]{return preflight(s,Kind::stay);},[&]{return a.use(*target);}).accepted();
            }
        }
        if(query([&]{return me.can_attack();})) {
            auto attack=query([&]{return me.attack_tiles();});auto valid=scalar(attack,s.terrain->width,s.terrain->height);
            auto foes=query([]{return vision::champions(team::enemy);});if(foes.size()>Limits::enemies)throw Halt{Status::incomplete};
            std::optional<champion> target;float lowest=1e30f;
            for(auto foe:foes) {
                auto p=point(query([&]{return foe.position();}));auto hp=query([&]{return foe.health();});
                if(valid[s.terrain->index(p)]&&hp<lowest){target=foe;lowest=hp;}
            }
            if(target){if(!preflight(s,Kind::stay)||!query([&]{return me.can_attack();}))return false;
                return dispatch.perform(request(s,action::Op::basic),
                    [&]{return preflight(s,Kind::stay)&&query([&]{return me.can_attack();});},
                    [&]{me.attack(*target);}).accepted();}
        }
        return false;
    }
};
}
recovery::Outcome recover(recovery::Intent intent,World& world,Memory& memory,TurnBudget& budget,RecoveryRuntime& cache,LiveTurn& turn) {
    try {
        if(!budget.ledger.handoff(action::Owner::recovery,turn.epoch()))return {recovery::Status::stale};
        LiveBackend backend(world,memory,budget,cache,turn);return recovery::execute(intent,memory,backend);
    } catch(const TurnExpired&) {return {recovery::Status::stale};}
      catch(const TurnDeferred&) {return {recovery::Status::incomplete};}
}
}
