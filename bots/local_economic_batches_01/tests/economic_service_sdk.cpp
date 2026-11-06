// Actual selector, transaction and public SDK. Host imports are scripted;
// every unimplemented import throws through mechanically generated stubs.
#include "economic_service_sdk.h"
#include <iostream>
#include <map>
#include <stdexcept>
#include <tuple>
using namespace lp;using namespace lp::economic;
namespace fake {
int round=10,x=7,y=7,actions=0,attacks=0,casts=0,moves=0;
std::uint32_t flags=1|8|16|2048;
unsigned revision=1;
std::uint64_t fuel=100000;
bool move_result=true,cast_result=true,roll_action=false,roll_read=false,hidden=false,wrong_identity=false,error_action=false,ranged=false;
int mode=0,cooldown[2]={0,0};
float hp[2]={30,40};
float enemy_hp=120;
struct Mask {int x=0,y=0;float radius=-1;};
auto& masks(){static std::map<const std::uint64_t*,Mask> values;return values;}
void committed(){++actions;if(roll_action)++round;}
}
namespace cambc::detail {extern "C" {
int32_t sdk_bc_get_last_error(char*,uint32_t){return 0;}
int32_t sdk_get_settings(game_settings* p){*p={};return 0;}
int32_t sdk_shared_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_bc_metadata(metadata* p){*p={16,16,2,2,2,256,512};return 0;}
int32_t sdk_bc_map_symmetry(int32_t* p){*p=0;return 0;}
int32_t sdk_my_champion(){return 1;}
int32_t sdk_my_team(){return 0;}
int32_t sdk_item_info(uint32_t,item_info* p){*p={};return 0;}
int32_t sdk_consumable_info(uint32_t,consumable_info* p){*p={};return 0;}
int32_t sdk_champion_design(int32_t,champion_design* p){*p={};p->base_stats.base_move_speed=1;return 0;}
int32_t sdk_draft_memory_size(uint32_t* p){*p=0;return 0;}
int32_t sdk_read_draft_memory(int32_t,void*,uint32_t){return 0;}
int32_t sdk_spawn_region(int32_t,aabb* p){*p={};return 0;}
int32_t sdk_Bitboard_Zero(uint64_t* p){fake::masks()[p]={};return 0;}
int32_t sdk_Bitboard_Set(uint64_t*,int32_t,int32_t,int32_t){return 0;}
int32_t sdk_Bitboard_DrawChebyshev(uint64_t* p,int32_t x,int32_t y,float r){fake::masks()[p]={x,y,r};return 0;}
int32_t sdk_Bitboard_Test(const uint64_t* p,int32_t x,int32_t y,int32_t* result) {
    const auto m=fake::masks().at(p);*result=std::max(std::abs(x-m.x),std::abs(y-m.y))<=m.radius;return 0;
}
int32_t sdk_bc_map_mask(int32_t,uint64_t*){return 0;}
int32_t sdk_camp_buffs(uint32_t,camp_buff_data*,uint32_t,uint32_t* n){*n=0;return 0;}
int32_t sdk_camp_design(int32_t,camp_design* p){*p={};return 0;}
int32_t sdk_champion_identity(uint32_t key,champion_identity* p){*p={key==201?1:0,0};return 0;}
int32_t sdk_champion_is_alive(uint32_t key,int32_t* p){*p=key==201?fake::enemy_hp>0:bool(fake::flags&1);return 0;}
int32_t sdk_champion_ability_props(uint32_t,uint32_t slot,ability_props* p) {
    *p={};if(slot==1)return 0;
    p->kind=uint32_t(fake::mode==0?ability_kind::attack_reset:fake::mode==1?ability_kind::damage:ability_kind::dash);
    p->targets=fake::mode==2?ability_target_ground:ability_target_camps;
    if(fake::mode==1)p->payload.damage={3,1};
    if(fake::mode==2)p->payload.dash={2,1,1,0};
    return 0;
}
int32_t sdk_champion_cooldown(uint32_t,uint32_t slot,int32_t* p){*p=fake::cooldown[slot];return 0;}
int32_t sdk_champion(uint32_t key,champion_info* p) {
    *p={};p->state=fake::flags;p->health=p->max_health=1000;p->x=fake::x;p->y=fake::y;p->attack_range=1;
    if(key==201){p->team=1;p->state=1;p->health=fake::enemy_hp;p->x=8;p->y=7;}
    if(fake::roll_read)++fake::round;return 0;
}
int32_t sdk_champion_restrictions(uint32_t,uint8_t* p){*p=0;return 0;}
int32_t sdk_champion_buff_data(uint32_t,buff_data*,uint32_t,uint32_t* n){*n=0;return 0;}
int32_t sdk_bc_round_number(uint32_t* p){*p=fake::round;return 0;}
int64_t sdk_fuel_remaining(){return int64_t(fake::fuel);}
int32_t sdk_champion_at(int32_t x,int32_t y,uint32_t* p){if(x!=8||y!=7)throw std::runtime_error("unexpected enemy tile");*p=fake::wrong_identity?999:201;return 0;}
int32_t sdk_camp_at(int32_t x,int32_t y,uint32_t* p) {
    if(fake::hidden)return int32_t(error_code::api_not_in_vision);
    if(x==8&&y==7)*p=101;else if(x==7&&y==8)*p=102;else throw std::runtime_error("Unexpected camp coordinate");
    if(fake::wrong_identity)*p=999;return 0;
}
int32_t sdk_map_camp_info(uint32_t key,camp_info* p){*p={key==102?7:8,key==102?8:7,int(camp_type::gem_cluster)};return 0;}
int32_t sdk_map_camp_group_of(uint32_t,uint32_t* p){*p=0;return 0;}
int32_t sdk_camp_state(uint32_t key,uint32_t* p){*p=fake::hp[key-101]>0?2:0;return 0;}
int32_t sdk_camp(uint32_t key,camp_state* p){*p={};p->health=fake::hp[key-101];return 0;}
int32_t sdk_move_to(int32_t x,int32_t y,int32_t* result) {
    ++fake::moves;fake::committed();*result=fake::move_result;
    if(*result){fake::x=x;fake::y=y;fake::flags&=~8u;if(fake::ranged)fake::flags&=~16u;}
    return fake::error_action?int32_t(error_code::api_not_found):0;
}
int32_t sdk_cast(uint32_t slot,uint32_t kind,uint32_t key,int32_t x,int32_t y,int32_t* result) {
    ++fake::casts;fake::committed();*result=fake::cast_result;
    if(*result) {
        fake::flags&=~2048u;fake::cooldown[slot]=10;
        if(fake::mode==0)fake::flags|=16u;
        if(fake::mode==1) {if(kind!=uint32_t(entity_kind::camp))throw std::runtime_error("Wrong spell target category");fake::hp[key-101]=std::max(0.0f,fake::hp[key-101]-120);}
        if(fake::mode==2) {
            fake::x=x;fake::y=y;
            for(int i=0;i<2;++i)if(std::max(std::abs((i==0?8:7)-x),std::abs((i==0?7:8)-y))<=1)
                fake::hp[i]=std::max(0.0f,fake::hp[i]-40);
        }
    }
    return fake::error_action?int32_t(error_code::api_not_found):0;
}
int32_t sdk_attack(uint32_t kind,uint32_t key) {
    if(kind==uint32_t(entity_kind::champion)&&key==201) {
        ++fake::attacks;fake::committed();fake::flags&=~16u;fake::enemy_hp=std::max(0.0f,fake::enemy_hp-100);return 0;
    }
    if(kind!=uint32_t(entity_kind::camp)||key<101||key>102)throw std::runtime_error("Wrong basic target");
    ++fake::attacks;fake::committed();fake::flags&=~16u;fake::hp[key-101]=std::max(0.0f,fake::hp[key-101]-100);
    return fake::error_action?int32_t(error_code::api_not_found):0;
}
}}
namespace lp {unsigned observation_version(){return fake::revision;}void invalidate_observations(){++fake::revision;}}
unsigned checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
void reset(int mode=0) {
    ++fake::round;fake::revision=1;fake::flags=1|8|16|2048;fake::x=fake::y=7;
    fake::actions=fake::attacks=fake::casts=fake::moves=0;fake::mode=mode;
    fake::move_result=fake::cast_result=true;
    fake::roll_action=fake::roll_read=fake::hidden=fake::wrong_identity=fake::error_action=fake::ranged=false;
    fake::cooldown[0]=fake::cooldown[1]=0;fake::hp[0]=30;fake::hp[1]=40;
    fake::enemy_hp=120;
    cambc::detail::cached_self=cambc::detail::handle_access::make_champion(static_cast<handle_champion_t>(1));
}
struct Context {
    action::Ledger ledger;Memory memory;LiveTurn turn{ledger,memory,1};
    Context(){CHECK(ledger.begin(turn.epoch(),fake::fuel));}
    Scene capture() {
        Scene s;s.width=s.height=16;s.visible.fill(1);s.economy.complete=true;
        s.economy.self.epoch=turn.epoch();s.economy.self.alive=true;s.economy.self.hp=s.economy.self.max_hp=1000;
        s.economy.self.pos={fake::x,fake::y};s.can_attack=fake::flags&16;s.can_move=fake::flags&8;s.can_cast=fake::flags&2048;
        s.attack_range=s.move_range=1;s.basic=100;s.ranged=fake::ranged;s.groups.resize(1);
        auto& a=s.abilities[0];a.supported=a.camps=true;a.range=3;a.cooldown=fake::cooldown[0];
        a.kind=fake::mode==0?AbilityKind::reset:fake::mode==1?AbilityKind::damage:AbilityKind::dash;
        a.amount=fake::mode==1?120:40;
        if(fake::mode==2){a.range=2;a.radius=1;a.damaging=true;}
        for(int i=0;i<2;++i) {
            Member c;c.key=101+i;c.group=0;c.pos=i==0?Point{8,7}:Point{7,8};c.hp=fake::hp[i];
            c.known=c.hp_known=c.passive=true;c.visible=c.alive=c.hp>0;s.members.push_back(c);
            if(c.alive)s.occupied.at(s.local(c.pos))=1;
        }
        return s;
    }
    ServiceChoice select(const Scene& s){ServiceIntent in;in.key={0,0,0,Purpose::gems,Role::worker};return select_service(s,in,ledger);}
    action::Result issue(const Scene& s,const ServiceChoice& c){return perform_service(s,c,turn);}
    void after(action::Result r){CHECK(ledger.observe(r.event,turn.epoch()));}
};
int main(){try {
    reset();{Context c;
        auto s=c.capture();auto choice=c.select(s);CHECK(choice.request.op==action::Op::basic&&choice.request.target.key==101);
        auto first=c.issue(s,choice);CHECK(first.accepted()&&fake::hp[0]==0&&fake::attacks==1&&c.ledger.basics==1);
        CHECK(c.issue(s,choice).stop==action::Stop::stale); // deliberate stale request seals its ledger
    }
    reset();{Context c;
        for(auto expected:{action::Op::basic,action::Op::reset,action::Op::basic}) {
            auto s=c.capture();auto choice=c.select(s);CHECK(choice.stop==ServiceStop::action&&choice.request.op==expected);
            auto r=c.issue(s,choice);CHECK(r.accepted());c.after(r);
        }
        CHECK(fake::actions==3&&fake::attacks==2&&fake::casts==1&&fake::hp[0]==0&&fake::hp[1]==0);
        CHECK(c.ledger.basics==2&&c.ledger.casts==1&&c.ledger.primitives==3);
        CHECK(c.select(c.capture()).stop!=ServiceStop::action);
    }
    for(bool cast_first:{false,true}) {
        reset(1);fake::hp[0]=200;fake::hp[1]=30;Context c;
        auto s=c.capture();auto choice=c.select(s);
        // Both legal orders use the same production issuer; each is freshly
        // selected/revalidated after the first real host effect.
        choice.request.op=cast_first?action::Op::cast:action::Op::basic;
        choice.request.target.key=cast_first?101:102;choice.request.target.x=cast_first?8:7;
        choice.request.target.y=cast_first?7:8;choice.request.target.slot=cast_first?0:-1;
        auto r=c.issue(s,choice);CHECK(r.accepted());c.after(r);
        s=c.capture();choice=c.select(s);CHECK(choice.request.op==(cast_first?action::Op::basic:action::Op::cast));
        r=c.issue(s,choice);CHECK(r.accepted());c.after(r);CHECK(fake::attacks==1&&fake::casts==1);
    }
    reset();{fake::x=6;fake::ranged=true;fake::hp[0]=200;fake::hp[1]=0;Context c;
        for(auto expected:{action::Op::step,action::Op::reset,action::Op::basic}) {
            auto s=c.capture();auto choice=c.select(s);CHECK(choice.stop==ServiceStop::action&&choice.request.op==expected);
            auto r=c.issue(s,choice);CHECK(r.accepted());c.after(r);
        }
        CHECK(fake::moves==1&&fake::casts==1&&fake::attacks==1&&fake::hp[0]==100&&c.ledger.primitives==3);
    }
    reset(2);{fake::hp[0]=200;Context c;
        for(auto expected:{action::Op::dash,action::Op::basic}) {
            auto s=c.capture();auto choice=c.select(s);CHECK(choice.stop==ServiceStop::action&&choice.request.op==expected);
            auto r=c.issue(s,choice);CHECK(r.accepted());c.after(r);
        }
        CHECK(fake::moves==0&&fake::casts==1&&fake::attacks==1&&fake::hp[0]==60&&fake::hp[1]==0);
    }
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);fake::wrong_identity=true;
        CHECK(c.issue(s,choice).stop==action::Stop::denied&&fake::actions==0);}
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);fake::hidden=true;bool caught=false;
        try{c.issue(s,choice);}catch(cambc::error){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::actions==0);}
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);fake::roll_read=true;bool caught=false;
        try{c.issue(s,choice);}catch(TurnExpired){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::actions==0);}
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);fake::roll_action=true;
        auto r=c.issue(s,choice);CHECK(r.accepted()&&!c.ledger.open&&c.ledger.basics==1&&fake::actions==1);}
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);fake::error_action=true;bool caught=false;
        try{c.issue(s,choice);}catch(cambc::error){caught=true;}
        CHECK(caught&&!c.ledger.open&&fake::actions==1&&c.ledger.at(action::Op::basic).uncertain==1);}
    reset();{Context c;auto s=c.capture();auto choice=c.select(s);choice.request.op=action::Op::step;
        choice.request.target.key=-1;choice.request.target.x=6;choice.request.target.y=7;
        fake::move_result=false;auto r=c.issue(s,choice);
        CHECK(r.stop==action::Stop::refused&&c.ledger.steps==0&&c.ledger.step_attempted&&c.ledger.service_rejections==1);
        c.after(r);s=c.capture();choice.request.epoch=s.economy.self.epoch;
        CHECK(c.issue(s,choice).stop==action::Stop::denied&&fake::actions==1);}
    reset();{Context c;auto s=c.capture();auto& g=s.groups[0].observation;g.fresh=g.self_occupant=true;g.life=Life::reward;
        Champion enemy;enemy.key=201;enemy.alive=true;enemy.hp=120;enemy.pos={8,7};s.enemies.push_back(enemy);
        auto choice=c.select(s);CHECK(choice.enemy&&choice.request.op==action::Op::basic);
        auto result=c.issue(s,choice);CHECK(result.accepted()&&fake::enemy_hp==20&&fake::moves==0&&fake::x==7&&fake::y==7);
        c.after(result);
    }
    std::cout<<"PASS: "<<checks<<" actual-SDK service/retarget/reset/epoch assertions (scripted host)\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
#include "service_sdk_unused.inc"
