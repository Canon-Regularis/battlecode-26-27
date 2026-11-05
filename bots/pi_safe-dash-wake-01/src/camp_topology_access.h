#pragma once
#include "objectives.h"
namespace lp {
inline std::optional<CampTopologyView::Members> CampTopologyView::members(handle_camp_t identity) const {
    for(const auto& objective:world_->camps) {
        Members result{objective.group.camps()};
        if(result.contains(identity))return result;
    }
    return std::nullopt;
}
}
