// Host fixture for executing verbatim production draft/route functions. Geometry
// and engine calls are deterministic substitutes; this is not an engine simulator.
#include <cambc.h>
#include "config.h"
#include "loop_planner.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <span>
#include <stdexcept>
#include <tuple>
#include <vector>
namespace cambc {
enum class team {ally,enemy};
struct vec2 {int x=0,y=0;};
struct bitboard {
    bool empty=false;
    int width() const {return 2;}
    std::vector<vec2> positions() const {return empty?std::vector<vec2>{}:std::vector<vec2>{{0,0}};}
    bitboard shift_right(int) const {return *this;} bitboard shift_up(int) const {return *this;}
};
inline bitboard operator|(bitboard a,bitboard){return a;}
inline bitboard operator&(bitboard a,bitboard){return a;}
inline bitboard operator~(bitboard a){return a;}
struct distance_field {
    void compute(bitboard,bitboard,bitboard&) {}
    std::vector<std::uint16_t> export_linear_buffer() const {return {2,2,2,2};}
};
struct Stats {float base_health=1000,base_strength=10,strength_growth=2,base_focus=20,focus_growth=3;};
inline std::vector<champion_type> queried;
inline champion_type self_type=champion_type::heart_of_ruin;
struct champion {
    champion_type type;
    explicit champion(champion_type t):type(t){queried.push_back(t);}
    Stats base_stats() const {return {};}
    champion_type champion_name() const {return type;}
};
inline champion self(){return champion(self_type);}
namespace map {
struct camp {Stats base_stats() const {return {};}};
struct camp_group {
    bitboard spawn_tiles() const {return {};}
    std::vector<camp> camps() const {return {{}};}
    int gem_value() const {return 10;} int gold_value() const {return 20;}
    int max_respawn_timer() const {return 30;}
};
inline bool no_camps=false;
inline std::vector<camp_group> camp_groups(){return no_camps?std::vector<camp_group>{}:std::vector<camp_group>{{}};}
inline bitboard spawn_region(team){return {};}
inline bitboard altars(){return {};}
}
inline unsigned fuel=11000000;
inline unsigned fuel_remaining(){return fuel;}
struct Packet {
    std::vector<std::byte> bytes;
    std::vector<std::vector<std::uint8_t>> writes;
    Packet& operator=(const std::vector<std::uint8_t>& p){writes.push_back(p);return *this;}
    auto size() const {return bytes.size();}
    auto operator[](std::size_t i) const {return bytes.at(i);}
    void load(const std::vector<std::uint8_t>& p){bytes.clear();for(auto n:p)bytes.push_back(std::byte(n));}
};
inline Packet draft_memory;
namespace draft {
inline std::vector<champion_draft> chosen;
inline std::vector<champion_draft> picked;
inline std::vector<champion_draft> current_draft(team){return chosen;}
inline void pick(champion_draft d){picked.push_back(d);}
}
}
namespace lp {
using namespace cambc;
inline bitboard static_blocked(){return {};}
inline bitboard around(vec2,int){return {};}
struct World {
    std::vector<int> camps=std::vector<int>(24);
    std::vector<std::vector<int>> loop_routes;
    int loop_choice=0,loop_cursor=0,slot=0;
};
void prepare_draft_routes();
}
namespace subhan {
inline int calls=0,skip=-1,fail=-1;
inline std::vector<unsigned> shares;
std::vector<Loop> find_loops(const Inputs& data,const Config& cfg,const std::function<bool()>& stop) {
    int body=calls++;
    assert(data.camps.size()==1&&data.distances==std::vector<std::vector<int>>{{2}});
    assert(data.camps[0].service==(body==0||body==3?66:49));
    assert(cfg.report_limit==3&&cfg.max_camps==5);
    unsigned start=cambc::fuel;
    unsigned share=(start-1000000)/(5-body);shares.push_back(share);
    assert(!stop());cambc::fuel=start-share+1;assert(!stop());--cambc::fuel;assert(stop());
    if(body==fail)throw std::runtime_error("fixture interruption");
    if(body==skip)return {};
    std::vector<Loop> result(3);
    for(auto& loop:result){loop.altar=0;loop.route={0,0,0,0,0};}
    return result;
}
}
