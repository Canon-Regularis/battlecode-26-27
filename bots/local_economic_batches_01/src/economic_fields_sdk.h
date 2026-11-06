#pragma once
#include "economic_route.h"
#include "economic_candidates.h"
#include "economic_scene.h"
#include "live_turn.h"
#include "objectives.h"
namespace lp {
enum class FieldStatus { ready, planning, deferred, exposed, unavailable, capacity, stale };
// One native field job at a time. Static altar reduction releases its N-cell
// scratch before dynamic ranking. A completed origin field is MOVED into the
// retained route after all candidates inspect this same export.
class EconomicFields {
    enum class Stage { none, delivery, origin } stage=Stage::none;
    economic::Field field_;
    std::vector<std::uint8_t> packed_blocked,packed_covered;
    std::array<DeliveryEstimate,128> delivery_{};
    unsigned conversion=0,reduction=0,job_turns=0,delivery_attempts=0;
    int job_round=-1;
    bool delivery_ready_=false;
    std::uint64_t next_graph=1;
    bool scope(const World&)const;
    bool eligible(LiveTurn&);
    bool job_turn(LiveTurn&);
    void release();
public:
    const auto& delivery()const{return delivery_;}
    bool delivery_ready()const{return delivery_ready_;}
    bool origin_pending()const{return stage==Stage::origin;}
    const economic::Field& origin()const{return field_;}
    FieldStatus prepare_delivery(World&,LiveTurn&,unsigned& shared_scalar_writes);
    FieldStatus start_origin(World&,const economic::Scene&,LiveTurn&);
    FieldStatus continue_origin(LiveTurn&,economic::Point actual_origin,unsigned& shared_scalar_writes);
    economic::Field take_origin();
    // Release transient scratch before recovery or changed-origin planning.
    // Completed static delivery estimates and finite attempt counts survive.
    void cancel_pending(){release();}
};
}
