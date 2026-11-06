#include "economic_candidates.h"
#include <algorithm>
#include <cmath>
#include <tuple>
namespace lp::economic {
namespace {
int distance(Point a,Point b){return std::max(std::abs(a.x-b.x),std::abs(a.y-b.y));}
bool add(std::uint64_t& a,std::uint64_t b){if(b>UINT64_MAX-a)return false;a+=b;return true;}
bool in(const Field& f,Point p){return p.x>=0&&p.y>=0&&p.x<f.width&&p.y<f.height;}
unsigned cell(const Field& f,Point p){return unsigned(p.y*f.width+p.x);}
bool quantize(float value,bool up,std::uint64_t& result) {
    if(!std::isfinite(value)||value<0)return false;
    double scaled=std::ldexp(double(value),10);
    scaled=up?std::ceil(scaled):std::floor(scaled);
    if(scaled>=std::ldexp(1.0,64))return false;
    result=std::uint64_t(scaled);return true;
}
bool adequate(const GroupObservation& g){return g.allied_holder&&(!g.holder_departing||g.capture_timer<=g.earliest_departure);}
bool same_group(const Member& m,const Group& g){return m.group==g.observation.object;}
}
bool nominal_work(float hp,float basic,std::uint64_t& turns) {
    std::uint64_t h,d;
    if(!quantize(hp,true,h)||!quantize(basic,false,d))return false;
    d=std::max(std::uint64_t(1024),d);turns=h/d+(h%d!=0);return true;
}
bool tribute_turns(std::uint64_t bag,bool tribute,std::uint64_t& turns) {
    if(!bag||bag>UINT32_MAX)return false; // bounded native default-settings contract
    auto ordinary=std::max(std::uint64_t(1),bag/10+(bag%10!=0));
    // Native metadata: 0.33f = 11072963 / 33554432 exactly. Keep the
    // complement exact through the second ceiling, after ordinary duration.
    const auto reduced=ordinary*22481469;
    turns=tribute?reduced/33554432+(reduced%33554432!=0):ordinary;
    // A timer t started in round r resolves at owner-start r+t, not r+t+1.
    return true;
}
void Candidates::contact(const Field& f,Point p) {
    if(!in(f,p))return;
    const auto at=cell(f,p);const auto d=f.distances[at];
    if(f.blocked[at]||d==65535)return;
    if(!found||std::tuple{d,p.y,p.x}<std::tuple{best_distance,best.y,best.x}) {
        found=true;best=p;best_distance=d;
    }
}
bool Candidates::append(const Candidate& candidate) {
    if(result.size()>=capacity){capacity_failed=true;return false;}
    result.push_back(candidate);return true;
}
void Candidates::begin(const Scene& s,const Field& f,RankingSettings config) {
    *this=Candidates{};settings=config;epoch=s.economy.self.epoch;graph=f.graph;origin=f.origin;
    const auto n=std::int64_t(f.width)*f.height;
    if(!s.economy.complete||!f.complete||f.width<=0||f.height<=0||n>Route::cells||
        n!=std::int64_t(f.distances.size())||n!=std::int64_t(f.blocked.size())||
        n!=std::int64_t(f.covered.size())||s.groups.size()>128||s.members.size()>256||!s.geometry||s.geometry->groups.size()!=s.groups.size()||
        s.allies.size()>32||s.altars.size()>128||s.width!=f.width||s.height!=f.height||
        s.economy.self.pos!=origin||!in(f,origin)||f.blocked[cell(f,origin)]||f.distances[cell(f,origin)]!=0||
        settings.capture_time<0||settings.submit_range<0||settings.submit_range>3||s.attack_range<0||s.attack_range>12) {
        capacity_failed=true;return;
    }
    stage=Stage::groups;
}
CandidatesStatus Candidates::continue_build(const Scene& s,const Field& f,
        const std::array<DeliveryEstimate,128>& delivery,unsigned& writes) {
    if(capacity_failed)return CandidatesStatus::capacity;
    if(s.economy.self.epoch!=epoch||f.graph!=graph||f.origin!=origin||!f.complete)return CandidatesStatus::stale;
    if(!s.geometry||s.geometry->groups.size()!=s.groups.size())return CandidatesStatus::capacity;
    if(writes>Route::scalar_batch)return CandidatesStatus::capacity;
    auto charge=[&](){if(writes>=Route::scalar_batch)return false;++writes;return true;};
    while(stage!=Stage::finished) {
        if(!charge())return CandidatesStatus::planning;
        if(stage==Stage::groups) {
            if(group>=s.groups.size()){stage=Stage::altars;altar=0;found=false;dx=dy=-settings.submit_range;continue;}
            const auto& g=s.groups[group];const auto& o=g.observation;
            if(o.object!=int(group)||s.geometry->groups[group].spawn.empty()||s.geometry->groups[group].spawn.size()>256){capacity_failed=true;break;}
            if((o.fresh&&o.life==Life::respawning)||(o.fresh&&o.life==Life::reward&&!o.self_occupant&&adequate(o))) {++group;continue;}
            current={};current.key={int(group),o.cycle,-1,Purpose::gems,Role::worker};
            current.approach=Evidence::unknown;current.service=Evidence::unknown;current.recipient=Evidence::unknown;
            current.conversion=Evidence::unknown;current.conditional=true;
            current.fact=o.role_fact;priced=true;found=false;recipients=1;counted={};member=spawn=0;
            reward=o.fresh&&o.life==Life::reward;
            if(reward) {
                current.key.role=o.self_occupant?(o.contested?Role::defender:Role::holder):
                    o.allied_holder?Role::takeover:Role::recipient;
                current.service=Evidence::ready;
                current.recipient=o.self_occupant?Evidence::ready:Evidence::unknown;
                if(o.self_occupant)contact(f,s.economy.self.pos);
                stage=Stage::contacts;radius=0;dx=dy=0;center=s.geometry->groups[group].spawn[0];
            } else stage=Stage::members;
            continue;
        }
        const auto& self=s.economy.self;
        if(stage==Stage::members) {
            const auto& g=s.groups[group];
            if(member>=s.members.size()){stage=Stage::finish_group;continue;}
            const auto& m=s.members[member];
            if(!same_group(m,g)||(m.known&&!m.alive)){++member;continue;}
            std::uint64_t work=0;
            const float hp=(m.visible&&m.known&&m.alive&&m.hp_known)?m.hp:m.prior_hp;
            if(!nominal_work(hp,s.basic,work)||!add(current.work_turns,work))priced=false;
            center=(m.visible&&m.known&&m.alive)?m.pos:s.geometry->groups[group].spawn[std::min(spawn,unsigned(s.geometry->groups[group].spawn.size()-1))];
            // Unknown members retain their immutable spawn/last-known contact;
            // their nonzero design HP remains explicitly an estimate.
            if(!m.known)center=m.pos;
            radius=s.attack_range;dx=dy=-radius;ally=0;stage=Stage::contacts;continue;
        }
        if(stage==Stage::contacts) {
            contact(f,{center.x+dx,center.y+dy});
            if(++dx>radius){dx=-radius;++dy;}
            if(dy<=radius)continue;
            if(reward) {
                if(++spawn<s.geometry->groups[group].spawn.size()){center=s.geometry->groups[group].spawn[spawn];dx=dy=0;}
                else stage=Stage::finish_group;
            } else {stage=Stage::allies;ally=0;}
            continue;
        }
        if(stage==Stage::allies) {
            if(ally>=s.allies.size()){++member;stage=Stage::members;continue;}
            const auto& a=s.allies[ally];const auto& m=s.members[member];
            if(!counted[ally]&&a.alive&&!a.channel&&m.visible&&m.known&&m.alive&&distance(a.pos,m.pos)<=a.range) {
                counted[ally]=true;++recipients;
            }
            ++ally;continue;
        }
        if(stage==Stage::finish_group) {
            const auto& g=s.groups[group];const auto& o=g.observation;
            if(found) {
                current.anchor=best;current.key.contact=int(cell(f,best));current.approach_hops=best_distance;
                current.approach=Evidence::ready; // finite witness on the frozen graph, not future permission
                current.own_gems=s.geometry->groups[group].gems/recipients;current.own_gold=s.geometry->groups[group].gold/recipients;
                int wait=reward?o.capture_timer:settings.capture_time;
                if(settings.capture_cap>=0)wait=std::min(wait,settings.capture_cap);
                if(wait<0||!settings.capture_supported)priced=false;
                else current.capture_turns=std::uint64_t(wait)+1;
                current.estimate_priced=priced;
                const auto& d=delivery[group];
                if(d.status==DeliveryStatus::finite&&d.walk_edges!=65535)current.delivery_hops=d.walk_edges;
                else current.estimate_priced=false;
                std::uint64_t bag=self.bag;
                if(!settings.duration_supported||!add(bag,current.own_gems)||!tribute_turns(bag,settings.tribute,current.tribute_turns))
                    current.estimate_priced=false;
                if(!s.economy.has_altars)current.conversion=Evidence::unavailable;
                if(current.own_gems&&!append(current))break;
                // Gold has independent output and no speculative carried-bag or
                // delivery numerator after access alternatives are exhausted.
                current.key.purpose=Purpose::gold;current.conversion=Evidence::ready;
                current.delivery_hops=current.tribute_turns=0;current.estimate_priced=priced;
                if(current.own_gold&&!append(current))break;
            }
            ++group;stage=Stage::groups;continue;
        }
        if(stage==Stage::altars) {
            if(!self.bag||altar>=s.altars.size()){stage=Stage::finished;continue;}
            const auto p=s.altars[altar];
            const int range=settings.submit_range+(observation_contact?1:0);
            // If every altar stand is blocked, a distinct finite observation
            // contact can inspect access. It is never a certified BankNow rate.
            if(dx<-range||dy<-range){dx=dy=-range;}
            contact(f,{p.x+dx,p.y+dy});
            if(++dx>range){dx=-range;++dy;}
            if(dy<=range)continue;
            if(!found&&!observation_contact) {observation_contact=true;dx=dy=-(settings.submit_range+1);continue;}
            if(!found){++altar;observation_contact=false;dx=dy=-settings.submit_range;continue;}
            current={};current.key={int(altar),0,int(cell(f,best)),observation_contact?Purpose::observe_access:Purpose::convert,Role::carrier};
            current.anchor=best;current.approach=Evidence::ready;current.service=current.recipient=Evidence::ready;
            current.conversion=Evidence::unknown;current.approach_hops=best_distance;current.conditional=true;
            path_cursor=best;path_steps=0;path_known=!f.conditional&&f.epoch==epoch&&!observation_contact;stage=Stage::bank_path;continue;
        }
        if(stage==Stage::bank_path) {
            const auto at=cell(f,path_cursor);path_known&=bool(f.covered[at]);
            if(path_cursor!=origin) {
                constexpr int directions[8][2]={{-1,-1},{0,-1},{1,-1},{-1,0},{1,0},{-1,1},{0,1},{1,1}};
                bool previous=false;
                for(const auto& d:directions) {
                    Point next{path_cursor.x+d[0],path_cursor.y+d[1]};
                    if(in(f,next)&&!f.blocked[cell(f,next)]&&f.distances[at]>0&&f.distances[cell(f,next)]==f.distances[at]-1) {
                        path_cursor=next;previous=true;break;
                    }
                }
                if(!previous||++path_steps>unsigned(f.width*f.height)){capacity_failed=true;break;}
                continue;
            }
            const auto target=s.altars[altar];
            bool lock=false;for(const auto& l:s.locks)if(l.pos==target&&!l.allied)lock=true;
            current.conditional=!path_known||!s.seen(target)||lock;
            current.conversion=current.conditional?Evidence::unknown:Evidence::ready;
            current.estimate_priced=settings.duration_supported&&tribute_turns(self.bag,settings.tribute,current.tribute_turns)&&!current.conditional;
            // Only a presently executable, supported start may preempt a useful
            // commitment. Remote winning bags retain an ordinary obligation.
            current.winning_start=!current.conditional&&best==origin&&self.alive&&!self.completed&&!self.stunned&&!self.danger&&settings.submission_available&&
                self.channel==Channel::none&&self.score<settings.winning_gems&&self.bag>=settings.winning_gems-self.score;
            if(!append(current))break;
            ++altar;found=false;observation_contact=false;dx=dy=-settings.submit_range;stage=Stage::altars;
        }
    }
    return capacity_failed?CandidatesStatus::capacity:stage==Stage::finished?CandidatesStatus::ready:CandidatesStatus::planning;
}
}
