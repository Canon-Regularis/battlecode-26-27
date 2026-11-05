#include "feature_flags.h"
#if (PARTY_FEATURE_MASK & ~((1ULL<<14)|(1ULL<<15)|(1ULL<<16)|(1ULL<<17)|(1ULL<<18)|(1ULL<<20))) != 0
#include "bot.h"
#include "party_protocol.h"
#include "strategy_policy.h"
#include <iostream>
using namespace lp;

int Bot::feature_support(const Snapshot& s) const {
    auto w=party::advance(shared_read(),s.round);int count=1;
    if(!w)return count;
    for(const auto& ally:s.allies)if(id(ally)!=id(self())&&ally.is_alive()&&!channel(ally)&&cheb(ally.position(),s.pos)<=4) {
        auto it=std::find_if(world.roster.begin(),world.roster.end(),[&](const auto& actor){return id(actor)==id(ally);});
        if(it!=world.roster.end()&&party::get(w,party::safety+2*int(it-world.roster.begin()),2)<2)++count;
    }
    return count;
}

void Bot::feature_event(int kind,const char* event,int round,int target,int distance) {
    // No turn-wide logging. Capped causal events prove a branch was exercised.
    if(kind>=int(feature_state().events.size())||feature_state().events[kind]>=24||fuel_remaining()<12000)return;
    ++feature_state().events[kind];
    std::cout<<"LF event="<<event<<" round="<<round<<" slot="<<world.slot
             <<" target="<<target<<" distance="<<distance<<'\n';
}

bool Bot::feature_leader(const Snapshot& s) {
    if(!s.alive||fuel_remaining()<16000)return false;
    auto w=party::advance(shared_read(),s.round);if(!w)w=party::empty(s.round);
    int old=party::get(w,party::leader,3),next=old;
    bool dead=old<int(world.roster.size())&&!world.roster[old].is_alive();
    if(dead)next=7;
    bool eligible=s.hp>s.max_hp*.5f&&!memory.recovering&&memory.state!=State::escape;
    if(next==world.slot&&!eligible)next=7;
    // Fixed preference decides simultaneous eligibility without preempting a live leader.
    if(next==7&&eligible) {
        bool first=true;
        for(int slot:world.preference) {
            if(slot==world.slot)break;
            if(world.roster[slot].is_alive()){first=false;break;}
        }
        // A preferred but injured actor must not prevent every other actor taking over.
        if(first||s.round%int(world.preference.size())==world.slot)next=world.slot;
    }
    next=maintain_leader(old,dead,world.slot,next==world.slot&&eligible);
    w=party::put(w,party::leader,3,next);
    if(int(round_number())!=s.round)return false;
    shared_write(w,s.round);
    if(next!=old)feature_event(0,"leader_change",s.round,next);
    if constexpr(Features::follow)memory.guidance_seen=next!=world.slot?s.round:-100;
    return next==world.slot;
}

void Bot::feature_update(const Snapshot& s,TurnBudget& b,bool leader) {
    if constexpr(Features::shared) {
        if(fuel_remaining()<16000||!b.current())return;
        auto w=party::advance(shared_read(),s.round);if(!w)w=party::empty(s.round);
        if constexpr(Features::own_safety) {
            bool danger=(s.enemies>0&&(s.enemies>s.friends||s.hp<=s.max_hp*Config::recovery_low))||s.incoming>=s.hp||(s.camp_hit&&s.hp<=s.max_hp*Config::recovery_low);
            int safety=!s.alive||memory.state==State::recall||memory.state==State::healing?3:
                memory.state==State::escape||memory.state==State::defend||danger?2:
                memory.task>=0||memory.carrier>=0||channel(self())||memory.state==State::rally||memory.state==State::prepare_bank?1:0;
            w=party::put(w,party::safety+2*world.slot,2,safety);
            feature_event(24,"own_safety",s.round,safety);
        }
        if constexpr(Features::leader) {
            int old=party::get(w,party::leader,3);
            if(old<int(world.roster.size())&&!world.roster[old].is_alive())w=party::put(w,party::leader,3,7);
        }
        if constexpr(Features::bank_rally||Features::attack_rally) {
        bool live=party::live(w,s.round,world.roster.size(),world.columns*world.rows);
        if(live&&!world.roster[party::get(w,party::owner,3)].is_alive()){w=party::clear(w);live=false;}
        if(feature_state().joined&&(!live||!party::same(w,feature_state().joined))){feature_state().joined=0;feature_state().accepted=feature_state().arrived=false;feature_event(1,"rally_end",s.round);}
        if(feature_state().joined)feature_state().joined=w;
        bool banking=s.alive&&s.bag>0&&memory.altar>=0&&(memory.state==State::prepare_bank||memory.state==State::bank);
        if(feature_state().owned&&party::same(w,feature_state().owned)) {
            bool keep=banking;
            if(party::get(w,party::type,2)==2) {
                bool dead=false;
                for(const auto& enemy:champions(team::enemy))if(id(enemy)==feature_state().target)dead=!enemy.is_alive();
                for(const auto& enemy:s.foes)if(id(enemy)==feature_state().target)feature_state().contact=s.round;
                keep=s.alive&&!dead&&s.enemies<=s.friends&&s.round-feature_state().contact<2;
            }
            if(!keep){w=party::clear(w);feature_state().owned=0;feature_state().retry=s.round+3;feature_event(2,"rally_cancel",s.round);}
            else {w=party::refresh(w);feature_state().owned=w;}
        }else feature_state().owned=0;
        auto base=facts(s,leader);
        bool free=s.alive&&memory.task<0&&memory.carrier<0&&!channel(self())&&!base.bank_needed&&!base.danger&&!base.recovery;
        int kind=0,target=-1;
        if constexpr(Features::bank_rally)if(banking){kind=1;target=world.chunk(world.altars[memory.altar]);}
        if constexpr(Features::attack_rally)if(!kind&&free&&s.foes.size()==1) {
            const auto& enemy=s.foes.front();
            if(attack_admission(1,s.enemies,s.friends,cheb(enemy.position(),s.pos),s.hp,s.max_hp,enemy.health(),enemy.max_health())){
                kind=2;target=world.chunk(enemy.position());feature_state().target=id(enemy);feature_state().contact=s.round;
            }
        }
        if(kind&&s.round>=feature_state().retry&&party::may_create(w,s.round,kind,feature_state().last_created)) {
            w=party::create(w,world.slot,s.round,kind,target);feature_state().owned=w;feature_state().last_created=s.round;feature_state().retry=s.round+3;
            feature_event(kind==1?3:4,kind==1?"bank_publish":"attack_publish",s.round,target);
            if(kind==2){feature_state().joined=w;feature_state().accepted=true;feature_state().arrived=false;}
        }
        if(free&&!feature_state().joined&&party::live(w,s.round,world.roster.size(),world.columns*world.rows)&&party::get(w,party::owner,3)!=unsigned(world.slot)) {
            auto type=party::get(w,party::type,2);
            if((type==1&&Features::bank_rally)||(type==2&&Features::attack_rally)){
                feature_state().joined=w;feature_state().accepted=feature_state().arrived=false;feature_event(5,"rally_consider",s.round,type);
            }
        }
        }
        if constexpr(Features::leader)if(leader) {
            auto anchor=memory.task>=0?world.camps[memory.task].anchor:s.pos;
            w=party::put(w,party::anchor,6,world.chunk(anchor));
            w=party::put(w,party::message,3,memory.task>=0?2:1);
        }
        if constexpr(Features::enemy_reports) {
            int chunk=-1,count=0;
            for(const auto& enemy:s.foes){int c=world.chunk(enemy.position()),n=0;for(const auto& other:s.foes)if(world.chunk(other.position())==c)++n;if(n>count){count=n;chunk=c;}}
            w=party::sighting(w,s.round,chunk,count);
            if(count)feature_event(6,"enemy_report",s.round,chunk,count);
        }
        if(b.current())shared_write(w,s.round);
    }
}

bool Bot::feature_follow(TurnBudget& b) {
    const auto& s=observe();auto w=party::advance(shared_read(),s.round);
    if(!party::leader_live(w,s.round,world.roster.size()))return Features::strict_follow;
    int slot=party::get(w,party::leader,3);if(slot==world.slot)return false;
    auto& leader=world.roster[slot];
    if(leader.is_alive()&&leader.is_visible()) {
        auto position=leader.position();int candidate=-1,chunk=party::get(w,party::anchor,6);
        if(party::get(w,party::message,3)==2)for(int i=0;i<int(world.camps.size());++i) {
            auto& camp=world.camps[i];
            if(world.chunk(camp.anchor)==chunk&&camp.seen==s.round&&camp.lifecycle!=3&&camp.cooldown<=s.round&&cheb(position,camp.anchor)<=3){if(candidate>=0){candidate=-2;break;}candidate=i;}
        }
        if(candidate>=0){memory.task=candidate;memory.task_started=memory.progressed=s.round;memory.last_distance=65535;feature_event(7,"follow_camp",s.round,candidate);camp_action(b);return true;}
        if(cheb(position,s.pos)>2){feature_event(8,"follow_move",s.round,slot);move_to(around(position,2)&~around(position,0),true,b,memory,true);}
        if(b.current())fight(world,-1,true);
        return true;
    }
    if constexpr(Features::inspect) {
        int chunk=party::get(w,party::anchor,6);
        auto result=feature_state().inspector.step(world,b,memory,chunk,0x10000+slot*64+chunk);
        feature_event(9,"follow_inspect",s.round,int(result));return true;
    }
    return Features::strict_follow;
}

bool Bot::feature_rally(TurnBudget& b) {
    const auto& s=observe();auto w=party::advance(shared_read(),s.round);
    if(!feature_state().joined||!party::live(w,s.round,world.roster.size(),world.columns*world.rows)||!party::same(w,feature_state().joined)){feature_state().joined=0;return false;}
    int owner=party::get(w,party::owner,3),kind=party::get(w,party::type,2),chunk=party::get(w,party::chunk,6);
    auto& actor=world.roster[owner];if(!actor.is_alive()){feature_state().joined=0;return false;}
    bitboard goals;int altar=-1,limit=kind==1?8:6;
    if(kind==1) {
        for(int i=0;i<int(world.altars.size());++i)if(world.chunk(world.altars[i])==chunk){if(altar>=0){altar=-2;break;}altar=i;}
        if(actor.is_visible()) {
            altar=-1;
            for(int i=0;i<int(world.altars.size());++i)if(world.chunk(world.altars[i])==chunk&&cheb(actor.position(),world.altars[i])<=1){if(altar>=0){altar=-2;break;}altar=i;}
        }
        if(altar>=0)goals=around(world.altars[altar],2)&~around(world.altars[altar],1);
    }else for(const auto& enemy:s.foes)if(world.chunk(enemy.position())==chunk)goals|=around(enemy.position(),std::max(1,self().attack_range()));
    if(goals.is_empty()) {
        auto key=(std::uint64_t(party::born(w)+1)<<12)|(owner<<8)|chunk;
        auto result=feature_state().inspector.step(world,b,memory,chunk,key,limit);
        feature_event(10,"rally_inspect",s.round,int(result));return true;
    }
    if(!b.admit())return true;
    auto mask=s.blocked;if(kind==1)mask|=s.risk;mask.set(s.pos,false);goals&=~mask;
    if(goals.is_empty())return true;
    distance_field field;bitboard reached;++b.fields;field.compute_to(mask,goals,around(s.pos,0),reached,limit);
    if(!b.current())return true;
    int distance=reached.is_set(s.pos)?field.get(s.pos):65535;
    if(!rally_admitted(feature_state().accepted,kind,distance)){feature_state().joined=0;feature_state().accepted=false;return false;}
    if(!feature_state().accepted)feature_event(kind==1?11:12,kind==1?"bank_accept":"attack_accept",s.round,owner,distance);
    feature_state().accepted=true;
    if(!distance&&!feature_state().arrived){feature_state().arrived=true;feature_event(kind==1?13:14,kind==1?"bank_arrive":"attack_arrive",s.round,owner,0);}
    if(kind==1) {
        if(actor.is_visible()&&actor.gem_count()>0&&cheb(actor.position(),world.altars[altar])<=1) {
            memory.carrier=owner;memory.carrier_seen=s.round;memory.pending_altar=altar;
            memory.protection_until=s.round+(actor.is_submitting_gems()?actor.remaining_channel_time():3)+3;
            feature_state().joined=0;feature_event(15,"bank_escort",s.round,owner,distance);
            fight(world,-1,true);if(b.current())move_to(goals,true,b,memory,true);
        }else move_to(goals,true,b,memory,true);
    }else {fight(world,-1,true);if(b.current())move_to(goals,false,b,memory);}
    return true;
}

void Bot::feature_patrol(TurnBudget& b,bitboard region,vec2 anchor) {
    const auto& s=observe();if(!b.current()||channel(self())||!self().can_move())return;
    if(!region.is_set(s.pos)){move_to(region,true,b,memory,true);return;}
    if(!s.foes.empty())return;
    auto legal=around(s.pos,1)&region&~(s.blocked|s.risk);
    for(const auto& camp:vision::camps())if(camp.is_alive()&&camp.is_awake()&&camp.strength()>0)legal&=~around(camp.position(),camp.attack_range());
    auto candidates=legal.positions();if(candidates.empty())return;
    for(unsigned i=0;i<candidates.size();++i) {
        auto p=candidates[(i+s.round+world.slot)%candidates.size()];
        if(p!=s.pos&&cheb(p,anchor)<=2&&b.current()&&move_checked(p)){invalidate_observations();feature_event(16,"guard_patrol",s.round,-1,cheb(p,anchor));break;}
    }
}

bool Bot::feature_retreat(TurnBudget& b) {
    const auto& s=observe();bitboard goals;
    for(const auto& ally:s.allies)if(id(ally)!=id(self())&&ally.health()>ally.max_health()*.55f&&!channel(ally)&&incoming_at(ally.position(),s.foes)<s.incoming)goals|=around(ally.position(),2);
    if(goals.is_empty())return false;
    auto status=move_to(goals,true,b,memory);
    if(status==RouteStatus::moved){feature_event(17,"ally_retreat",s.round);return true;}
    return false;
}

#endif
