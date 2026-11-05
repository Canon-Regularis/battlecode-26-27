using D=cambc::champion_draft;using T=cambc::champion_type;
const std::vector<T> expected_types{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren,T::vendetta};
void reset() {
    cambc::draft_memory=cambc::Packet{};cambc::queried.clear();cambc::fuel=11000000;
    cambc::map::no_camps=false;subhan::calls=0;subhan::skip=-1;subhan::fail=-1;subhan::shares.clear();
}
int main() {
    // Call the real draft producer for every prefix, including 3/4/5 choices and
    // fallback picks through all twelve entries. No team-size query is supplied.
    for(std::size_t i=0;i<=lp::roster::preferences.size();++i) {
        reset();cambc::draft::picked.clear();
        cambc::draft::chosen.assign(lp::roster::preferences.begin(),lp::roster::preferences.begin()+i);
        play_draft();
        assert(cambc::draft::picked.size()==(i<12?1:0));
        if(i<12)assert(cambc::draft::picked[0]==lp::roster::preferences[i]);
        assert(subhan::calls==(i==0?5:0));
    }
    for(int choices:{3,4,5}) {
        reset();cambc::draft::chosen.resize(choices);lp::prepare_draft_routes();
        assert(cambc::queried==expected_types&&subhan::calls==5);
        assert(subhan::shares==std::vector<unsigned>(5,2000000));
        auto writes=cambc::draft_memory.writes;
        assert(writes.size()==6&&writes[0]==std::vector<std::uint8_t>({'S','L','P',1,0}));
        for(int i=1;i<=5;++i) {
            assert(writes[i].size()==std::size_t(5+41*i)&&writes[i][4]==i);
            for(int j=0;j<i;++j)assert(writes[i][5+41*j]==int(expected_types[j]));
            assert(std::equal(writes[i-1].begin()+5,writes[i-1].end(),writes[i].begin()+5));
        }
        std::vector<std::uint8_t> exact{'S','L','P',1,5};
        for(auto type:expected_types) {
            exact.push_back(int(type));exact.push_back(3);
            for(int route=0;route<3;++route){exact.push_back(5);exact.insert(exact.end(),12,0);}
        }
        assert(writes.back()==exact);
        assert(writes.back().size()==210&&5+6*(2+3*(3+2*5))==251&&251<1024);
        // Read actual producer bytes with the actual loader for all physical types.
        for(int type=0;type<13;++type)for(int slot=0;slot<6;++slot) {
            cambc::draft_memory.load(writes.back());cambc::self_type=T(type);lp::World w;w.slot=slot;
            lp::load_draft_routes(w);
            bool owner=std::find(expected_types.begin(),expected_types.end(),T(type))!=expected_types.end();
            assert(w.loop_routes.size()==(owner?3:0));if(owner)assert(w.loop_choice==slot%3);
        }
    }
    reset();subhan::skip=1;lp::prepare_draft_routes();
    assert(cambc::draft_memory.writes.size()==5&&cambc::draft_memory.writes.back()[4]==4);
    cambc::draft_memory.load(cambc::draft_memory.writes.back());cambc::self_type=T::marcella;
    lp::World missing;lp::load_draft_routes(missing);assert(missing.loop_routes.empty());
    reset();subhan::fail=2;
    try {lp::prepare_draft_routes();assert(false);}catch(const std::runtime_error&) {}
    assert(cambc::draft_memory.writes.size()==3&&cambc::draft_memory.writes.back()[4]==2);
    for(auto type:{T::heart_of_ruin,T::vesper_vale}) {
        cambc::draft_memory.load(cambc::draft_memory.writes.back());cambc::self_type=type;
        lp::World w;lp::load_draft_routes(w);assert(w.loop_routes.size()==(type==T::heart_of_ruin?3:0));
    }
    reset();cambc::map::no_camps=true;lp::prepare_draft_routes();
    assert(cambc::draft_memory.writes.size()==1&&subhan::calls==0);
    cambc::draft_memory.load(cambc::draft_memory.writes[0]);lp::World empty;
    lp::load_draft_routes(empty);assert(empty.loop_routes.empty());
    // Existing loader bounds and truncation behavior (including exceptions).
    for(auto bytes:std::vector<std::vector<std::uint8_t>>{
        {},{'X','L','P',1,0},{'S','L','P',1,14},
        {'S','L','P',1,1,12,4},{'S','L','P',1,1,12,1,6,0,0},
        {'S','L','P',1,1,12,1,1,0,0,24,0}}) {
        cambc::draft_memory.load(bytes);lp::World w;lp::load_draft_routes(w);assert(w.loop_routes.empty());
    }
    cambc::draft_memory.load({'S','L','P',1,1});
    try {lp::World w;lp::load_draft_routes(w);assert(false);}catch(const std::out_of_range&) {}
    std::cout<<"PASS: production draft, route producer, fuel shares, incremental packet ownership/fallback/bounds\n";
}
