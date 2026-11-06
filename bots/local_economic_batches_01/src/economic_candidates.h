#pragma once
#include "economic_scene.h"
#include "economic_route.h"
#include <array>
namespace lp {
enum class DeliveryStatus:std::uint8_t { pending, finite, no_altar, no_root, no_capture, disconnected, capacity };
struct DeliveryEstimate {
    std::uint16_t walk_edges=65535;
    DeliveryStatus status=DeliveryStatus::pending;
    std::uint8_t flags=3; // static walking model, optimistic group minimum
};
static_assert(sizeof(DeliveryEstimate)==4);
namespace economic {
// Default native-duration contract only. A different setting/modifier leaves
// the estimate unpriced, without prohibiting the actual action.
struct RankingSettings {
    int capture_time=5,submit_range=1;
    bool duration_supported=false,tribute=false,capture_supported=true,submission_available=true;
    int capture_cap=-1;
    std::uint64_t winning_gems=0;
};
enum class CandidatesStatus { planning, ready, capacity, stale };
class Candidates {
    enum class Stage { groups, members, contacts, allies, finish_group, altars, bank_path, finished } stage=Stage::finished;
    action::Epoch epoch;
    std::uint64_t graph=0;
    Point origin;
    RankingSettings settings;
    std::vector<Candidate> result;
    Candidate current;
    unsigned group=0,member=0,ally=0,spawn=0,altar=0;
    int dx=0,dy=0,radius=0;
    unsigned recipients=1;
    std::array<bool,32> counted{};
    bool priced=true,found=false,reward=false,observation_contact=false,path_known=true;
    bool capacity_failed=false;
    std::uint16_t best_distance=65535;
    Point center,best,path_cursor;
    unsigned path_steps=0;
    void contact(const Field&,Point);
    bool append(const Candidate&);
public:
    static constexpr unsigned capacity=512;
    void begin(const Scene&,const Field&,RankingSettings);
    CandidatesStatus continue_build(const Scene&,const Field&,
        const std::array<DeliveryEstimate,128>&,unsigned& shared_scalar_writes);
    const auto& options()const{return result;}
};
// Checked scale-1024 nominal basic work. This is a ranking estimate, never a
// solo-clear rejection or a service feasibility bound.
bool nominal_work(float hp,float basic,std::uint64_t& turns);
bool tribute_turns(std::uint64_t bag,bool completed_tribute,std::uint64_t& turns);
}
}
