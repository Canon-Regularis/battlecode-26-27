// Included after the actual SDK host seam; all actions below go through LiveBackend.
struct EpochFixture {
    World world;Memory memory;TurnBudget budget;RecoveryRuntime cache;
    EpochFixture():budget{fake::round} {
        fake::hide_after_motion=false;fake::epoch_mode=true;fake::attack_available=true;fake::dash_mode=false;fake::targets=false;
        fake::origin={10,10};fake::health=30;fake::move_available=true;fake::cast_available=true;
        fake::recalling=fake::recall_started=fake::recall_cancelled=false;
        fake::false_action=fake::throw_action=fake::defense_changes=false;
        fake::conversion_after_action=0;
        fake::transition=fake::transition_export=fake::after_action=fake::revision_export=0;
        fake::live_memory=&memory;fake::log.clear();fake::heal_ready=false;
        self()=cambc::detail::handle_access::make_champion(static_cast<handle_champion_t>(1));
        world.width=45;world.height=30;
        LiveBackend backend(world,memory,budget,cache);
        assert(backend.prepare(backend.turn)==Status::ready);
    }
    Outcome run(){return recover(Intent::health,world,memory,budget,cache);}
};
template<class F> void stale(F f){try{f();assert(false);}catch(Halt h){assert(h.status==Status::stale);}}
void epoch_regressions(){
    // The extracted production functions really increment on every invalidation.
    auto revision=observation_version();invalidate_observations();invalidate_observations();
    assert(observation_version()==revision+2);
    {
        EpochFixture f;fake::dash_mode=true;self()=cambc::detail::handle_access::make_champion(static_cast<handle_champion_t>(1));
        LiveBackend b(f.world,f.memory,f.budget,f.cache);const auto dispatch=b.turn;
        Scene old;assert(b.capture(old)==Status::ready);
        auto rev=observation_version();int actions=fake::actions;
        assert(b.issue(old,{Kind::step,{9,9}}));
        assert(fake::origin==vec2(9,9)&&!fake::move_available&&observation_version()==rev+1);
        stale([&]{b.issue(old,{Kind::dash,{7,7},0});});assert(fake::actions==actions+1);
        Scene fresh;assert(b.capture(fresh)==Status::ready&&fresh.movement_spent&&!fresh.can_move&&fresh.dash.available);
        assert(b.turn==dispatch&&fresh.epoch.revision>dispatch.revision);
        assert(b.issue(fresh,{Kind::dash,{7,7},0}));assert(fake::origin==vec2(7,7)&&!fake::cast_available);
        Scene after;assert(b.capture(after)==Status::ready);
        assert(fake::log==std::vector<Kind>({Kind::step,Kind::dash}));
    }
    {
        EpochFixture f;fake::dash_mode=true;self()=cambc::detail::handle_access::make_champion(static_cast<handle_champion_t>(1));
        auto result=f.run();
        assert(result.dashes==1&&result.moves==1&&result.recall_starts==1&&result.status==Status::channeling);
        assert(fake::log==std::vector<Kind>({Kind::dash,Kind::step,Kind::recall}));
        assert(result.captures==4&&fake::recalling&&!fake::move_available&&!fake::cast_available);
        std::cout<<"PASS: actual controller dash -> refreshed step -> health recall, four captures\n";
    }
    {
        EpochFixture f;fake::origin={40,28};fake::targets=true;fake::hide_after_motion=true;auto result=f.run();
        assert(result.moves==1&&result.recall_starts==1&&result.status==Status::channeling&&result.captures==3);
        assert(fake::log==std::vector<Kind>({Kind::step,Kind::recall})&&!fake::targets);
    }
    {
        EpochFixture f;fake::origin={2,2};fake::recalling=true;
        auto result=f.run();
        assert(result.cancellations==1&&result.moves==1&&result.homeward&&result.recall_starts==0);
        assert(fake::log==std::vector<Kind>({Kind::cancel,Kind::step})&&fake::recall_cancelled&&!fake::recalling);
        assert(result.status!=Status::stale&&result.captures==3);
    }
    {
        EpochFixture f;fake::origin={2,2};fake::recalling=true;fake::move_available=false;
        auto result=f.run();
        assert(result.status==Status::cancelled_wait&&result.cancellations==1&&result.moves==0);
        assert(fake::log==std::vector<Kind>({Kind::cancel}));
    }
    {
        EpochFixture f;fake::origin={40,28};fake::move_available=false;
        fake::targets=true;fake::defense_changes=true;
        int attacks=fake::attacks;auto rev=observation_version();auto result=f.run();
        // Actual basic attack removes the foe in the host seam; it does not heal self.
        // Fresh enemy/HP/permission data allows the health-recall footer.
        assert(fake::attacks==attacks+1&&fake::health==25&&!fake::targets&&!fake::cast_available);
        assert(result.defenses==1&&result.recall_starts==1&&result.status==Status::channeling&&result.captures==3);
        assert(observation_version()==rev+2);
        LiveBackend b(f.world,f.memory,f.budget,f.cache);Scene after;
        assert(b.capture(after)==Status::ready&&after.hp==25&&after.enemies.empty()&&!after.can_cast&&after.recalling);
    }
    // A revision change *inside* SDK positions() is stale for every conversion,
    // including after one committed motion; no defense or recall follows.
    for(int offset:{1,2}){
        EpochFixture f;LiveBackend b(f.world,f.memory,f.budget,f.cache);
        Scene s;assert(b.capture(s)==Status::ready);assert(b.issue(s,{Kind::step,{9,9}}));
        int actions=fake::actions;fake::revision_export=fake::exports+offset;
        Scene fresh;stale([&]{b.capture(fresh);});assert(fake::actions==actions);
    }
    // Actor/life/round transitions before, during conversion, and after the first
    // action must preserve exactly that action, never a second action/footer.
    for(int identity:{1,2,3})for(int phase:{0,1,2,3}){
        EpochFixture f;fake::transition=identity;
        LiveBackend b(f.world,f.memory,f.budget,f.cache);Scene s;
        assert(b.capture(s)==Status::ready);int actions=fake::actions;
        if(phase==0){fake::rollover();bitboard board;int exports=fake::exports;
            stale([&]{b.scalar(board,45,30);});assert(fake::exports==exports);stale([&]{b.issue(s,{Kind::step,{9,9}});});assert(fake::actions==actions);}
        if(phase==1){fake::transition_export=fake::exports+1;Scene next;stale([&]{b.capture(next);});
            stale([&]{b.issue(s,{Kind::step,{9,9}});});assert(fake::actions==actions);}
        if(phase>=2){if(phase==2)fake::after_action=1;else fake::conversion_after_action=1;auto result=execute(Intent::health,f.memory,b);
            assert(result.status==Status::stale&&result.moves==1&&result.history.size()==1&&result.defenses==0&&result.recall_starts==0);
            assert(fake::actions==actions+1);}
    }
    for(bool revision_change:{false,true}){
        EpochFixture f;int actions=fake::actions;
        fake::conversion_after_action=revision_change?2:3;
        auto result=f.run();
        assert(result.status==(revision_change?Status::stale:Status::incomplete));
        assert(result.moves==1&&result.history.size()==1&&result.defenses==0&&result.recall_starts==0&&fake::actions==actions+1);
        fake::fuel_export=0;fake::fuel=100000;
    }
    // Boolean false wrappers still invalidate; unexpected SDK exceptions do not
    // acquire new invalidation behavior and escape without continuation.
    for(bool dash:{false,true})for(bool throws:{false,true}){
        EpochFixture f;fake::dash_mode=dash;self()=cambc::detail::handle_access::make_champion(static_cast<handle_champion_t>(1));
        LiveBackend b(f.world,f.memory,f.budget,f.cache);Scene old;
        assert(b.capture(old)==Status::ready);int actions=fake::actions;auto rev=observation_version();
        fake::false_action=!throws;fake::throw_action=throws;
        if(throws){try{execute(Intent::health,f.memory,b);assert(false);}catch(const cambc::error& e){assert(e.code()==error_code::api_not_found);}
            assert(observation_version()==rev);}
        else {auto result=execute(Intent::health,f.memory,b);assert(result.status==Status::blocked&&result.defenses==0&&result.recall_starts==0);
            assert(observation_version()==rev+1);stale([&]{b.issue(old,{Kind::step,{9,9}});});}
        assert(fake::actions==actions+1&&fake::log.empty());
    }
    {
        EpochFixture f;fake::origin={41,28};fake::targets=true;fake::move_available=false;fake::heal_ready=true;fake::false_action=true;
        auto rev=observation_version();int actions=fake::actions;
        auto result=f.run();
        assert(result.status==Status::stale&&result.defenses==0&&result.recall_starts==0);
        assert(fake::actions==actions+1&&observation_version()==rev+1);
    }
    std::cout<<"PASS: actual move/dash/cancel/recall/attack host transitions; fresh epochs, stale scenes, rollover and errors\n";
}
