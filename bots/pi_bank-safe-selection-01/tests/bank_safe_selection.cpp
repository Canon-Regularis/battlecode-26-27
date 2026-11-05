// Reuse the public-dispatch host, with the actual World::refresh linked below.
#define BSS_REAL_REFRESH
#include "bank_admission.cpp"

static void corridor(){
    for(int y=0;y<H;++y)if(y!=2)for(int x=0;x<W;++x)scene.blocked.set({x,y});
    scene.blocked.set({15,2}); // Known enemy spawn/physical occupancy remains blocked.
}
static void mask_checks(){
    for(int mode=0;mode<5;++mode){
        auto b=fresh();corridor();b.world.altars={{12,2}};b.world.altar_retry={0};
        if(mode!=0)vision::local_camps={{{7,3},mode!=4,mode!=2,mode==3?0.0f:20.0f,1}};
        TurnBudget budget{host_round};auto r=choose_altar(b.world,observe(),budget,0);
        status(r,mode==1?AltarStatus::unavailable:AltarStatus::selected,"only living awake damaging camp cuts physical/enemy-safe corridor");
        require(budget.fields==1&&field_calls==1,"mask uses exactly the existing single field");
        apply_altar_selection(r,scene,budget,b.memory);
        require(b.memory.bank_unavailable_round==(mode==1?100:-1),"only completed masked failure stamps admission");
        if(mode==1)require(std::vector<std::string>(camp_queries.begin(),camp_queries.begin()+4)==std::vector<std::string>{"list","alive","awake","strength"},"alive then awake then strength query order matches executor");
        if(mode==4){require(std::find(camp_queries.begin(),camp_queries.end(),"awake")==camp_queries.end(),"dead camp short circuits before awake");}
        if(mode==2){require(std::find(camp_queries.begin(),camp_queries.end(),"strength")==camp_queries.end(),"sleeping camp short circuits before strength");}
        if(mode==3){require(std::find(camp_queries.begin(),camp_queries.end(),"position")==camp_queries.end(),"zero strength short circuits before geometry");}
    }
    auto b=fresh();corridor();b.world.altars={{12,2}};b.world.altar_retry={0};vision::local_camps={{{7,4},true,true,20,1}};
    status(select(b),AltarStatus::selected,"route one tile beyond attack range remains reachable");
    vision::local_camps[0].range=2;status(select(b),AltarStatus::unavailable,"exact attack range boundary is excluded");
    b=fresh();corridor();b.world.altars={{12,2}};b.world.altar_retry={0};
    vision::local_camps={{{7,2},true,true,0,1}};scene.blocked.set({7,2});
    status(select(b),AltarStatus::unavailable,"zero strength preserves original physical occupancy blocker");
    b=fresh();vision::local_camps={{{3,2},true,true,20,2}};scene.blocked.set({3,2});
    status(select(b,0),AltarStatus::unavailable,"origin cleared after hazard cannot bridge all-neighbor enclosure");
    b=fresh();corridor();vision::local_camps={{{7,3},true,true,20,1}};
    b.world.altars={{12,2},{4,2}};b.world.altar_retry={0,0};
    require(select(b,0).index==1,"masked previous cannot defeat reachable alternative via hysteresis");
    b.world.altar_retry[1]=110;status(select(b,0),AltarStatus::cooldown,"reachable alternative cooling is cooldown even with masked old target");
    b.world.altars[1]={13,2};status(select(b,0),AltarStatus::unavailable,"cooldown does not manufacture spatial reachability");
    b=fresh();b.world.altars={{5,2},{2,5}};vision::local_camps={{{18,18},true,true,20,1}};
    require(select(b).index==0&&select(b,1).index==1,"unaffected route tie order and eligible previous hysteresis retained");
}
static void construction_checks(){
    for(bool capped:{false,true}){
        auto b=fresh();vision::local_camps={{{7,3}}};if(!capped)host_fuel=29999;
        TurnBudget budget{host_round,capped?1:0};status(choose_altar(b.world,observe(),budget),AltarStatus::deferred,"initial denied/capped selection defers");
        require(camp_queries.empty()&&field_calls==0,"initial denial never starts new vision scan");
    }
    for(int stage=0;stage<5;++stage)for(bool rollover:{false,true}){
        auto b=fresh();vision::local_camps={{{7,3}},{{8,3}},{{9,3}}};
        if(stage==3)vision::local_camps.resize(1);
        if(stage==4)vision::local_camps.clear();
        b.memory.altar=0;b.memory.queue_started=90;b.memory.bank_unavailable_round=95;
        const char* trigger=(stage==0||stage==4)?"list":stage==1?"alive":"position";
        bool fired=false;on_camp_query=[&](const char* name){if(!fired&&std::string(name)==trigger){fired=true;if(rollover)++host_round;else host_fuel=29999;}};
        TurnBudget budget{100};auto result=choose_altar(b.world,scene,budget,0);status(result,AltarStatus::deferred,"mask query rollover or lost field-admission fuel defers");
        apply_altar_selection(result,scene,budget,b.memory);
        require(fired&&field_calls==0&&budget.fields==0,"incomplete mask consumes no field");
        require(b.memory.altar==0&&b.memory.queue_started==90&&b.memory.bank_unavailable_round==95,"mask deferral preserves state and records no failure");
        require(std::count(camp_queries.begin(),camp_queries.end(),"list")==1,"one captured local camp list");
        require(std::count(camp_queries.begin(),camp_queries.end(),"alive")== ((stage==0||stage==4)?0:1),"bounded scan stops before next camp after becoming stale/underfunded");
    }
    auto b=fresh();vision::local_camps={{{18,18}}};on_camp_query=[](const char*){host_fuel=30000;};
    status(select(b),AltarStatus::selected,"exact field-admission boundary after mask still computes");require(field_calls==1,"no second field at admission boundary");
}
static void completion_checks(){
    for(int mode=0;mode<4;++mode){
        auto b=fresh();vision::local_camps={{{18,18}}};
        b.memory.altar=0;b.memory.queue_started=90;
        auto interrupt=[mode] {if(mode%2)host_fuel=4999;else ++host_round;};
        if(mode<2)after_field=interrupt;else during_scoring=interrupt;
        TurnBudget budget{host_round};auto result=choose_altar(b.world,observe(),budget,0);
        status(result,AltarStatus::deferred,"field/scoring epoch and reserve guards remain after camp masking");
        apply_altar_selection(result,scene,budget,b.memory);
        require(field_calls==1&&budget.fields==1&&b.memory.altar==0&&b.memory.queue_started==90&&b.memory.bank_unavailable_round==-1,"incomplete field/scoring does not apply or allocate another field");
    }
    for(bool failure:{false,true})for(bool rollover:{false,true}){
        auto b=fresh();vision::local_camps={{{18,18}}};if(failure)unavailable();
        b.memory.altar=1;b.memory.queue_started=90;TurnBudget budget{host_round};
        auto result=choose_altar(b.world,observe(),budget,1);
        status(result,failure?AltarStatus::unavailable:AltarStatus::selected,"completed result before application interruption");
        if(rollover)++host_round;else host_fuel=4999;
        apply_altar_selection(result,scene,budget,b.memory);
        require(b.memory.altar==1&&b.memory.queue_started==90&&b.memory.bank_unavailable_round==-1,"application rejects stale/under-reserve selected or unavailable result");
    }
}
static void refresh_dispatch_checks(){
    auto b=fresh(246);vision::local_camps={{{3,2},true,true,20,2}};scene.blocked.set({3,2});
    b.memory.task=0;b.memory.task_started=236;b.memory.progressed=245;b.memory.last_distance=0;
    b.world.camps[0].remaining=b.world.camps[0].design_health=host_camp_hp;
    route_result=RouteStatus::wait; // No simulated movement progress; only actual refresh of HP.
    b.play_turn();
    require(b.memory.bank_unavailable_round==246&&b.memory.state==State::prepare_bank&&camp_attacks==0,"current completed masked failure at 246 stays bank-preempted");
    require(field_calls==1&&b.memory.task==0&&b.memory.task_started==236&&b.memory.progressed==245,"failure preserves original task and clocks with no extra field");
    for(int r=247;r<=256;++r){
        host_round=r;int before=camp_attacks;float hp=host_camp_hp;b.play_turn();
        require(camp_attacks>before&&host_camp_hp<hp&&host_camp_hp>0,"next-round original work deals simulated nonlethal damage");
        require(b.memory.task==0&&b.memory.task_started==236&&b.memory.progressed==r,"production World refresh renews committed task HP progress without timer edits");
        require(actors[0].bag==8&&b.memory.bag_since==166&&b.memory.prior_bag==8&&b.memory.life==0,"bag and life accounting survive original-work interval");
        require(b.memory.bank_unavailable_round==246&&b.memory.state==State::capture&&bank_due(8,166,r,0),"still-due task remains admitted only under inherited window");
    }
    host_round=257;int before=camp_attacks;b.play_turn();
    require(b.memory.state==State::prepare_bank&&camp_attacks==before&&b.memory.bank_unavailable_round==257,"inherited reconsideration boundary restores bank preemption and completes fresh failure");
    require(b.memory.task_started==236&&b.memory.progressed==256&&field_calls==2,"reconsideration does not reset task clocks or add selector fields");
}
int main(){mask_checks();construction_checks();completion_checks();refresh_dispatch_checks();std::cout<<"PASS: "<<checks<<" safe-mask/production-refresh assertions\n";}
