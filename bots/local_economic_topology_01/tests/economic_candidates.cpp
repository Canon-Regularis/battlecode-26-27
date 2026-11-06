#include "economic_candidates.h"
#include <iostream>
#include <limits>
#include <queue>
#include <stdexcept>
using namespace lp;using namespace lp::economic;
int checks=0;
#define CHECK(...) do{++checks;if(!(__VA_ARGS__))throw std::runtime_error("line "+std::to_string(__LINE__)+": " #__VA_ARGS__);}while(0)
Scene scene() {
    Scene s;s.width=s.height=16;s.attack_range=1;s.basic=100;
    s.economy.complete=true;s.economy.self.epoch={1,0,10,1};s.economy.self.pos={1,1};
    s.economy.self.hp=s.economy.self.max_hp=1000;s.economy.self.alive=true;
    s.can_attack=s.can_cast=s.can_move=true;s.move_range=1;
    s.visible.fill(1);return s;
}
void group(Scene& s,Point pos,unsigned gems,unsigned gold=0,float hp=100) {
    int i=int(s.groups.size());Group g;
    auto geometry=s.geometry?std::make_shared<Geometry>(*s.geometry):std::make_shared<Geometry>();
    GroupGeometry metadata;metadata.anchor=pos;metadata.spawn={pos};metadata.gems=gems;metadata.gold=gold;
    geometry->groups.push_back(std::move(metadata));s.geometry=std::move(geometry);
    g.observation.object=i;g.observation.cycle=0;g.observation.life=Life::living;g.observation.fresh=true;
    s.groups.push_back(g);s.economy.groups.push_back(g.observation);
    Member m;m.group=i;m.key=100+i;m.pos=pos;m.hp=m.prior_hp=hp;
    m.known=m.visible=m.alive=m.passive=m.hp_known=true;s.members.push_back(m);
}
Field field(const Scene& s) {
    Field f;f.width=s.width;f.height=s.height;f.epoch=s.economy.self.epoch;f.origin=s.economy.self.pos;
    f.graph=1;f.complete=true;f.blocked.resize(f.width*f.height);f.covered.assign(f.blocked.size(),1);
    f.distances.assign(f.blocked.size(),65535);
    for(auto p:s.altars)f.blocked[p.y*f.width+p.x]=1;
    for(auto m:s.members)if(m.known&&m.alive)f.blocked[m.pos.y*f.width+m.pos.x]=1;
    auto root=f.origin;f.blocked[root.y*f.width+root.x]=0;f.distances[root.y*f.width+root.x]=0;
    std::queue<Point> q;q.push(root);
    while(!q.empty()) {
        auto p=q.front();q.pop();
        for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx)if(dx||dy) {
            Point n{p.x+dx,p.y+dy};if(n.x<0||n.y<0||n.x>=f.width||n.y>=f.height)continue;
            int at=n.y*f.width+n.x;if(f.blocked[at]||f.distances[at]!=65535)continue;
            f.distances[at]=f.distances[p.y*f.width+p.x]+1;q.push(n);
        }
    }
    return f;
}
RankingSettings config(){RankingSettings c;c.duration_supported=true;c.winning_gems=1000;return c;}
std::array<DeliveryEstimate,128> delivery(){std::array<DeliveryEstimate,128> d;for(auto& v:d)v={3,DeliveryStatus::finite,3};return d;}
std::vector<Candidate> build(const Scene& s,const Field& f,RankingSettings config=config(),unsigned batch=4096) {
    Candidates c;c.begin(s,f,config);auto d=delivery();
    for(int i=0;i<100;++i) {
        unsigned writes=Route::scalar_batch-batch;auto result=c.continue_build(s,f,d,writes);
        CHECK(writes<=Route::scalar_batch);
        if(result==CandidatesStatus::ready)return c.options();
        CHECK(result==CandidatesStatus::planning);
    }
    throw std::runtime_error("nonterminating ranking");
}
const Candidate& find(const std::vector<Candidate>& c,int object,Purpose p){for(auto& v:c)if(v.key.object==object&&v.key.purpose==p)return v;throw std::runtime_error("missing option");}
int main(){try {
    std::uint64_t n=0;
    CHECK(nominal_work(100.01f,100,n)&&n==2);CHECK(nominal_work(0,0,n)&&n==0);
    CHECK(!nominal_work(std::numeric_limits<float>::infinity(),100,n));
    CHECK(!nominal_work(100,std::numeric_limits<float>::quiet_NaN(),n));
    // All 20 independent native channel starts, with/without one Tribute.
    for(auto row:{std::array<unsigned,3>{1,1,1},{10,1,1},{11,2,2},{14,2,2},{15,2,2},
                  {20,2,2},{21,3,3},{30,3,3},{31,4,3},{100,10,7}}) {
        CHECK(tribute_turns(row[0],false,n)&&n==row[1]);CHECK(tribute_turns(row[0],true,n)&&n==row[2]);
    }
    CHECK(!tribute_turns(UINT64_MAX,true,n));
    auto s=scene();s.economy.has_altars=true;s.altars={{1,0}};group(s,{3,1},5,5);group(s,{8,1},100,10);
    auto f=field(s);auto options=build(s,f);
    CHECK(options.size()==4);CHECK(find(options,1,Purpose::gems).approach_hops>find(options,0,Purpose::gems).approach_hops);
    Owner owner;auto chosen=owner.update(s.economy,options);
    CHECK(chosen.decision==Decision::task&&chosen.task.key.object==1); // valuable, farther group wins
    auto split=build(s,f,config(),7);
    CHECK(split.size()==options.size());
    for(unsigned i=0;i<split.size();++i)CHECK(split[i].key==options[i].key&&split[i].anchor==options[i].anchor&&
        split[i].work_turns==options[i].work_turns&&split[i].own_gems==options[i].own_gems);
    // A large group is an expensive estimate, not an arbitrary >90-turn ban.
    auto large=scene();group(large,{3,1},343,0,100000);large.economy.has_altars=true;large.altars={{1,0}};
    auto costly=build(large,field(large));CHECK(find(costly,0,Purpose::gems).work_turns==1000);
    Owner large_owner;CHECK(large_owner.update(large.economy,costly).task.present);
    large.members[0].hp=large.members[0].prior_hp=std::numeric_limits<float>::max();
    auto unpriced=build(large,field(large));CHECK(!find(unpriced,0,Purpose::gems).estimate_priced);
    Owner unknown_owner;CHECK(unknown_owner.update(large.economy,unpriced).task.present);
    // Unknown visibility retains design HP and never masquerades as zero work.
    large.members[0].known=large.members[0].visible=large.members[0].hp_known=false;
    large.members[0].hp=0;large.members[0].prior_hp=300;
    auto hidden=build(large,field(large));CHECK(find(hidden,0,Purpose::gems).work_turns==3);
    // One ally engaging two members is one forecast recipient, not two.
    auto crowd=scene();group(crowd,{3,1},21,11);auto m=crowd.members[0];m.key=201;m.pos={3,2};
    crowd.members.push_back(m);
    auto crowd_geometry=std::make_shared<Geometry>(*crowd.geometry);crowd_geometry->groups[0].spawn.push_back(m.pos);
    crowd.geometry=std::move(crowd_geometry);
    Champion a;a.alive=true;a.pos={4,1};a.range=1;crowd.allies.push_back(a);
    auto crowded=build(crowd,field(crowd));CHECK(find(crowded,0,Purpose::gems).own_gems==10);
    CHECK(find(crowded,0,Purpose::gold).own_gold==5&&find(crowded,0,Purpose::gold).work_turns==2);
    crowd.allies[0].channel=true;CHECK(find(build(crowd,field(crowd)),0,Purpose::gems).own_gems==21);
    // A sufficiently secured allied holder removes unnecessary helper work.
    crowd.groups[0].observation.life=Life::reward;crowd.groups[0].observation.allied_holder=true;
    CHECK(build(crowd,field(crowd)).empty());
    crowd.groups[0].observation.holder_departing=true;crowd.groups[0].observation.capture_timer=5;
    crowd.groups[0].observation.earliest_departure=1;for(auto& member:crowd.members)member.alive=false;
    auto takeover=build(crowd,field(crowd));CHECK(find(takeover,0,Purpose::gems).key.role==Role::takeover);
    // No-altar output is independent earned gold, not a bag conversion promise.
    auto gold=scene();group(gold,{3,1},10,30);auto gold_options=build(gold,field(gold));
    Owner gold_owner;CHECK(gold_owner.update(gold.economy,gold_options).task.key.purpose==Purpose::gold);
    // BankNow shares the same origin field and includes actual owner-start time.
    s.economy.self.bag=30;options=build(s,field(s));auto bank=find(options,0,Purpose::convert);
    CHECK(bank.approach_hops==0&&bank.tribute_turns==3&&!bank.conditional&&!bank.winning_start);
    s.economy.self.score=980;bank=find(build(s,field(s)),0,Purpose::convert);CHECK(bank.winning_start);
    s.economy.self.stunned=true;CHECK(!find(build(s,field(s)),0,Purpose::convert).winning_start);
    s.economy.self.stunned=false;s.locks.push_back({s.altars[0],false,5});
    bank=find(build(s,field(s)),0,Purpose::convert);CHECK(bank.conditional&&!bank.estimate_priced&&!bank.winning_start);
    s.locks.clear();f=field(s);f.covered[s.economy.self.pos.y*16+s.economy.self.pos.x]=0;
    bank=find(build(s,f),0,Purpose::convert);CHECK(bank.conditional&&!bank.winning_start);
    f=field(s);f.conditional=true;CHECK(find(build(s,f),0,Purpose::convert).conditional);
    // Static delivery failure is an unpriced walking estimate, not impossibility.
    Candidates c;f=field(s);c.begin(s,f,config());auto d=delivery();d[0]={65535,DeliveryStatus::disconnected,3};unsigned writes=0;
    CHECK(c.continue_build(s,f,d,writes)==CandidatesStatus::ready);
    auto disconnected=find(c.options(),0,Purpose::gems);CHECK(!disconnected.estimate_priced&&disconnected.conversion==Evidence::unknown);
    // Frozen planning data must not silently switch to another scene or field.
    Candidates stale;c.begin(s,f,config());++s.economy.self.epoch.revision;writes=0;
    CHECK(c.continue_build(s,f,d,writes)==CandidatesStatus::stale);
    --s.economy.self.epoch.revision;c.begin(s,f,config());++f.graph;writes=0;
    CHECK(c.continue_build(s,f,d,writes)==CandidatesStatus::stale);
    std::cout<<"PASS: "<<checks<<" economic candidate/whole-cycle selection assertions\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
