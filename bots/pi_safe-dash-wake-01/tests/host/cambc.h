#pragma once
#include <algorithm>
#include <cmath>
#include <vector>
#include <variant>
#include <optional>
#include <span>
#include <set>
#include <map>
#include <string>
#include <stdexcept>
namespace cambc {
struct vec2 {int x=0,y=0;friend auto operator<=>(const vec2&,const vec2&)=default;};
using handle_camp_t=int;using handle_champion_t=int;
inline int epoch=1,fuel=100000,queries=0,trip=0,trip_fuel=-1,fields=0,actions=0,dashes=0,moves=0,fail_moves=0;
inline std::vector<std::string> trace;
inline void query(const char* name){trace.push_back(name);if(++queries==trip){if(trip_fuel<0)++epoch;else fuel=trip_fuel;}}
inline int round_queries=0,fuel_queries=0;
inline unsigned round_number(){++round_queries;return epoch;}
inline unsigned fuel_remaining(){++fuel_queries;return fuel;}
inline vec2 origin,endpoint,ordinary;inline bool reached_field=true;inline int field_fuel=20000;
struct bitboard {
 std::set<vec2> data;
 void set(vec2 p,bool yes=true){if(yes)data.insert(p);else data.erase(p);}
 bool is_set(vec2 p)const{return data.contains(p);}bool is_empty()const{return data.empty();}
 auto positions()const{return std::vector<vec2>(data.begin(),data.end());}
 void draw_chebyshev(vec2 p,int r){for(int x=p.x-r;x<=p.x+r;++x)for(int y=p.y-r;y<=p.y+r;++y)set({x,y});}
 bitboard reachable_tiles(vec2,int range)const {bitboard b;b.set(origin);if(!is_set(ordinary))b.set(ordinary);if(range>1&&!is_set(endpoint))b.set(endpoint);return b;}
 bitboard& operator|=(const bitboard& b){data.insert(b.data.begin(),b.data.end());return *this;}
 bitboard& operator&=(const bitboard& b){std::erase_if(data,[&](vec2 p){return !b.is_set(p);});return *this;}
 friend bitboard operator~(bitboard b){bitboard c;for(int x=0;x<64;++x)for(int y=0;y<64;++y)if(!b.is_set({x,y}))c.set({x,y});return c;}
 friend bitboard operator&(bitboard a,const bitboard& b){return a&=b;}
};
struct distance_field {
 void compute_to(bitboard,bitboard,bitboard,bitboard& r){++fields;fuel=std::min(fuel,field_fuel);if(reached_field)r.set(origin);}
 int get(vec2 p)const{return p==origin?10:p==endpoint?1:p==ordinary?9:100;}
};
struct CampData {int identity;vec2 pos;bool awake=false,alive=true,visible=true;float strength=60;int range=4;};
inline std::map<int,CampData> camp_data;
struct camp_state {bool living,awake;bool is_alive()const{return living;}bool is_awake()const{return awake;}};
struct camp {
 int identity=0;operator handle_camp_t()const{return identity;}
 const CampData& live(const char* name)const {if(!camp_data.at(identity).visible)throw std::runtime_error("hidden live query");query(name);return camp_data.at(identity);}
 camp_state state()const {auto& d=live("camp.state");return {d.alive,d.awake};}
 vec2 position()const{return live("camp.position").pos;}
 float strength()const{return live("camp.strength").strength;}
 int attack_range()const{return live("camp.range").range;}
};
struct ability_dash {float range=3,radius=1,modifier=2;int duration=1;bool exclusive_with_movement=false;};
inline ability_dash dash;inline float actor_focus=233,actor_hp=1000,actor_shield=0;
struct ability {
 bool is_dash()const{return true;}bool is_ready()const{return true;}
 std::optional<std::variant<ability_dash>> info()const{return dash;}
 template<class T>T get()const{return dash;}
 bool use(vec2 p)const{if(p!=endpoint)throw std::runtime_error("changed endpoint");++actions;++dashes;return true;}
};
struct champion {
 int identity=0;vec2 pos{};operator handle_champion_t()const{return identity;}
 bool is_alive()const{return true;}bool is_recalling()const{return false;}bool is_submitting_gems()const{return false;}bool is_teleporting()const{return false;}
 bool can_move()const{return true;}bool can_cast()const{return true;}
 vec2 position()const{return pos;}
 float focus()const{query("self.focus");return actor_focus;}
 std::vector<ability> abilities()const{return {ability{}};}
};
inline champion actor;inline champion& self(){return actor;}
namespace vision {inline std::vector<camp> camps(){query("vision.camps");std::vector<camp> v;for(auto& [i,d]:camp_data)if(d.visible)v.push_back({i});return v;}}
enum class team {ally,enemy};
namespace map {
 struct camp_group {std::vector<camp> storage;std::span<const camp> camps()const{return storage;}};
 inline bitboard spawn_region(team){bitboard b;b.set(endpoint);return b;}
}
}
