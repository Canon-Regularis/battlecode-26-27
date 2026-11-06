#include "economic_service.h"
#include <algorithm>
#include <bit>
#include <iostream>
#include <stdexcept>
using namespace lp;using namespace lp::economic;
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
Scene scene() {
    Scene s;s.width=s.height=16;s.economy.complete=true;s.economy.self.epoch={1,0,10,1};
    s.economy.self.alive=true;s.economy.self.hp=s.economy.self.max_hp=1000;s.economy.self.pos={7,7};
    s.visible.fill(1);s.can_attack=s.can_cast=true;s.attack_range=s.move_range=1;s.basic=100;
    s.groups.resize(2);for(int g=0;g<2;++g){s.groups[g].observation.object=g;s.groups[g].observation.cycle=0;}
    return s;
}
Member member(unsigned key,Point pos,float hp,int group=0,bool passive=true) {
    Member c;c.key=key;c.pos=pos;c.group=group;c.hp=hp;c.range=1;
    c.visible=c.known=c.alive=c.hp_known=true;c.passive=passive;return c;
}
void add(Scene& s,Member c){s.members.push_back(c);int i=s.local(c.pos);if(i>=0&&c.visible&&c.alive)s.occupied[i]=1;}
action::Ledger ledger(const Scene& s) {
    action::Ledger l;CHECK(l.begin(s.economy.self.epoch,100000));CHECK(l.handoff(action::Owner::service,s.economy.self.epoch));return l;
}
ServiceIntent intent(){ServiceIntent i;i.key={0,0,0,Purpose::gems,Role::worker};return i;}
work::Wide amount(float f){work::Domain d;work::Wide v;CHECK(d.encode(f,v));return v;}
void basic_reset_and_49() {
    auto s=scene();s.abilities[0].kind=AbilityKind::reset;s.abilities[0].supported=true;
    add(s,member(11,{8,7},30));add(s,member(12,{7,8},150));
    auto l=ledger(s);auto result=select_service(s,intent(),l);
    CHECK(result.stop==ServiceStop::action&&result.request.op==action::Op::basic);
    CHECK(result.request.target.key==12&&result.nominal_work==amount(150)); // two hits, not HP30+100
    s.members[1].hp=40;result=select_service(s,intent(),l);
    CHECK(result.nominal_work==amount(70)&&result.removals==2&&result.request.target.key==11);
    s.members[0].visible=s.members[0].alive=false;s.members[0].hp=0;s.can_attack=false;l.basics=1;l.primitives=1;
    result=select_service(s,intent(),l);CHECK(result.request.op==action::Op::reset&&result.request.target.key==12);
    l.casts=1;CHECK(select_service(s,intent(),l).stop==ServiceStop::allowance);
    s=scene();s.attack_range=10;s.abilities[0].kind=AbilityKind::reset;s.abilities[0].supported=true;
    for(int i=0;i<49;++i)add(s,member(100+i,{3+i%7,3+i/7},i==48?1:500));
    l=ledger(s);result=select_service(s,intent(),l);
    CHECK(result.nominal_work==amount(200)&&result.removals==0); // no target truncation or overkill credit
    s.members[48].hp=100;result=select_service(s,intent(),l);CHECK(result.nominal_work==amount(200)&&result.removals==1);
    l.basics=1;l.primitives=1;s.can_attack=false;
    result=select_service(s,intent(),l);CHECK(result.request.op==action::Op::reset&&result.request.target.key==148);
}
void damage_and_exact_pairs() {
    auto s=scene();auto& a=s.abilities[0];a.kind=AbilityKind::damage;a.supported=a.camps=true;a.range=2;a.amount=120;
    add(s,member(1,{8,7},110));add(s,member(2,{7,8},200));
    add(s,member(3,{6,7},std::bit_cast<float>(0x42c7ffffu))); // just below 100
    auto l=ledger(s);auto c=select_service(s,intent(),l);
    CHECK(c.nominal_work==amount(220)&&c.removals==0&&c.request.target.key==1);
    s.members.erase(s.members.begin());c=select_service(s,intent(),l);
    work::Wide expected;CHECK(amount(120).add(amount(std::bit_cast<float>(0x42c7ffffu)),expected));
    CHECK(c.nominal_work==expected&&c.removals==1&&c.request.target.key==3);
    // A basic-only later target must still pair with an earlier spell-only one.
    const auto damage=a;s=scene();s.abilities[0]=damage;s.abilities[0].range=3;
    add(s,member(90,{10,7},120));add(s,member(91,{8,7},100));
    l=ledger(s);c=select_service(s,intent(),l);CHECK(c.nominal_work==amount(220)&&c.removals==2);
    // Wide domain is an exact fallback, not unsupported.
    s.members[1].hp=std::bit_cast<float>(1u);c=select_service(s,intent(),l);
    CHECK(!c.fast_domain&&c.stop==ServiceStop::action);
    // An unavailable second facet cannot price a compound plan.
    l.primitives=3;c=select_service(s,intent(),l);CHECK(c.nominal_work==amount(120));
}
void admission_and_contact() {
    auto s=scene();auto c=member(1,{8,7},300,0,false);c.strength=20;add(s,c);
    auto l=ledger(s);CHECK(select_service(s,intent(),l).stop==ServiceStop::action);
    s.economy.self.hp=600;s.members[0].awake=true;s.members[0].strength=60;
    CHECK(select_service(s,intent(),l).stop==ServiceStop::action);
    s.economy.self.hp=400;s.members[0].strength=400;
    CHECK(select_service(s,intent(),l).stop==ServiceStop::unsafe);
    s.members[0].strength=450;CHECK(select_service(s,intent(),l).stop==ServiceStop::unsafe);
    s.members[0].strength=20;auto hidden=member(2,{14,14},100,0,false);hidden.known=hidden.visible=hidden.hp_known=false;
    add(s,hidden);CHECK(select_service(s,intent(),l).stop==ServiceStop::unknown_wake);
    s.members.back().known=true;s.members.back().alive=false;
    CHECK(select_service(s,intent(),l).stop==ServiceStop::action);
    s.economy.self.hp=340;CHECK(select_service(s,intent(),l).stop==ServiceStop::incomplete);
    s.economy.self.hp=500;auto in=intent();in.recovering=true;
    CHECK(select_service(s,in,l).stop==ServiceStop::incomplete);
    s=scene();s.can_move=true;add(s,member(1,{9,7},100));l=ledger(s);
    auto action=select_service(s,intent(),l);CHECK(action.request.op==action::Op::step&&action.nominal_work==amount(100));
    s.ranged=true;CHECK(select_service(s,intent(),l).stop==ServiceStop::no_contact);
    s.abilities[0].kind=AbilityKind::reset;s.abilities[0].supported=true;
    CHECK(select_service(s,intent(),l).request.op==action::Op::step);
    s.can_move=false;s.can_attack=false;l.steps=1;l.primitives=1;
    s.members[0].pos={8,7};CHECK(select_service(s,intent(),l).request.op==action::Op::reset);
    s.abilities[0].exclusive=true;CHECK(select_service(s,intent(),l).stop==ServiceStop::no_contact);
    s=scene();s.can_move=true;in=intent();in.has_contact=true;in.contact={6,7};l=ledger(s);
    CHECK(select_service(s,in,l).request.op==action::Op::step);
    s.visible[s.local(in.contact)]=0;CHECK(select_service(s,in,l).stop==ServiceStop::no_contact);
}
void heart_and_incidental_wake() {
    auto s=scene();s.occupied.fill(1);s.occupied.at(s.local({8,7}))=0;s.occupied.at(s.local({7,7}))=0;
    auto& dash=s.abilities[0];dash.kind=AbilityKind::dash;dash.supported=dash.damaging=true;
    dash.range=2;dash.radius=1;dash.amount=40;
    add(s,member(1,{9,7},100));auto l=ledger(s);auto c=select_service(s,intent(),l);
    CHECK(c.request.op==action::Op::dash&&c.nominal_work==amount(100)&&c.removals==1);
    // A second outside-footprint basic competes by exact marginal work.
    s.attack_range=3;add(s,member(2,{11,7},100));c=select_service(s,intent(),l);
    CHECK(c.nominal_work==amount(140)&&c.removals==1&&c.request.op==action::Op::dash);
    s.attack_range=1;s.members.pop_back();auto incidental=member(3,{9,8},100,1,false);incidental.range=2;incidental.strength=450;
    add(s,incidental);s.economy.self.hp=400;c=select_service(s,intent(),l);
    CHECK(c.stop==ServiceStop::unsafe);
    s.members.back().strength=20;CHECK(select_service(s,intent(),l).request.op==action::Op::dash);
    auto sibling=member(4,{14,14},100,1,false);sibling.visible=sibling.known=sibling.hp_known=false;add(s,sibling);
    CHECK(select_service(s,intent(),l).stop==ServiceStop::unknown_wake);
    s.members.back().known=true;s.members.back().alive=false;CHECK(select_service(s,intent(),l).request.op==action::Op::dash);
    l.casts=1;CHECK(select_service(s,intent(),l).stop!=ServiceStop::action);
}
void defense_and_guards() {
    auto s=scene();auto wolf=member(1,{8,7},500,0,false);wolf.awake=true;wolf.strength=20;add(s,wolf);
    s.economy.self.hp=600;s.abilities[0].kind=AbilityKind::shield;s.abilities[0].supported=true;auto l=ledger(s);
    CHECK(select_service(s,intent(),l).request.op==action::Op::shield);
    l.casts=1;CHECK(select_service(s,intent(),l).request.op==action::Op::basic);
    s.economy.self.channel=Channel::submit;CHECK(select_service(s,intent(),l).stop==ServiceStop::incomplete);
    s.economy.self.channel=Channel::none;s.basic=std::numeric_limits<float>::infinity();
    CHECK(select_service(s,intent(),l).stop==ServiceStop::unsupported);
    s=scene();s.groups[0].observation.fresh=true;s.groups[0].observation.life=Life::reward;
    s.groups[0].observation.self_occupant=true;l=ledger(s);CHECK(select_service(s,intent(),l).stop==ServiceStop::holding);
    Champion enemy;enemy.key=44;enemy.alive=true;enemy.hp=200;enemy.pos={8,7};s.enemies.push_back(enemy);
    auto defense=select_service(s,intent(),l);CHECK(defense.stop==ServiceStop::action&&defense.enemy&&defense.request.op==action::Op::basic&&defense.request.target.key==44);
    l.basics=2;CHECK(select_service(s,intent(),l).stop==ServiceStop::holding);l.basics=0;s.enemies.clear();
    s.groups[0].observation.self_occupant=false;
    Champion ally;ally.key=2;ally.alive=true;ally.hp=300;ally.max_hp=1000;ally.pos={8,7};s.allies.push_back(ally);
    auto& heal=s.abilities[0];heal.kind=AbilityKind::heal;heal.supported=heal.allies=true;heal.range=3;heal.amount=200;
    auto c=select_service(s,intent(),l);CHECK(c.request.op==action::Op::heal&&c.request.target.key==2);
    l.service_rejections=2;CHECK(select_service(s,intent(),l).stop==ServiceStop::allowance);
}
void exhaustive_stationary_controls() {
    // Independently enumerate ALL ordered pairs on small integer scenes, so
    // the streaming shortlist is checked against an O(T^2) reference.
    std::uint32_t random=0xca6bc;
    auto draw=[&](unsigned n){random=random*1664525u+1013904223u;return (random>>8)%n;};
    for(int test=0;test<600;++test) {
        auto s=scene();s.basic=1+draw(200);s.attack_range=1+draw(3);const int count=1+draw(8);
        constexpr int xy[8][2]={{6,6},{7,5},{9,6},{4,7},{8,7},{6,9},{7,10},{10,8}};
        for(int i=0;i<count;++i)add(s,member(100+i,{xy[i][0],xy[i][1]},1+draw(400)));
        s.abilities[0].kind=test%2?AbilityKind::damage:AbilityKind::reset;
        s.abilities[0].supported=s.abilities[0].camps=true;s.abilities[0].range=1+draw(3);s.abilities[0].amount=1+draw(200);
        s.abilities[1]=s.abilities[0];s.abilities[1].kind=AbilityKind::damage;s.abilities[1].range=1+draw(3);s.abilities[1].amount=1+draw(200);
        auto l=ledger(s);l.casts=draw(2);l.basics=draw(2);l.primitives=l.casts+l.basics;
        s.can_attack=draw(2);s.can_cast=draw(2);
        unsigned bestwork=0,bestremovals=0;
        auto score=[&](int i,unsigned hit1,int j,unsigned hit2,unsigned ops) {
            if(l.primitives+ops>4)return;
            unsigned total=0,removed=0;
            for(int k=0;k<count;++k) {
                unsigned hits=(k==i?hit1:0)+(k==j?hit2:0),hp=unsigned(s.members[k].hp);
                total+=std::min(hp,hits);removed+=unsigned(hits>=hp);
            }
            if(total>bestwork||(total==bestwork&&removed>bestremovals)){bestwork=total;bestremovals=removed;}
        };
        auto inrange=[&](int i,int range){auto p=s.members[i].pos;return std::max(std::abs(p.x-7),std::abs(p.y-7))<=range;};
        const bool basic=s.can_attack&&l.basics<2,cast=s.can_cast&&!l.casts;
        for(int i=0;i<count;++i) {
            if(basic&&inrange(i,s.attack_range))score(i,unsigned(s.basic),-1,0,1);
            for(const auto& a:s.abilities)if(cast) {
                if(a.kind==AbilityKind::reset) {
                    if(inrange(i,s.attack_range)) {
                        if(!basic)score(i,unsigned(s.basic),-1,0,2);
                        else if(!l.basics)for(int j=0;j<count;++j)if(inrange(j,s.attack_range))
                            score(i,unsigned(s.basic),j,unsigned(s.basic),3);
                    }
                } else if(inrange(i,a.range)) {
                    score(i,unsigned(a.amount),-1,0,1);
                    if(basic)for(int j=0;j<count;++j)if(inrange(j,s.attack_range))
                        score(i,unsigned(a.amount),j,unsigned(s.basic),2);
                }
            }
        }
        const auto chosen=select_service(s,intent(),l);
        if(bestwork)CHECK(chosen.stop==ServiceStop::action&&chosen.nominal_work==amount(float(bestwork))&&chosen.removals==bestremovals);
        else CHECK(chosen.stop!=ServiceStop::action);
    }
}
int main(){try {basic_reset_and_49();damage_and_exact_pairs();admission_and_contact();heart_and_incidental_wake();
    defense_and_guards();exhaustive_stationary_controls();
    std::cout<<"PASS: "<<checks<<" service assertions (owned synthetic scenes, 600 exhaustive stationary controls)\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
