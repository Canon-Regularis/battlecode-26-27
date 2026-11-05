#include "recovery_sdk.h"
#include <cmath>
#include <optional>
namespace lp {
namespace {
using namespace recovery;
Point point(vec2 p){return {p.x,p.y};}
vec2 tile(Point p){return {p.x,p.y};}
struct LiveBackend final:Backend {
    World& world;Memory& memory;TurnBudget& budget;RecoveryRuntime& cache;
    Epoch turn;int queries=0;
    LiveBackend(World& w,Memory& m,TurnBudget& b,RecoveryRuntime& c):world(w),memory(m),budget(b),cache(c) {
        turn={id(self()),m.life,b.round,observation_version()};
        if(cache.action_round!=b.round||cache.action_life!=m.life){cache.action_round=b.round;cache.action_life=m.life;cache.recall_started=cache.recall_cancelled=cache.movement_spent=false;}
    }
    Epoch epoch()override{return {id(self()),memory.life,int(round_number()),observation_version()};}
    bool current(Epoch e)override{return epoch()==e;}
    void check(){if(!budget.current()||id(self())!=turn.actor||memory.life!=turn.life)throw Halt{Status::stale};
        if(fuel_remaining()<Config::reserve)throw Halt{Status::incomplete};}
    template<class F> auto query(F f) {
        check();if(++queries>Limits::queries)throw Halt{Status::incomplete};
        auto value=f();check();return value;
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
            if(world.width<=0||world.height<=0||world.width*world.height>Limits::cells)return Status::incomplete;
            if(!budget.admit())return Status::initialization_deferred;
            auto terrain=std::make_shared<Terrain>();terrain->width=world.width;terrain->height=world.height;
            auto blocked=query([]{return static_blocked();});auto spawn=query([]{return map::spawn_region(team::ally);});
            terrain->blocked=query([&]{return blocked.export_linear_buffer();});
            terrain->spawn=query([&]{return spawn.export_linear_buffer();});
            // Full static field and export may resume next round: retain only completed static work.
            ++budget.fields;distance_field field;bitboard visited;
            field.compute(blocked,spawn,visited);
            terrain->home=field.export_linear_buffer();
            cache.terrain=std::move(terrain);
            check();
        }
        return Status::ready;
    }
    Status capture(Scene& s)override {
        queries=0;check();s.epoch=epoch();s.terrain=cache.terrain;
        auto& me=self();auto state=query([&]{return me.state();});
        s.alive=state.contains(champion_state::alive);
        if(!s.alive)return Status::defensive_wait;
        s.completed=state.contains(champion_state::completed_turn);
        s.can_move=state.contains(champion_state::can_move);s.can_cast=state.contains(champion_state::can_cast);
        s.recalling=state.contains(champion_state::recalling);s.tribute=state.contains(champion_state::submitting_gems);
        s.teleport=state.contains(champion_state::teleporting);
        s.pos=point(query([&]{return me.position();}));s.hp=query([&]{return me.health();});s.max_hp=query([&]{return me.max_health();});
        auto restrictions=query([&]{return me.restrictions();});
        s.move_restricted=restrictions.contains(buff_restrictions::move);s.cast_restricted=restrictions.contains(buff_restrictions::cast);
        s.stunned=query([&]{return me.buffs().has_stun();});
        if(s.recalling)s.timer=query([&]{return me.remaining_channel_time();});
        s.recall_started=cache.recall_started||state.contains(champion_state::recall_started);
        s.recall_cancelled=cache.recall_cancelled||state.contains(champion_state::recall_cancelled);
        s.movement_spent=cache.movement_spent;
        auto visible=query([]{return vision::visible_tiles();});s.visible=query([&]{return visible.export_linear_buffer();});
        auto occupancy=query([]{return vision::champion_tiles()|vision::camp_tiles()|vision::teleport_tiles();});
        s.occupied=query([&]{return occupancy.export_linear_buffer();});
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
        auto camps=query([]{return vision::camps();});if(camps.size()>Limits::camps)return Status::incomplete;
        s.groups=int(world.camps.size());
        // Capture positions once, then scalar membership/relevance. No per-endpoint SDK work.
        std::vector<int> visible_member(cache.members.size(),-1);
        std::vector<Point> positions;positions.reserve(camps.size());
        for(auto c:camps)positions.push_back(point(query([&]{return c.position();})));
        std::vector<bool> effect_groups(s.groups,false);unsigned mapped=0;
        for(unsigned i=0;i<cache.members.size();++i) {
            auto found=std::find(camps.begin(),camps.end(),cache.members[i].handle);
            if(found==camps.end())continue;
            ++mapped;int v=int(found-camps.begin());visible_member[i]=v;
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
        if(kind==Kind::cancel)return recalling&&!cache.recall_cancelled&&!state.contains(champion_state::recall_cancelled);
        if(recalling)return false;
        auto r=query([&]{return me.restrictions();});
        if(kind==Kind::step)return state.contains(champion_state::can_move)&&!r.contains(buff_restrictions::move);
        if(kind==Kind::dash)return state.contains(champion_state::can_cast)&&!r.contains(buff_restrictions::move)&&!r.contains(buff_restrictions::cast);
        if(kind==Kind::recall)return !cache.recall_started&&!cache.recall_cancelled&&!state.contains(champion_state::recall_started)&&!state.contains(champion_state::recall_cancelled);
        return true;
    }
    bool issue(const Scene& s,Action action)override {
        if(!preflight(s,action.kind))return false;
        auto& me=self();bool success=false;
        if(action.kind==Kind::step)success=me.move_absolute(tile(action.target));
        else if(action.kind==Kind::dash) {
            auto abilities=query([&]{return me.abilities();});
            if(action.slot<0||action.slot>=int(abilities.size()))return false;
            auto a=abilities[action.slot];if(!a.is_dash())return false;
            auto data=query([&]{return a.get<ability_dash>();});auto cooldown=query([&]{return a.cooldown();});
            if(cooldown||data.exclusive_with_movement||!s.dash.supported)return false;
            check();success=a.use(tile(action.target));
        } else if(action.kind==Kind::cancel) {
            cache.recall_cancelled=true;me.cancel_recall();success=true;
        } else if(action.kind==Kind::recall) {
            cache.recall_started=true;me.recall();success=true;
        }
        if(success&&action.kind==Kind::step)cache.movement_spent=true;
        invalidate_observations();return success;
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
                bool success=a.use();invalidate_observations();return success;
            }
            if(a.is_heal()) {
                auto allies=query([]{return vision::champions(team::ally);});if(allies.size()>Limits::enemies)throw Halt{Status::incomplete};
                auto tiles=query([&]{return a.valid_tiles();});auto valid=query([&]{return tiles.export_linear_buffer();});
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
                if(target){if(!preflight(s,Kind::stay))return false;bool success=a.use(*target);invalidate_observations();return success;}
            }
        }
        if(query([&]{return me.can_attack();})) {
            auto attack=query([&]{return me.attack_tiles();});auto valid=query([&]{return attack.export_linear_buffer();});
            auto foes=query([]{return vision::champions(team::enemy);});if(foes.size()>Limits::enemies)throw Halt{Status::incomplete};
            std::optional<champion> target;float lowest=1e30f;
            for(auto foe:foes) {
                auto p=point(query([&]{return foe.position();}));auto hp=query([&]{return foe.health();});
                if(valid[s.terrain->index(p)]&&hp<lowest){target=foe;lowest=hp;}
            }
            if(target){if(!preflight(s,Kind::stay)||!query([&]{return me.can_attack();}))return false;
                me.attack(*target);invalidate_observations();return true;}
        }
        return false;
    }
};
}
recovery::Outcome recover(recovery::Intent intent,World& world,Memory& memory,TurnBudget& budget,RecoveryRuntime& cache) {
    LiveBackend backend(world,memory,budget,cache);return recovery::execute(intent,memory,backend);
}
}
