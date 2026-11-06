#include "recovery.h"
#include <cassert>
#include <functional>
#include <iostream>
#include <queue>
using namespace lp;
using namespace lp::recovery;
static int checks=0;
#define REQUIRE(...) do {++checks;if(!(__VA_ARGS__)){std::cerr<<"line "<<__LINE__<<": "<<#__VA_ARGS__<<"\n";std::exit(1);}}while(0)
struct Fixture {
    std::shared_ptr<Terrain> t=std::make_shared<Terrain>();Scene s;
    Fixture(Point origin={4,5},Point home={2,5},int width=50,int height=25) {
        t->width=width;t->height=height;t->blocked.assign(width*height,1);t->spawn.assign(width*height,0);
        t->home.assign(width*height,65535);t->spawn[t->index(home)]=1;
        s.terrain=t;s.visible.assign(width*height,1);s.occupied.assign(width*height,0);s.pos=origin;
        s.alive=true;s.hp=230;s.max_hp=1000;s.can_move=true;s.can_cast=true;s.epoch={7,1,37,1};
        s.dash={true,true,false,false,2,0,0};open(origin);open(home);
    }
    void open(Point p){t->blocked[t->index(p)]=0;}
    void field() {
        std::queue<Point> q;std::fill(t->home.begin(),t->home.end(),65535);
        for(int y=0;y<t->height;++y)for(int x=0;x<t->width;++x)if(t->spawn[t->index({x,y})]){q.push({x,y});t->home[t->index({x,y})]=0;}
        while(!q.empty()){auto p=q.front();q.pop();for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){Point v{p.x+dx,p.y+dy};
            if(!t->inside(v)||t->blocked[t->index(v)]||t->home[t->index(v)]!=65535)continue;
            t->home[t->index(v)]=t->home[t->index(p)]+1;q.push(v);}}
    }
    void camp(Point p,int group,int range,float strength,bool awake,bool known=true,bool alive=true) {
        s.groups=std::max(s.groups,group+1);s.camps.push_back({p,group,range,strength,known,alive,awake});
    }
};
// Script changes only engine observations/permissions; every decision is made by execute/select_plan.
struct Script final:Backend {
    Scene live;Epoch now;int capture_calls=0,issued=0,defense_calls=0,current_calls=0;
    int stale_capture=-1,incomplete_capture=-1,stale_issue=-1,fail_issue=-1,stale_current=-1;
    bool unavailable_after_first=false,defensive_heal=false,allow_after_cancel=true;
    Status prerequisite=Status::ready;
    float defense_hp=-1;
    bool field_ready=false,roll_field=false;int fields=0;
    std::vector<Action> actions;
    std::function<void(Script&,Action)> after;
    explicit Script(const Scene& s):live(s),now(s.epoch){}
    Epoch epoch()override{return now;}
    bool current(Epoch e)override{if(++current_calls==stale_current)++now.round;return e==now;}
    Status prepare(Epoch)override {
        if(roll_field&&!field_ready){++fields;field_ready=true;++now.round;return Status::stale;}
        return prerequisite;
    }
    Status capture(Scene& s)override {
        ++capture_calls;if(capture_calls==stale_capture){++now.round;return Status::stale;}
        if(capture_calls==incomplete_capture)return Status::incomplete;
        live.epoch=now;s=live;return Status::ready;
    }
    bool issue(const Scene& s,Action a)override {
        if(!current(s.epoch))throw Halt{Status::stale};
        ++issued;actions.push_back(a);
        if(issued==fail_issue)return false;
        if(a.kind==Kind::step){REQUIRE(live.can_move);live.pos=a.target;live.can_move=false;live.movement_spent=true;}
        if(a.kind==Kind::dash){REQUIRE(live.can_cast);live.pos=a.target;live.can_cast=false;live.dash.available=false;}
        if(a.kind==Kind::cancel){REQUIRE(live.recalling);live.recalling=false;live.recall_cancelled=true;live.can_move=allow_after_cancel;live.can_cast=true;}
        if(a.kind==Kind::recall){REQUIRE(!live.recalling&&!live.tribute&&!live.teleport&&!live.stunned&&!live.completed&&!live.recall_started&&!live.recall_cancelled);live.recalling=true;live.recall_started=true;live.can_move=live.can_cast=false;live.timer=5;}
        if(unavailable_after_first&&issued==1)live.can_move=live.can_cast=false;
        if(after)after(*this,a);
        ++now.revision;if(issued==stale_issue)++now.round;
        return true;
    }
    bool defend(const Scene& s)override {if(!current(s.epoch))throw Halt{Status::stale};++defense_calls;
        if(defensive_heal||defense_hp>=0){live.hp=defense_hp>=0?defense_hp:700;++now.revision;return true;}return false;}
};
Outcome run(Fixture& f,Script& b,Memory& m,Intent intent=Intent::health){f.field();return execute(intent,m,b);}
Fixture ren() {
    Fixture f({21,15},{19,15});f.open({20,15});f.s.can_move=false;
    f.s.enemies.push_back({{22,15},2,60});f.field();return f;
}
Fixture heart() {
    Fixture f({18,13},{15,15});f.open({17,14});f.open({16,15});
    f.camp({20,14},0,4,60,true);f.s.dash.damage=true;f.s.dash.stun=true;f.s.dash.radius=1;f.field();return f;
}
Fixture leader() {
    Fixture f({38,20},{35,17});f.open({37,19});f.open({36,18});
    f.camp({40,20},0,4,20,true);f.camp({42,20},1,4,40,true);f.field();return f;
}
void motion() {
    {auto f=ren();Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.dashes==1&&o.moves==0&&b.live.pos==Point{19,15});REQUIRE(o.status==Status::reached_spawn);REQUIRE(o.candidates<=834);REQUIRE(!f.s.physical({19,17},f.s.pos)&&!f.s.physical({20,17},f.s.pos));}
    // Walking rejected by risk cannot mask a physically connected dash endpoint.
    {auto f=ren();f.s.can_move=true;auto p=select_plan(f.s);REQUIRE(p.first.kind==Kind::dash&&p.first.target==Point{19,15});}
    // Physical midpoint blockers cover wall/hole/altar/enemy spawn (same scalar static contract), occupancy and teleport.
    for(int mode=0;mode<4;++mode){auto f=ren();int i=f.t->index({20,15});
        if(mode==0)f.t->blocked[i]=1;
        if(mode==1||mode==2)f.s.occupied[i]=1;
        if(mode==3)f.s.visible[i]=0;
        REQUIRE(select_plan(f.s).actions==0);}
    {auto f=ren();f.s.occupied[f.t->index({19,15})]=1;REQUIRE(select_plan(f.s).first.target!=Point{19,15});}
    {Fixture f({1,0},{0,0},3,3);f.s.can_move=false;f.field();auto p=select_plan(f.s);REQUIRE(p.first.target==Point{0,0});
        REQUIRE(f.t->inside(p.first.target));REQUIRE(!f.s.physical({-1,0},f.s.pos));}
    {auto f=heart();auto p=select_plan(f.s);REQUIRE(p.first.kind==Kind::dash&&p.first.target==Point{16,15});
        Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.dashes==1&&o.moves==1&&b.live.pos==Point{15,15});}
    {auto f=leader();Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.dashes==1&&o.moves==1&&b.actions[0].target==Point{36,18}&&b.live.pos==Point{35,17});}
    {Fixture f({5,5},{2,5});f.open({4,5});f.open({3,5});f.s.dash.damage=true;f.s.dash.radius=1;
        f.s.visible[f.t->index({4,6})]=0;f.field();auto p=select_plan(f.s);REQUIRE(p.first.kind==Kind::step&&p.first.target==Point{4,5});
        Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.moves==1&&o.dashes==1&&b.live.pos==Point{2,5});}
    {auto f=ren();f.s.dash.supported=false;REQUIRE(select_plan(f.s).actions==0);f.s.can_move=true;REQUIRE(select_plan(f.s).first.kind==Kind::step);}
    for(int mode=0;mode<3;++mode){auto f=heart();Script b(f.s);Memory m;
        if(mode==0)b.unavailable_after_first=true;
        if(mode==1)b.fail_issue=2;
        if(mode==2)b.stale_issue=2;
        auto o=execute(Intent::health,m,b);REQUIRE(o.dashes==1);REQUIRE(o.moves==(mode==2?1:0));
        REQUIRE(o.status==(mode==0?Status::partial:mode==1?Status::blocked:Status::stale));REQUIRE(b.issued<=2);}
    {auto f=heart();Script b(f.s);Memory m;b.fail_issue=1;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::blocked&&o.dashes==0&&b.issued==1&&b.defense_calls==0);}
    {auto f=heart();Script b(f.s);Memory m;b.after=[](Script& b,Action){b.live.occupied[b.live.terrain->index({15,15})]=1;};
        auto o=execute(Intent::health,m,b);REQUIRE(o.dashes==1&&o.moves==0&&b.issued==1);}
}
void effects() {
    // Isolated dash: no ordinary action, static home favors landing; a remote sibling can cover it after wake.
    auto make=[] {Fixture f;f.open({3,5});f.s.can_move=false;f.s.dash.damage=true;f.s.dash.radius=1;f.s.visible[f.t->index({4,6})]=0;f.field();return f;};
    {auto f=make();REQUIRE(select_plan(f.s).actions==1);f.s.visible[f.t->index({1,4})]=0;REQUIRE(select_plan(f.s).actions==0);
        f.s.dash.damage=false;REQUIRE(select_plan(f.s).actions==1);}
    for(bool awake:{false,true}) {auto f=make();f.camp({1,4},0,0,0,awake);f.camp({7,5},0,5,70,false);
        REQUIRE(select_plan(f.s).actions==0);}
    {auto f=make();f.camp({1,4},0,0,0,false);f.camp({7,5},0,5,70,false,false);REQUIRE(select_plan(f.s).actions==0);}
    {auto f=make();f.camp({1,4},0,0,0,false);f.camp({7,5},0,5,70,false,true,false);REQUIRE(select_plan(f.s).actions==1);}
    {auto f=make();f.camp({1,4},0,0,0,false);f.camp({1,6},0,0,0,true);f.camp({7,5},0,5,70,false);REQUIRE(select_plan(f.s).actions==0);}
    {auto f=make();f.camp({1,4},0,0,0,false);f.camp({1,6},0,0,0,true);f.camp({7,5},0,5,70,false);
        f.camp({6,5},1,2,100,true);auto p=select_plan(f.s);REQUIRE(p.actions==1&&p.first.target==Point{2,5});}
    {auto f=make();f.camp({1,4},0,5,70,false);f.s.dash.stun=true;REQUIRE(select_plan(f.s).actions==0); // no invented kill/stun discount
        f.s.dash.damage=false;REQUIRE(select_plan(f.s).actions==0);}
    {auto f=make();f.s.enemies.push_back({{1,4},0,0});REQUIRE(select_plan(f.s).actions==0);}
    {auto f=heart();REQUIRE(select_plan(f.s).actions==2);}
    {auto f=ren();f.s.visible[f.t->index({18,14})]=0;REQUIRE(select_plan(f.s).actions==1);}
}
void channels_and_health() {
    // A37/B40: after a safe ordinary step, a new health channel may start in this dispatch.
    for(auto origin:{Point{18,7},Point{22,15}}) {
        Point destination{origin.x+1,origin.y-1};Fixture f(origin,{0,0});f.open(destination);f.s.dash.available=false;
        f.s.enemies.push_back({{origin.x-1,origin.y+1},1,60});f.field();
        Script b(f.s);b.after=[](Script& b,Action a){if(a.kind==Kind::step)b.live.enemies.clear();};Memory m;
        auto o=execute(Intent::health,m,b);REQUIRE(o.moves==1&&o.recall_starts==1&&o.status==Status::channeling&&m.recovering);
    }
    {Fixture f;f.s.can_move=f.s.can_cast=false;f.field();Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.status==Status::channeling&&o.recall_starts==1);}
    {Fixture f;f.s.can_move=f.s.can_cast=false;f.s.enemies.push_back({{30,20},1,60});f.field();Script b(f.s);Memory m;
        auto o=execute(Intent::health,m,b);REQUIRE(o.recall_starts==0&&o.status==Status::no_improvement);}
    {Fixture f;f.s.can_move=f.s.can_cast=false;f.field();Script b(f.s);b.defensive_heal=true;Memory m;m.recovering=true;
        auto o=execute(Intent::health,m,b);REQUIRE(!m.recovering&&o.recall_starts==0&&o.defenses==1&&o.status==Status::recovered);}
    {Fixture f;f.s.hp=900;f.s.can_move=f.s.can_cast=false;f.field();Script b(f.s);Memory m;
        auto o=execute(Intent::evasion,m,b);REQUIRE(!m.recovering&&o.recall_starts==0);}
    {Fixture f;f.s.hp=900;f.s.can_move=f.s.can_cast=false;f.field();Script b(f.s);b.defensive_heal=true;
        b.live.hp=230;Memory m;auto o=execute(Intent::evasion,m,b);REQUIRE(!m.recovering&&o.recall_starts==0);}
    {Fixture f;f.s.hp=900;f.s.can_move=f.s.can_cast=false;f.field();Script b(f.s);b.defense_hp=220;Memory m;
        auto o=execute(Intent::evasion,m,b);REQUIRE(m.recovering&&o.recall_starts==1);}
    for(int mode=0;mode<7;++mode){Fixture f;f.s.can_move=f.s.can_cast=false;f.field();
        if(mode==0)f.s.tribute=true;
        if(mode==1)f.s.teleport=true;
        if(mode==2)f.s.alive=false;
        if(mode==3)f.s.stunned=true;
        if(mode==4)f.s.completed=true;
        if(mode==5)f.s.recall_started=true;
        if(mode==6)f.s.recall_cancelled=true;
        Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.recall_starts==0);}
    {auto f=ren();Script b(f.s);Memory m;m.bank_bag=23;m.prior_bag=23;m.bag_since=12;m.altar=2;
        auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::reached_spawn&&m.bank_bag==23&&m.bag_since==12&&m.altar==2&&m.prior_bag==23);}
    {Fixture f({2,5},{2,5});f.s.hp=800;f.field();Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::recovered);}
    auto active=[] {Fixture f({24,0},{26,1});f.open({25,0});f.s.hp=415;f.s.max_hp=1200;f.s.recalling=true;f.s.timer=2;
        f.s.can_move=f.s.can_cast=false;f.s.enemies.push_back({{12,0},1,60});f.field();return f;};
    {auto f=active();Script b(f.s);Memory m;m.recovering=true;auto o=execute(Intent::health,m,b);
        REQUIRE(o.cancellations==1&&o.moves==1&&o.homeward&&b.live.pos==Point{25,0}&&o.recall_starts==0);}
    {auto f=active();Script b(f.s);b.allow_after_cancel=false;Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::cancelled_wait&&o.cancellations==1&&o.moves==0);}
    for(int mode=0;mode<5;++mode){auto f=active();
        if(mode==0)f.s.occupied[f.t->index({25,0})]=1;
        if(mode==1)f.s.visible[f.t->index({25,0})]=0;
        if(mode==2)f.s.enemies.push_back({{27,0},1,60});
        if(mode==3)f.s.timer=1;
        if(mode==4)f.s.movement_spent=true;
        Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::channeling&&o.cancellations==0&&b.issued==0&&b.defense_calls==0);}
    {auto f=active();Script b(f.s);b.fail_issue=2;Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::blocked&&o.homeward&&o.cancellations==1&&o.recall_starts==0);}
    {auto f=active();f.s.enemies.push_back({{23,0},1,60});Script b(f.s);Memory m;
        auto o=execute(Intent::health,m,b);REQUIRE(o.cancellations==1&&o.moves<=1&&o.recall_starts==0);}
    {auto f=active();f.s.timer=0;Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::channeling&&o.cancellations==0);}
}
void budgets_and_staleness() {
    {auto f=heart();Script b(f.s);b.roll_field=true;Memory m;
        auto first=execute(Intent::health,m,b);REQUIRE(first.status==Status::stale&&b.fields==1&&b.issued==0);
        auto second=execute(Intent::health,m,b);REQUIRE(second.moves+second.dashes==2&&b.fields==1);}
    for(int mode=0;mode<2;++mode){Fixture f({24,0},{26,1});f.open({25,0});f.s.recalling=true;f.s.timer=2;f.s.can_move=f.s.can_cast=false;f.field();
        Script b(f.s);if(mode==0)b.stale_issue=1;else b.stale_capture=2;Memory m;
        auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::stale&&o.cancellations==1&&o.moves==0&&b.issued==1&&b.defense_calls==0);}
    for(int at:{1,2,3}){auto f=heart();Script b(f.s);b.stale_capture=at;Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.status==Status::stale&&o.stop_dispatch());REQUIRE(o.moves+o.dashes==at-1);REQUIRE(b.defense_calls==0);}
    for(int at:{1,2}){auto f=heart();Script b(f.s);b.stale_issue=at;Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.status==Status::stale&&o.moves+o.dashes==at&&b.issued==at&&b.defense_calls==0);}
    for(auto status:{Status::initialization_deferred,Status::stale,Status::incomplete}){auto f=heart();Script b(f.s);b.prerequisite=status;Memory m;
        auto o=execute(Intent::health,m,b);REQUIRE(o.status==status&&o.stop_dispatch()&&b.issued==0&&b.capture_calls==0);}
    for(int at:{1,2}){auto f=heart();Script b(f.s);b.incomplete_capture=at;Memory m;auto o=execute(Intent::health,m,b);
        REQUIRE(o.status==Status::incomplete&&o.moves+o.dashes==at-1&&b.defense_calls==0);}
    {Fixture f;f.field();f.s.can_move=f.s.can_cast=false;Script b(f.s);Memory m;
        // Enumerate every current() checkpoint: rollover must issue no action after it.
        auto clean=execute(Intent::health,m,b);int total=b.current_calls;REQUIRE(clean.recall_starts==1);
        for(int at=1;at<=total;++at){Script x(f.s);x.stale_current=at;Memory n;auto o=execute(Intent::health,n,x);
            REQUIRE(o.status==Status::stale);REQUIRE(x.issued<=1);if(x.issued)REQUIRE(o.recall_starts==1);}
    }
    {auto f=heart();Script clean(f.s);Memory m;execute(Intent::health,m,clean);
        for(int at=1;at<=clean.current_calls;++at){Script b(f.s);b.stale_current=at;Memory n;
            auto o=execute(Intent::health,n,b);REQUIRE(o.status==Status::stale&&b.issued==o.moves+o.dashes);}}
    {auto f=ren();for(int i=0;i<Limits::enemies+1;++i)f.s.enemies.push_back({{0,0},1,1});
        Script b(f.s);Memory m;auto o=execute(Intent::health,m,b);REQUIRE(o.status==Status::incomplete&&b.issued==0);}
    {auto f=heart();f.s.groups=Limits::groups+1;REQUIRE(!select_plan(f.s).complete);}
    {auto f=heart();f.s.camps.resize(Limits::camps+1);REQUIRE(!select_plan(f.s).complete);}
    {auto f=heart();auto p=select_plan(f.s);for(int i=0;i<100;++i)REQUIRE(select_plan(f.s).first==p.first);}
    {Fixture f({4,5},{4,5});f.open({3,5});f.field();REQUIRE(select_plan(f.s).actions==0);}
    {Fixture f({10,10},{0,0});for(int y=7;y<=13;++y)for(int x=7;x<=13;++x)f.open({x,y});f.field();
        auto p=select_plan(f.s);REQUIRE(p.complete&&p.raw==417);Script b(f.s);int calls=b.current_calls;
        select_plan(b.live);REQUIRE(b.current_calls==calls&&b.issued==0&&b.capture_calls==0);}
    for(auto state:{State::dead,State::bank,State::healing,State::defend,State::prepare_bank,State::capture,State::protect,State::explore})
        REQUIRE(!routes(state,true)&&!routes(state,false));
    REQUIRE(routes(State::escape,false)&&routes(State::escape,true)&&routes(State::recall,true)&&!routes(State::recall,false));
}
void inherited_actions() {
    // Misleading fresh SDK permissions must not erase work from a prior owner.
    for(bool step:{false,true})for(bool dash:{false,true}) {
        auto f=leader();f.s.step_attempted=step;f.s.dash_attempted=dash;
        Script host(f.s);Memory memory;auto result=execute(Intent::health,memory,host);
        if(step)REQUIRE(result.moves==0);
        if(dash)REQUIRE(result.dashes==0);
        if(step&&dash)REQUIRE(host.issued==0);
        if(!step&&dash)REQUIRE(result.moves==1);
        if(step&&!dash)REQUIRE(result.dashes==1);
    }
}
int main(){motion();effects();channels_and_health();budgets_and_staleness();inherited_actions();std::cout<<"PASS: "<<checks<<" recovery assertions\n";}
