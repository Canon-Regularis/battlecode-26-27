#pragma once
// Native scenario host, deliberately independent of SDK buffer layout/ABI.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <queue>
#include <span>
#include <variant>
#include <vector>
namespace cambc {
inline constexpr int W=20,H=20;
struct vec2 {int x=0,y=0;friend bool operator==(vec2,vec2)=default;};
enum class team {ally,enemy};
enum class champion_type {heart_of_ruin,ren,marcella};
using handle_champion_t=int;
inline int host_round=100,host_score=0,score_calls=0,field_calls=0,attacks=0,moves=0,submissions=0;
inline unsigned host_fuel=100000;
inline std::function<void()> after_field,after_score,during_scoring;
inline int round_number(){return host_round;}
inline unsigned fuel_remaining(){return host_fuel;}
inline int global_submitted_gems(team){++score_calls;if(after_score)after_score();return host_score;}
struct bitboard {
    std::array<bool,W*H> bits{};
    int width() const{return W;} int height() const{return H;}
    bool is_set(vec2 p) const{return p.x>=0&&p.y>=0&&p.x<W&&p.y<H&&bits[p.y*W+p.x];}
    void set(vec2 p,bool v=true){if(p.x>=0&&p.y>=0&&p.x<W&&p.y<H)bits[p.y*W+p.x]=v;}
    bool is_empty() const{return std::none_of(bits.begin(),bits.end(),[](bool b){return b;});}
    void draw_chebyshev(vec2 p,int r){for(int y=0;y<H;++y)for(int x=0;x<W;++x)if(std::max(abs(x-p.x),abs(y-p.y))<=r)set({x,y});}
    std::vector<vec2> positions() const {std::vector<vec2> v;for(int y=0;y<H;++y)for(int x=0;x<W;++x)if(is_set({x,y}))v.push_back({x,y});return v;}
    friend bitboard operator~(bitboard a){for(auto& b:a.bits)b=!b;return a;}
    friend bitboard operator|(bitboard a,const bitboard& b){for(int i=0;i<W*H;++i)a.bits[i]=a.bits[i]||b.bits[i];return a;}
    friend bitboard operator&(bitboard a,const bitboard& b){for(int i=0;i<W*H;++i)a.bits[i]=a.bits[i]&&b.bits[i];return a;}
    bitboard& operator|=(const bitboard& b){return *this=*this|b;}
    bitboard& operator&=(const bitboard& b){return *this=*this&b;}
};
struct distance_field {
    std::vector<uint16_t> d=std::vector<uint16_t>(W*H,65535);
    void compute(const bitboard& blocked,const bitboard& roots,bitboard& reached){
        ++field_calls;std::queue<vec2> q;for(auto p:roots.positions()){q.push(p);d[p.y*W+p.x]=0;reached.set(p);}
        while(!q.empty()){auto p=q.front();q.pop();for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){vec2 n{p.x+dx,p.y+dy};if(n.x<0||n.y<0||n.x>=W||n.y>=H||blocked.is_set(n)||reached.is_set(n))continue;d[n.y*W+n.x]=d[p.y*W+p.x]+1;reached.set(n);q.push(n);}}
        if(after_field)after_field();
    }
    int get(vec2 p) const{return d[p.y*W+p.x];}
    auto export_linear_buffer() const{return d;}
};
struct altar_lock {vec2 p;int hits=5;vec2 position() const{return p;}int hits_remaining() const{return hits;}};
namespace vision {inline std::vector<altar_lock> locks;inline std::vector<altar_lock> altar_locks(team t){if(during_scoring)during_scoring();return t==team::enemy?locks:std::vector<altar_lock>{};}}
enum class consumable_type {altar_lock};
struct consumable {int count() const{return 0;}void use(vec2) const{}};
struct consumable_inventory {consumable operator[](consumable_type) const{return {};}};
struct champion_data {bool alive=true,submit=false,recall=false,teleport=false,move=true,attack=true;vec2 pos{2,2};int bag=8,gold=0;};
inline std::array<champion_data,3> actors;
struct champion {
    int n=0;explicit operator int() const{return n;}auto& data() const{return actors[n];}
    bool is_alive() const{return data().alive;}bool is_visible() const{return true;}
    bool is_submitting_gems() const{return data().submit;}bool is_recalling() const{return data().recall;}bool is_teleporting() const{return data().teleport;}
    vec2 position() const{return data().pos;}int gem_count() const{return data().bag;}int gold_count() const{return data().gold;}
    float strength() const{return 50;}float focus() const{return 0;}int attack_range() const{return 1;}
    bool can_move() const{return data().move;}bool can_attack() const{return data().attack;}
    bitboard attack_tiles() const{bitboard b;b.draw_chebyshev(position(),1);return b;}
    void attack(altar_lock) const{++attacks;}
    void submit_gems(vec2) const{++submissions;data().submit=true;}
    auto consumables() const{return consumable_inventory{};}
    int remaining_channel_time() const{return 5;}void set_priority(int) const{}
    void recall() const{data().recall=true;}void cancel_recall() const{data().recall=false;}
};
inline champion& self(){static champion me;return me;}
struct ability_info {bool exclusive_with_movement=false;};
struct ability {std::optional<std::variant<ability_info>> info() const{return std::nullopt;}bool is_ready() const{return false;}};
namespace map {
struct camp {vec2 p{3,2};bool is_visible() const{return true;}bool is_alive() const{return true;}vec2 position() const{return p;}vec2 spawn_position() const{return p;}};
struct camp_group {std::vector<camp> camps() const{return {{}};}int gem_value() const{return 4;}int gold_value() const{return 60;}};
}
struct shared_mem {void read(int,std::span<std::byte> b) const{std::fill(b.begin(),b.end(),std::byte{});}void write(int,std::span<std::byte>) const{}};
inline shared_mem shared_memory;
}
