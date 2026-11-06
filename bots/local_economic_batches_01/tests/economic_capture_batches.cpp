// Reuse the strict public-SDK scripted host; its original assertions stay intact.
#define main inherited_capture_main
#include "economic_capture_sdk.cpp"
#undef main
namespace probe {
int calls=0,at=0,effect=0;
Context* context=nullptr;
void hook() {
    if(++calls!=at)return;
    if(effect==0)++fake::round;
    if(effect==1)++context->memory.life;
    if(effect==2)++fake::revision;
    if(effect==3)++context->ledger.origin.actor;
    if(effect==4)throw std::runtime_error("injected getter failure");
    if(effect==5){fake::fuel=100;throw std::runtime_error("injected getter failure");}
}
}
void reset_case(unsigned count=49){reset(count);fake::fuel=100000;}
int main(){try {
    // Warm SDK initialization is outside the measured guard window.
    (void)self();
    reset_case(2);{Context c;float total=0;
        fake::round_reads=fake::fuel_reads=0;
        for(int i=0;i<8;++i)total+=c.turn.read([]{return self().health();});
        CHECK(total==8000&&fake::round_reads==16&&fake::fuel_reads==32);
        CHECK(c.ledger.queries_issued==8&&c.ledger.queries_completed==8);
    }
    reset_case(2);{Context c;float total=0;
        fake::round_reads=fake::fuel_reads=0;
        c.turn.capture_reads([&](auto& batch){for(int i=0;i<8;++i)total+=batch.read([]{return self().health();});});
        CHECK(total==8000&&fake::round_reads==4&&fake::fuel_reads==2);
        CHECK(c.ledger.queries_issued==8&&c.ledger.queries_completed==8&&c.ledger.open);
    }
    for(int at:{1,2}) {
        reset_case(2);Context c;probe::context=&c;probe::calls=0;probe::at=at;probe::effect=0;
        fake::fuel_hook=probe::hook;bool expired=false,published=false;int getters=0;
        try{c.turn.capture_reads([&](auto& b){for(int i=0;i<8;++i)(void)b.read([&]{++getters;return self().health();});});published=true;}
        catch(TurnExpired){expired=true;}
        CHECK(expired&&!published&&!c.ledger.open&&getters==(at==1?0:8));
    }
    for(int effect=0;effect<4;++effect)for(int at:{1,4,8}) {
        reset_case(2);Context c;probe::context=&c;probe::calls=0;probe::at=at;probe::effect=effect;
        fake::query_hook=probe::hook;bool expired=false,published=false;
        try {c.turn.capture_reads([&](auto& b){for(int i=0;i<8;++i)(void)b.read([]{return self().health();});});published=true;}
        catch(TurnExpired){expired=true;}
        CHECK(expired&&!published&&!c.ledger.open&&probe::calls==8);
        CHECK(c.ledger.queries_issued==8&&c.ledger.queries_completed==8);
        bool entered=false;try{c.turn.capture_reads([&](auto&){entered=true;});}catch(TurnExpired){}
        CHECK(!entered&&probe::calls==8);
        try{c.turn.perform({c.turn.epoch(),action::Op::priority,{}},[]{return true;},[]{++fake::actions;});}catch(TurnExpired){}
        CHECK(fake::actions==0);
    }
    for(int effect:{4,5}) {reset_case(2);Context c;probe::context=&c;probe::calls=0;probe::at=3;probe::effect=effect;fake::query_hook=probe::hook;
        bool caught=false,published=false;
        try{c.turn.capture_reads([&](auto& b){for(int i=0;i<8;++i)(void)b.read([]{return self().health();});});published=true;}
        catch(const std::runtime_error& e){caught=std::string(e.what())=="injected getter failure";}
        CHECK(caught&&!published&&probe::calls==3&&c.ledger.queries_issued==3&&c.ledger.queries_completed==2);
    }
    for(bool crossing:{false,true}) {
        reset_case(2);Context c;auto hidden=c.w.camps[0].group.camps()[1];fake::camps()[1].visible=false;
        probe::context=&c;probe::calls=0;probe::at=1;probe::effect=0;if(crossing)fake::query_hook=probe::hook;
        bool expected=false,expired=false;
        try{c.turn.capture_reads([&](auto& b){(void)b.read([&]{return hidden.state();});});}
        catch(TurnExpired){expired=true;}
        catch(const cambc::error& e){expected=e.code()==error_code::api_not_in_vision;}
        CHECK(crossing?expired&&!expected:expected&&!expired);
        CHECK(c.ledger.queries_issued==1&&c.ledger.queries_completed==0);
    }
    for(int limit=0;limit<3;++limit) {
        reset_case(2);Context c;bool failed=false;
        if(limit==0)c.ledger.queries_issued=UINT32_MAX;
        if(limit==1)c.ledger.queries_completed=UINT32_MAX;
        int calls=0;
        try{c.turn.capture_reads([&](auto& b){for(int i=0;i<9;++i)(void)b.read([&]{++calls;return self().health();});});}
        catch(TurnExpired){failed=true;}catch(TurnDeferred){failed=true;}
        CHECK(failed&&!c.ledger.open&&calls==(limit==2?8:0));
        CHECK(limit!=0||c.ledger.queries_issued==UINT32_MAX);
        CHECK(limit!=1||c.ledger.queries_completed==UINT32_MAX);
    }
    reset_case(2);{Context c;float hp=0;int key=0;
        c.turn.capture_reads([&](auto& b){auto camp=b.read([]{return vision::camp_at({8,7});});
            hp=b.read([&]{return camp.health();});auto actor=b.read([]{return vision::champion_at(fake::origin);});key=id(actor);});
        CHECK(hp==30&&key==1&&c.ledger.queries_issued==3&&c.ledger.queries_completed==3);
        CHECK(fake::camp_identities==1&&fake::camp_reads==1);
    }
    reset_case(2);{Context c;probe::context=&c;probe::calls=0;probe::at=2;probe::effect=2;fake::query_hook=probe::hook;
        bool expired=false,published=false;
        try{auto scene=c.read();(void)scene;published=true;}catch(TurnExpired){expired=true;}
        CHECK(expired&&!published&&!c.ledger.open&&fake::actions==0);
    }
    std::cout<<"PASS: "<<checks<<" actual-SDK bounded-capture assertions; 8-getter guards 48 -> 6\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
