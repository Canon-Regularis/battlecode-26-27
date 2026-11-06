#include "economic_fields_sdk.h"
#include <algorithm>
namespace lp {
namespace {
vec2 tile(economic::Point p){return {p.x,p.y};}
bool bit(const std::vector<std::uint8_t>& bytes,unsigned cell){return (bytes[cell/8]>>(cell%8))&1;}
}
bool EconomicFields::scope(const World& w)const {
    if(w.width<=0||w.height<=0||w.width>16384/w.height||w.camps.size()>128)return false;
    unsigned members=0;
    for(const auto& group:w.camps) {
        members+=group.group.camps().size();if(members>256)return false;
        for(const auto& c:group.group.camps()) {
            const auto p=c.spawn_position();if(p.x<0||p.y<0||p.x>=w.width||p.y>=w.height)return false;
        }
    }
    for(auto p:w.altars)if(p.x<0||p.y<0||p.x>=w.width||p.y>=w.height)return false;
    return true;
}
bool EconomicFields::eligible(LiveTurn& turn) {
    turn.check();return turn.ledger().fields==0&&turn.ledger().planning_jobs==0&&fuel_remaining()>=Config::field_admission;
}
bool EconomicFields::job_turn(LiveTurn& turn) {
    turn.check();const int round=turn.epoch().round;
    if(round!=job_round){job_round=round;++job_turns;}
    return job_turns<=8;
}
void EconomicFields::release() {
    field_={};packed_blocked={};packed_covered={};stage=Stage::none;
    conversion=reduction=job_turns=0;job_round=-1;
}
FieldStatus EconomicFields::prepare_delivery(World& w,LiveTurn& turn,unsigned& writes) {
    turn.check();if(delivery_ready_)return FieldStatus::ready;
    if(!scope(w))return FieldStatus::capacity;
    if(stage==Stage::origin)return FieldStatus::deferred;
    if(stage==Stage::none) {
        if(w.altars.empty()) {
            if(writes>economic::Route::scalar_batch||w.camps.size()>economic::Route::scalar_batch-writes)return FieldStatus::planning;
            for(unsigned g=0;g<w.camps.size();++g)delivery_[g]={65535,DeliveryStatus::no_altar,3};
            writes+=unsigned(w.camps.size());delivery_ready_=true;return FieldStatus::ready;
        }
        if(!eligible(turn))return FieldStatus::deferred;
        if(delivery_attempts>=8)return FieldStatus::unavailable;
        ++delivery_attempts;++turn.ledger().planning_jobs;
        const auto epoch=turn.epoch();auto read=[&](auto f){return turn.read(f);};
        auto walls=read([]{return static_blocked();});bitboard roots;
        if(walls.width()!=w.width||walls.height()!=w.height)return FieldStatus::capacity;
        for(auto altar:w.altars)read([&]{roots.draw_chebyshev(altar,constants::submit_gems_range);return true;});
        roots=read([&]{return roots&~walls;});
        if(read([&]{return roots.is_empty();})) {
            if(writes>economic::Route::scalar_batch||w.camps.size()>economic::Route::scalar_batch-writes)return FieldStatus::planning;
            for(unsigned g=0;g<w.camps.size();++g)delivery_[g]={65535,DeliveryStatus::no_root,3};
            writes+=unsigned(w.camps.size());delivery_ready_=true;return FieldStatus::ready;
        }
        distance_field native;bitboard visited;
        ++turn.ledger().fields;
        read([&]{native.compute(walls,roots,visited);return true;});
        auto distances=read([&]{return native.export_linear_buffer();});
        auto packed=read([&]{return walls.export_linear_buffer();});
        if(distances.size()!=unsigned(w.width*w.height)||packed.size()!=(distances.size()+7)/8)return FieldStatus::capacity;
        turn.check();if(turn.epoch()!=epoch)throw TurnExpired{};
        field_.epoch=epoch;field_.width=w.width;field_.height=w.height;field_.distances=std::move(distances);
        packed_blocked=std::move(packed);stage=Stage::delivery;
    }
    if(reduction<w.camps.size()&&(writes>economic::Route::scalar_batch||
        w.camps[reduction].group.camps().size()+1>economic::Route::scalar_batch-writes))return FieldStatus::planning;
    if(!job_turn(turn)){release();return FieldStatus::unavailable;}
    while(reduction<w.camps.size()) {
        const auto members=w.camps[reduction].group.camps();
        const unsigned cost=unsigned(members.size())+1;
        if(writes>economic::Route::scalar_batch||cost>economic::Route::scalar_batch-writes)return FieldStatus::planning;
        unsigned best=65535,legal=0;
        for(const auto& member:members) {
            auto p=member.spawn_position();const unsigned cell=unsigned(p.y*w.width+p.x);
            if(!bit(packed_blocked,cell)){++legal;best=std::min(best,unsigned(field_.distances[cell]));}
        }
        delivery_[reduction++]={std::uint16_t(best),!legal?DeliveryStatus::no_capture:
            best==65535?DeliveryStatus::disconnected:DeliveryStatus::finite,3};
        writes+=cost;turn.check();
    }
    delivery_ready_=true;release();return FieldStatus::ready;
}
FieldStatus EconomicFields::start_origin(World& w,const economic::Scene& scene,LiveTurn& turn) {
    turn.check();if(stage!=Stage::none)return FieldStatus::planning;
    if(!scope(w)||!scene.economy.complete||!scene.economy.self.alive||
        scene.economy.self.channel!=economic::Channel::none)return FieldStatus::capacity;
    if(scene.economy.self.epoch!=turn.epoch())return FieldStatus::stale;
    if(!eligible(turn))return FieldStatus::deferred;
    if(next_graph==UINT64_MAX)return FieldStatus::unavailable;
    auto read=[&](auto f){return turn.read(f);};const auto epoch=turn.epoch();const auto origin=tile(scene.economy.self.pos);
    auto walls=read([]{return static_blocked();});
    if(walls.width()!=w.width||walls.height()!=w.height||!scene.inside(scene.economy.self.pos))return FieldStatus::capacity;
    if(read([&]{return walls.is_set(origin);}))return FieldStatus::unavailable; // never erase terrain
    auto camps=read([]{return vision::camp_tiles();});
    auto teleports=read([]{return vision::teleport_tiles();});
    if(read([&]{return camps.is_set(origin)||teleports.is_set(origin);}))return FieldStatus::unavailable;
    auto actors=read([]{return vision::champion_tiles();});
    read([&]{actors.set(origin,false);return true;}); // only dynamic self occupancy
    auto occupied=read([&]{return camps|actors|teleports;});
    bitboard risk;auto covered=read([]{return vision::visible_tiles();});
    for(const auto& enemy:scene.enemies)if(enemy.alive)
        read([&]{risk.draw_chebyshev(tile(enemy.pos),enemy.range+enemy.move_range);return true;});
    for(const auto& camp:scene.members)if(!camp.passive) {
        if(camp.known&&camp.alive&&camp.visible&&camp.awake&&camp.strength>0)
            read([&]{risk.draw_chebyshev(tile(camp.pos),camp.range);return true;});
        else if(!camp.known) {
            bitboard uncertain;read([&]{uncertain.draw_chebyshev(tile(camp.pos),camp.range);return true;});
            covered=read([&]{return covered&~uncertain;});
        }
    }
    if(read([&]{return risk.is_set(origin);}))return FieldStatus::exposed;
    auto blocked=read([&]{return walls|occupied|risk;});bitboard roots;
    read([&]{roots.set(origin,true);return true;});
    ++turn.ledger().planning_jobs;++turn.ledger().fields;
    distance_field native;bitboard visited;read([&]{native.compute(blocked,roots,visited);return true;});
    auto distances=read([&]{return native.export_linear_buffer();});
    auto packed=read([&]{return blocked.export_linear_buffer();});
    auto coverage=read([&]{return covered.export_linear_buffer();});
    const unsigned cells=unsigned(w.width*w.height);
    if(distances.size()!=cells||packed.size()!=(cells+7)/8||coverage.size()!=packed.size()||
        distances[unsigned(origin.y*w.width+origin.x)]!=0)return FieldStatus::capacity;
    turn.check();if(turn.epoch()!=epoch)throw TurnExpired{};
    field_={epoch,scene.economy.self.pos,w.width,w.height,next_graph++,false,{},{},std::move(distances)};
    field_.blocked.reserve(cells);field_.covered.reserve(cells);
    packed_blocked=std::move(packed);packed_covered=std::move(coverage);stage=Stage::origin;
    conversion=job_turns=0;job_round=-1;return FieldStatus::planning;
}
FieldStatus EconomicFields::continue_origin(LiveTurn& turn,economic::Point origin,unsigned& writes) {
    turn.check();if(stage!=Stage::origin)return FieldStatus::unavailable;
    const auto epoch=turn.epoch();
    if(epoch.actor!=field_.epoch.actor||epoch.life!=field_.epoch.life||origin!=field_.origin) {
        release();return FieldStatus::stale;
    }
    field_.conditional|=epoch!=field_.epoch;
    if(writes>economic::Route::scalar_batch)return FieldStatus::capacity;
    if(writes+2>economic::Route::scalar_batch)return FieldStatus::planning;
    if(!job_turn(turn)){release();return FieldStatus::unavailable;}
    const unsigned n=unsigned(field_.width*field_.height);
    while(conversion<n&&writes+2<=economic::Route::scalar_batch) {
        field_.blocked.push_back(bit(packed_blocked,conversion));
        field_.covered.push_back(bit(packed_covered,conversion));++conversion;writes+=2;
    }
    turn.check();if(turn.epoch()!=epoch)throw TurnExpired{};
    if(conversion<n)return FieldStatus::planning;
    field_.complete=true;return FieldStatus::ready;
}
economic::Field EconomicFields::take_origin() {
    if(stage!=Stage::origin||!field_.complete)return {};
    auto out=std::move(field_);release();return out;
}
}
