#pragma once
#include "inspection.h"
#include "feature_flags.h"
#include "feature_policy.h"
namespace lp {
struct FeatureState {
    Inspector inspector;
    std::uint64_t owned=0, joined=0;
    int last_created=-100, retry=0, target=-1, contact=-100;
    int missing=0, carrier_checked=-1, clear_round=-1, clear_turns=0;
    int bank_life=-1;
    bool accepted=false, arrived=false;
    std::array<unsigned,25> events{};
};
inline FeatureState& feature_state(){static FeatureState state;return state;}
}
