// Exercise the actual capture/SDK seam; inherited cases run separately unchanged.
#define main inherited_topology_capture_main
#include "economic_capture_sdk.cpp"
#undef main
#include <type_traits>

static_assert(std::is_same_v<decltype(Scene{}.geometry),std::shared_ptr<const Geometry>>);
namespace topology_probe {
int effect=0,fired=0;
void cold_failure() {
    // Trigger after a public design read, while cold metadata is provisional.
    if(fake::designs!=1||fired)return;
    ++fired;
    if(effect==0)++fake::round;
    if(effect==1)++fake::revision;
    if(effect==2)throw std::runtime_error("cold topology getter failure");
}
}
void topology_reset(unsigned count=2){reset(count);fake::fuel=100000;}
Field ranking_field(const Scene& s) {
    Field f;f.width=s.width;f.height=s.height;f.origin=s.economy.self.pos;
    f.epoch=s.economy.self.epoch;f.graph=1;f.complete=true;
    f.blocked.assign(f.width*f.height,0);f.covered.assign(f.blocked.size(),1);
    f.distances.assign(f.blocked.size(),1);f.distances[f.origin.y*f.width+f.origin.x]=0;
    return f;
}
void rejects_geometry(const Scene& s,const Field& f) {
    Candidates candidates;candidates.begin(s,f,{});unsigned writes=0;
    CHECK(candidates.continue_build(s,f,{},writes)==CandidatesStatus::capacity);
    CHECK(candidates.options().empty()&&writes==0);
}
int main(){try {
    (void)self();
    topology_reset();{
        Context c;auto before=c.read();auto frozen=before;
        CHECK(before.geometry&&before.geometry->groups.size()==1);
        const auto& metadata=before.geometry->groups[0];
        CHECK(metadata.anchor==Point{8,7}&&metadata.gems==343&&metadata.gold==20);
        CHECK(metadata.spawn.size()==2&&metadata.spawn[0]==Point{8,7});
        const auto old_position=before.members[1].pos;const auto old_hp=before.members[1].hp;
        const auto old_epoch=before.economy.self.epoch;
        c.next();fake::camps()[1].pos={9,8};fake::camps()[1].hp=121;fake::lifecycle=2;
        auto changed=c.read();
        CHECK(changed.geometry==before.geometry&&frozen.geometry==before.geometry&&fake::designs==1);
        CHECK(changed.members[1].pos==Point{9,8}&&changed.members[1].hp==121);
        CHECK(changed.groups[0].observation.life==Life::reward&&changed.groups[0].observation.fresh);
        CHECK(changed.members[1].hp_epoch==changed.economy.self.epoch&&changed.economy.self.epoch!=old_epoch);
        CHECK(before.members[1].pos==old_position&&before.members[1].hp==old_hp);
        CHECK(frozen.members[1].pos==old_position&&frozen.members[1].hp==old_hp);
        CHECK(before.groups[0].observation.life==Life::living&&frozen.groups[0].observation.life==Life::living);
        CHECK(changed.geometry->groups[0].spawn[1]==old_position);
        c.next();fake::lifecycle=3;auto respawning=c.read();
        c.next();fake::lifecycle=1;auto next_cycle=c.read();
        CHECK(next_cycle.groups[0].observation.cycle==1&&respawning.groups[0].observation.cycle==0);
        CHECK(frozen.groups[0].observation.cycle==0&&next_cycle.geometry==frozen.geometry);
    }
    Scene escaped;std::weak_ptr<const Geometry> lifetime;
    topology_reset();{
        Context c;escaped=c.read();lifetime=escaped.geometry;
        CHECK(!lifetime.expired());
    }
    CHECK(!lifetime.expired()&&escaped.geometry->groups[0].spawn[0]==Point{8,7});
    CHECK(escaped.geometry->groups[0].gems==343&&escaped.members[0].hp==30);
    escaped=Scene{};CHECK(lifetime.expired());
    topology_reset();{
        Context c;auto original=c.w.camps[0];c.w.camps.clear();
        for(unsigned i=0;i<2;++i) {
            auto member=original.group.camps()[i];std::vector<camp> members{member};
            auto handle=cambc::detail::handle_access::make_camp_group(static_cast<handle_camp_group_t>(i),
                20+i,343+i,10,std::move(members));
            c.w.camps.push_back({handle,member.spawn_position(),{},{}});
        }
        auto s=c.read();CHECK(s.geometry->groups.size()==2&&s.groups.size()==2);
        for(unsigned i=0;i<2;++i) {
            CHECK(s.geometry->groups[i].anchor==s.members[i].pos&&s.geometry->groups[i].spawn.size()==1);
            CHECK(s.geometry->groups[i].gems==343+i&&s.geometry->groups[i].gold==20+i);
            CHECK(s.members[i].group==int(i)&&s.groups[i].observation.object==int(i));
        }
    }
    topology_reset();{
        Context c;c.w.camps.push_back(c.w.camps[0]);bool caught=false;
        try{c.read();}catch(const std::runtime_error& e){caught=std::string(e.what())=="economic scene capacity/metadata";}
        CHECK(caught&&fake::designs==1);c.w.camps.pop_back();c.next();auto coherent=c.read();
        CHECK(coherent.geometry->groups.size()==1&&coherent.members.size()==2&&fake::designs==2);
    }
    for(int effect=0;effect<3;++effect) {
        topology_reset();Context c;topology_probe::effect=effect;topology_probe::fired=0;
        fake::fuel_hook=topology_probe::cold_failure;bool caught=false,published=false;
        try{auto provisional=c.read();(void)provisional;published=true;}
        catch(TurnExpired){caught=effect!=2;}
        catch(const std::runtime_error& e){caught=effect==2&&std::string(e.what())=="cold topology getter failure";}
        CHECK(caught&&!published&&topology_probe::fired==1&&fake::designs==1);
        fake::fuel_hook=nullptr;c.next();auto coherent=c.read();
        CHECK(coherent.economy.complete&&coherent.geometry&&coherent.geometry->groups.size()==1);
        CHECK(coherent.geometry->groups[0].spawn.size()==2&&coherent.members.size()==2&&fake::designs==2);
        CHECK(coherent.groups[0].observation.cycle==0&&coherent.groups[0].observation.fresh);
    }
    // Failure after a complete static build must not commit dynamic lifecycle.
    for(int failure=0;failure<3;++failure) {
        topology_reset();Context c;fake::lifecycle=3;auto before=c.read();auto frozen=before;
        c.next();fake::lifecycle=1;fake::camps()[1].pos={9,8};
        fake::roll_locks=failure==0;fake::revise_locks=failure==1;fake::error_locks=failure==2;
        bool caught=false,published=false;
        try{auto provisional=c.read();(void)provisional;published=true;}
        catch(TurnExpired){caught=true;}catch(const cambc::error&){caught=true;}
        CHECK(caught&&!published);
        fake::roll_locks=fake::revise_locks=fake::error_locks=false;fake::camps()[1].visible=false;
        c.next();auto after=c.read();
        CHECK(after.geometry==before.geometry&&after.groups[0].observation.cycle==1);
        CHECK(frozen.groups[0].observation.cycle==0&&frozen.groups[0].observation.life==Life::respawning);
        CHECK(!after.members[1].known&&after.members[1].pos==before.members[1].pos);
    }
    topology_reset();{
        Context c;auto before=c.read();auto first=c.basic(before);CHECK(first.accepted());
        const int reads=fake::camp_reads,identities=fake::camp_identities;
        auto after=c.read();CHECK(after.geometry==before.geometry&&!after.members[0].alive&&before.members[0].hp==30);
        CHECK(after.members[1].unchanged_event==first.event&&after.members[1].hp_epoch==before.economy.self.epoch);
        CHECK(c.ledger.observe(first.event,c.turn.epoch()));auto reset_result=c.reset();CHECK(reset_result.accepted());
        auto reset_after=c.read();CHECK(reset_after.geometry==before.geometry&&reset_after.can_attack);
        CHECK(reset_after.members[1].unchanged_event==reset_result.event&&after.members[1].unchanged_event==first.event);
        CHECK(fake::camp_reads==reads&&fake::camp_identities==identities&&fake::designs==1);
        auto f=ranking_field(reset_after);auto missing=reset_after;missing.geometry.reset();rejects_geometry(missing,f);
        auto mismatch=reset_after;mismatch.geometry=std::make_shared<const Geometry>();rejects_geometry(mismatch,f);
        // Also validate at continuation, before dereferencing an altered scene.
        Candidates candidates;candidates.begin(reset_after,f,{});unsigned writes=0;
        CHECK(candidates.continue_build(missing,f,{},writes)==CandidatesStatus::capacity&&writes==0);
    }
    std::cout<<"PASS: "<<checks<<" actual-SDK topology/lifetime/publication assertions\n";
    std::cout<<"LIMIT: scripted host; no engine fuel, aggregate memory or strength claim\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
