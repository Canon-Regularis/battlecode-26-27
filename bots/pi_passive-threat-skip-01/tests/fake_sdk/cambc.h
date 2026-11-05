// Minimal native test double. Production sources/headers are compiled unchanged.
// Not an engine, pathfinding implementation, or fuel model.
#pragma once
#include <algorithm>
#include <cmath>
#include <optional>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
namespace cambc {
struct vec2 { int x=0,y=0; bool operator==(const vec2&) const=default; };
inline constexpr int side=16;
struct bitboard {
    bool tiles[side*side]{};
    bool is_set(vec2 p) const {return p.x>=0&&p.y>=0&&p.x<side&&p.y<side&&tiles[p.y*side+p.x];}
    void set(vec2 p,bool v=true) {if(p.x>=0&&p.y>=0&&p.x<side&&p.y<side)tiles[p.y*side+p.x]=v;}
    void draw_chebyshev(vec2 p,int r) {for(int y=0;y<side;++y)for(int x=0;x<side;++x)if(std::max(std::abs(x-p.x),std::abs(y-p.y))<=r)set({x,y});}
    bool is_empty() const {for(bool t:tiles)if(t)return false;return true;}
    std::vector<vec2> positions() const {std::vector<vec2> v;for(int y=0;y<side;++y)for(int x=0;x<side;++x)if(is_set({x,y}))v.push_back({x,y});return v;}
    bitboard reachable_tiles(vec2 p,int r) const {bitboard b;b.draw_chebyshev(p,r);return b&~*this;}
    bitboard& operator|=(const bitboard& b) {for(int i=0;i<side*side;++i)tiles[i]|=b.tiles[i];return *this;}
    bitboard& operator&=(const bitboard& b) {for(int i=0;i<side*side;++i)tiles[i]&=b.tiles[i];return *this;}
    friend bitboard operator|(bitboard a,const bitboard& b){return a|=b;}
    friend bitboard operator&(bitboard a,const bitboard& b){return a&=b;}
    bitboard operator~() const {bitboard b;for(int i=0;i<side*side;++i)b.tiles[i]=!tiles[i];return b;}
    bool operator==(const bitboard&) const=default;
};
enum class team {ally,enemy};
enum class error_code {invalid_action_move_bad_destination};
struct error:std::runtime_error {error():std::runtime_error("fake"){} error_code code() const{return error_code::invalid_action_move_bad_destination;}};
struct buff_restrictions {static const buff_restrictions move;bool contains(buff_restrictions) const{return false;}};
inline const buff_restrictions buff_restrictions::move{};
struct ability_dash {int range=0;bool exclusive_with_movement=false;};
struct ability {
    const std::optional<std::variant<ability_dash>>& info() const {static std::optional<std::variant<ability_dash>> v;return v;}
    bool is_ready() const{return false;} bool is_dash() const{return false;}
    template<class T>T get() const{return {};}
    bool use(vec2) const{return false;}
};
using handle_champion_t=int;
struct champion {
    vec2 pos{5,5};float damage=11;int range=1,handle=1;
    operator handle_champion_t() const{return handle;}
    bool is_alive() const{return true;} bool can_move() const{return true;}
    bool can_cast() const{return false;}
    bool is_recalling() const{return false;} bool is_submitting_gems() const{return false;} bool is_teleporting() const{return false;}
    vec2 position() const{return pos;} float health() const{return 100;} float max_health() const{return 100;}
    int gem_count() const{return 0;} int attack_range() const{return range;} float strength() const{return damage;}
    buff_restrictions restrictions() const{return {};}
    std::vector<ability> abilities() const{return {};}
    bool move_absolute(vec2);
};
enum class camp_type {wolf,elk,gem_cluster,gold_cluster,monolith,golem};
struct camp {
    camp_type type;bool alive,awake;float damage;vec2 pos;int range;
    mutable std::string calls;
    bool is_gem_cluster() const{return type==camp_type::gem_cluster;}
    bool is_gold_cluster() const{return type==camp_type::gold_cluster;}
    bool is_alive() const{calls+='L';return alive;}
    bool is_awake() const{calls+='W';return awake;}
    float strength() const{calls+='S';return damage;}
    vec2 position() const{calls+='P';return pos;}
    int attack_range() const{calls+='R';return range;}
};
namespace fake {
inline champion me;
inline std::vector<camp> camps;
inline std::vector<champion> enemies;
inline bitboard occupied,field_blocked;
inline int enumerations=0,moves=0,fields=0;
}
inline champion& self(){return fake::me;}
inline int round_number(){return 10;}
inline unsigned fuel_remaining(){return 1000000;}
inline bool champion::move_absolute(vec2 p){++fake::moves;if(fake::occupied.is_set(p))throw error{};pos=p;return true;}
namespace vision {
inline const std::vector<camp>& camps(){++fake::enumerations;return fake::camps;}
inline bitboard visible_tiles(){bitboard b;b.draw_chebyshev({8,8},16);return b;}
inline bitboard champion_tiles(){return {};}
inline bitboard camp_tiles(){return fake::occupied;}
inline bitboard teleport_tiles(){return {};}
inline std::vector<champion> champions(team t){return t==team::enemy?fake::enemies:std::vector<champion>{};}
}
namespace map {
inline bitboard walls(){return {};} inline bitboard holes(){return {};} inline bitboard altars(){return {};}
inline bitboard spawn_region(team){return {};}
}
struct distance_field {
    // Capture the exact mask passed by production move_to; no route is reached.
    void compute_to(bitboard b,bitboard,bitboard,bitboard&){fake::field_blocked=b;++fake::fields;}
    int get(vec2) const{return 100;}
};
}
