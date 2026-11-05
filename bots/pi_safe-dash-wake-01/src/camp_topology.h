#pragma once
#include "observations.h"
namespace lp {
struct World;
// Borrowed only for a synchronous movement call after World::init. World.camps
// and its member vectors must not be mutated while this view is in use.
class CampTopologyView {
    const World* world_;
public:
    class Members {
        std::span<const camp> members_;
        friend class CampTopologyView;
        explicit Members(std::span<const camp> m):members_(m){}
    public:
        bool contains(handle_camp_t identity) const {
            for(const auto& c:members_) if(static_cast<handle_camp_t>(c)==identity)return true;
            return false;
        }
        const void* identity() const {return members_.data();}
    };
    explicit CampTopologyView(const World& w):world_(&w){}
    std::optional<Members> members(handle_camp_t) const;
};
}
