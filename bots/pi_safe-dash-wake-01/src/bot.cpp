#include "bot.h"
#include "route_plan.h"
#include <span>
#include <tuple>
using namespace lp;
std::uint64_t Bot::shared_read() const {
    std::array<std::byte,8> bytes{};shared_memory.read(0,bytes);std::uint64_t w=0;
    for(int i=0;i<8;++i)w|=std::uint64_t(std::to_integer<unsigned>(bytes[i]))<<(8*i);return w;
}
void Bot::shared_write(std::uint64_t w,int r) {
    if(int(round_number())!=r||fuel_remaining()<Config::reserve)return;
    std::array<std::byte,8> bytes{};for(int i=0;i<8;++i)bytes[i]=std::byte((w>>(8*i))&255);shared_memory.write(0,bytes);
}
bool Bot::coordinate(const Snapshot& s) {
    if(!Config::coordination)return false;
    auto w=shared_read();
    if(!wire::get(w,wire::initialized,1)&&world.slot==0&&s.round<=2000){shared_write(wire::empty(),s.round);w=shared_read();}
    if(!wire::valid(w,s.round))return false;
    int leader=wire::get(w,wire::leader,3);bool stale=!wire::leader_live(w,s.round,world.roster.size());
    if(leader<int(world.roster.size())&&!world.roster[leader].is_alive())stale=true;
    bool eligible=s.alive&&s.hp>s.max_hp*0.5f&&!memory.recovering&&memory.state!=State::escape;
    if(stale)w=wire::put(w,wire::leader,3,7);
    if(wire::get(w,wire::leader,3)==unsigned(world.slot)&&!eligible)w=wire::put(w,wire::leader,3,7);
    if(wire::get(w,wire::leader,3)==7&&eligible&&world.preference[s.round%world.preference.size()]==world.slot)w=wire::put(w,wire::leader,3,world.slot);
    if(wire::get(w,wire::leader,3)==unsigned(world.slot))w=wire::put(w,wire::heartbeat,11,s.round);
    if(wire::get(w,wire::type,2)) {
        int owner=wire::get(w,wire::owner,3);
        if(!wire::live(w,s.round,world.roster.size(),world.columns*world.rows)||(owner<int(world.roster.size())&&!world.roster[owner].is_alive()))w=wire::clear(w);
    }
    shared_write(w,s.round);return wire::get(w,wire::leader,3)==unsigned(world.slot);
}
void Bot::publish(const Snapshot& s,bool leader) {
    if(!Config::coordination||fuel_remaining()<16000||int(round_number())!=s.round)return;
    auto w=shared_read();if(!wire::valid(w,s.round))return;
    int safety=!s.alive||memory.state==State::recall||memory.state==State::healing?3:
        memory.state==State::escape||memory.state==State::defend?2:
        memory.task>=0||memory.state==State::prepare_bank||memory.state==State::bank||memory.state==State::protect?1:0;
    w=wire::put(w,wire::safety+2*world.slot,2,safety);
    if(leader&&wire::get(w,wire::leader,3)==unsigned(world.slot)) {
        vec2 anchor=s.pos;unsigned message=1;
        if(memory.task>=0){anchor=world.camps[memory.task].anchor;message=memory.state==State::protect?3:2;}
        if(memory.altar>=0&&(memory.state==State::bank||memory.state==State::prepare_bank)){anchor=world.altars[memory.altar];message=memory.state==State::bank?5:4;}
        w=wire::put(w,wire::anchor,6,world.chunk(anchor));w=wire::put(w,wire::message,3,message);w=wire::put(w,wire::heartbeat,11,s.round);
    }
    bool wantsbank=s.alive&&s.bag>0&&(memory.state==State::prepare_bank||memory.state==State::bank)&&memory.altar>=0;
    if(memory.owned&&wire::same(w,memory.owned)&&!wantsbank){w=wire::clear(w);memory.rally_retry=s.round+3;memory.owned=0;}
    if(wantsbank&&!wire::get(w,wire::type,2)&&memory.last_created!=s.round&&s.round>=memory.rally_retry) {
        w=wire::create(w,world.slot,s.round,1,world.chunk(world.altars[memory.altar]));memory.owned=w;memory.last_created=s.round;memory.rally_retry=s.round+15;
    }
    shared_write(w,s.round);
}
void Bot::abandon(int r) {
    advance_loop(world,memory.task);
    if(memory.task>=0)world.camps[memory.task].cooldown=r+Config::retry;
    memory.task=-1;memory.carrier=-1;memory.protection_started=0;memory.blocked=0;memory.last_distance=65535;
}
Facts Bot::facts(const Snapshot& s,bool leader) {
    Facts f;f.alive=s.alive;if(!s.alive)return f;
    auto& me=self();f.hp=s.hp;f.max_hp=s.max_hp;f.spawn=s.spawn;
    f.tribute=me.is_submitting_gems();f.teleport=me.is_teleporting();f.recalling=me.is_recalling();
    f.enemy_visible=!s.foes.empty();f.camp_hit=s.camp_hit;
    // Nearby vision across a wall is not a reason to defend spawn forever.
    f.threatened=s.incoming>0||s.camp_hit;
    f.danger=(s.enemies>0&&(s.enemies>s.friends||s.hp<=s.max_hp*Config::recovery_low))||(s.camp_hit&&s.hp<=s.max_hp*Config::recovery_low)||s.incoming>=s.hp;
    if(s.hp<=s.max_hp*Config::recovery_low)memory.recovering=true;if(s.hp>=s.max_hp*Config::recovery_high)memory.recovering=false;
    f.recovery=memory.recovering||(!s.spawn&&s.bag==0&&s.foes.empty()&&me.gold_count()>=Config::recall_gold);
    f.bank_needed=(memory.altar>=0&&s.bag>0)||bank_due(s.bag,memory.bag_since,s.round,global_submitted_gems(team::ally));
    if(memory.task>=0) {
        const auto& o=world.camps[memory.task];f.camp_valid=o.lifecycle!=3||o.respawn<=s.round;
        f.reward=o.lifecycle==2&&o.seen==s.round;
        if(f.reward)for(const auto& a:s.allies)if(o.tiles.is_set(a.position()))f.occupied=true;
    }
    f.leader=leader;f.bank_protect=memory.carrier>=0;return f;
}
void Bot::camp_action(TurnBudget& b) {
    if(memory.task<0)return;
    auto& o=world.camps[memory.task];const auto& s=observe();auto& me=self();
    if(o.lifecycle==2&&o.seen==s.round) {
        if(o.tiles.is_set(s.pos))return;
        bool occupant=false;for(const auto& a:s.allies)if(o.tiles.is_set(a.position()))occupant=true;
        if(occupant) {
            if(!memory.protection_started)memory.protection_started=s.round;
            if(s.round-memory.protection_started>=Config::protection_limit){abandon(s.round);return;}
            fight(world,memory.task);
            if(fuel_remaining()>40000) {
                bitboard guard;for(auto p:o.tiles.positions())guard|=around(p,2);guard&=~o.tiles;
                if((guard&around(s.pos,0)).is_empty())move_to(guard,true,b,memory,CampTopologyView{world},true);
            }return;
        }
    }
    int nearest=1000;for(const auto& c:o.group.camps())nearest=std::min(nearest,cheb(s.pos,c.spawn_position()));
    if(o.lifecycle==1&&nearest<=me.attack_range()&&fight(world,memory.task)) {if(!me.can_move())return;observe();world.refresh(s,memory);}
    auto before=memory.last_distance;auto result=move_to(camp_goals(o,s),false,b,memory,CampTopologyView{world});
    if(result==RouteStatus::moved){++stats.moves;if(memory.last_distance<before)memory.progressed=s.round;}
    if(result==RouteStatus::deferred)++stats.defers;
    if(!b.current())return;
    const auto& fresh=observe();world.refresh(fresh,memory);if(facts(fresh,false).danger)return;if(fuel_remaining()>35000)fight(world,memory.task);
}
void Bot::play_turn() {
    int r=round_number();if(executing_round>=0&&executing_round!=r)++stats.resumes;executing_round=r;
    world.init();r=round_number();TurnBudget budget{r};const auto& s=observe();
    if(!priority_set){self().set_priority(80-world.slot*5);priority_set=true;}
    if(!s.alive) {
        if(memory.was_alive){++memory.life;abandon(r);memory.altar=-1;memory.bag_since=-1;memory.bank_bag=0;}
        memory.was_alive=false;memory.state=State::dead;shop(memory);coordinate(s);publish(s,false);++stats.dwell[int(memory.state)];executing_round=-1;return;
    }
    memory.was_alive=true;
    if(s.bag>0&&memory.bag_since<0)memory.bag_since=r;
    if(s.bag==0){memory.bag_since=-1;memory.altar=-1;if(memory.bank_bag>0)++stats.banks;memory.bank_bag=0;}
    if(memory.bank_bag>0&&!self().is_submitting_gems())memory.bank_bag=0;
    shop(memory);observe();world.refresh(s,memory);bool leader=coordinate(s);
    if(memory.task>=0) {
        auto& o=world.camps[memory.task];
        if(o.lifecycle==3&&o.seen==r){if(s.bag>memory.prior_bag)++stats.captures;advance_loop(world,memory.task);memory.task=-1;memory.protection_started=0;}
        else if(task_expired(r,memory.task_started,memory.progressed)){abandon(r);if(s.bag>0)memory.altar=choose_altar(world,s,budget);}
    }
    if(memory.task<0&&s.bag<Config::bank_bag&&!channel(self())) {
        auto w=shared_read();
        if(Config::coordination&&wire::leader_live(w,r,world.roster.size())) {
            int slot=wire::get(w,wire::leader,3);auto& a=world.roster[slot];
            if(slot!=world.slot&&a.is_alive()&&a.is_visible()&&cheb(a.position(),s.pos)<=6&&wire::get(w,wire::message,3)==2) {
                int candidate=-1;
                for(int i=0;i<int(world.camps.size());++i)if(world.chunk(world.camps[i].anchor)==int(wire::get(w,wire::anchor,6))&&world.camps[i].seen==r&&world.camps[i].lifecycle!=3&&cheb(a.position(),world.camps[i].anchor)<=3) {
                    if(candidate>=0){candidate=-1;break;}candidate=i;
                }
                if(candidate>=0&&world.camps[candidate].cooldown<=r){memory.task=candidate;memory.task_started=memory.progressed=r;memory.last_distance=65535;memory.guidance_seen=r;}
            }
        }
    }
    if(memory.carrier>=0) {
        auto& a=world.roster[memory.carrier];bool visible=a.is_alive()&&a.is_visible();
        if(!a.is_alive()||r>memory.protection_until||(!visible&&r-memory.carrier_seen>=2)||
            (visible&&(!a.is_submitting_gems()||cheb(a.position(),world.altars[memory.pending_altar])>1)))memory.carrier=-1;
        else if(visible)memory.carrier_seen=r;
    }
    if(memory.task<0&&memory.carrier<0&&s.bag==0)for(int i=0;i<int(world.roster.size());++i) {
        auto& a=world.roster[i];if(i==world.slot||!a.is_alive()||!a.is_visible()||!a.is_submitting_gems()||cheb(a.position(),s.pos)>3)continue;
        for(int j=0;j<int(world.altars.size());++j)if(cheb(a.position(),world.altars[j])<=1){memory.carrier=i;memory.pending_altar=j;memory.carrier_seen=r;memory.protection_until=r+a.remaining_channel_time()+3;break;}
        if(memory.carrier>=0)break;
    }
    auto f=facts(s,leader);memory.state=decide(f,memory);++stats.dwell[int(memory.state)];publish(s,leader);
    if(!budget.current())return;
    switch(memory.state) {
    case State::dead:case State::bank:case State::healing:break;
    case State::recall:if(!self().is_recalling())self().recall();break;
    case State::escape:
        if(self().is_recalling())self().cancel_recall();if(memory.task>=0)abandon(r);memory.carrier=-1;
        retreat(budget,memory,CampTopologyView{world});if(budget.current()){const auto& current=observe();defend_cast(current);fight(world,-1,true);}break;
    case State::defend:fight(world,-1);break;
    case State::prepare_bank:if(bank(world,budget,memory))memory.state=State::bank;break;
    case State::capture:case State::protect:
        if(memory.carrier>=0) {
            fight(world,-1,true);auto altar=world.altars[memory.pending_altar];
            if(cheb(self().position(),altar)>2)move_to(around(altar,2)&~around(altar,1),true,budget,memory,CampTopologyView{world},true);
        }else camp_action(budget);break;
    default:
        if(memory.task<0) {
            int selected=choose_camp(world,s,budget,!Config::value_routing,memory.shop_phase<Config::loop_phase);
            if(selected>=0){memory.task=selected;memory.task_started=memory.progressed=r;memory.protection_started=0;memory.last_distance=65535;}
            else if(selected==-2)++stats.defers;
        }
        if(memory.task>=0){memory.state=State::capture;camp_action(budget);}
        else {memory.state=State::explore;explore(world,budget,memory);}break;
    }
    if(!budget.current())return;
    const auto& fresh=observe();world.refresh(fresh,memory);publish(fresh,leader);
    if(memory.state!=State::escape&&memory.state!=State::recall&&memory.state!=State::healing&&budget.current())optional_ward(world,memory.task);
    if(r%100==world.slot&&fuel_remaining()>12000)stats.report(r,world.slot,fresh.bag,memory.task);
    memory.prior_bag=fresh.bag;executing_round=-1;
}
