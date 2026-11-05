#pragma once
#include <cambc.h>
#include <array>
#include <span>

namespace lp::roster {
// One ordered draft policy. Route preparation deliberately uses all five template
// choices even on three/four-choice maps: unused routes affect fuel allocation.
inline constexpr std::array original_preferences{
    cambc::champion_draft::heart_of_ruin, cambc::champion_draft::marcella,
    cambc::champion_draft::vesper_vale, cambc::champion_draft::ren,
    cambc::champion_draft::vendetta, cambc::champion_draft::varg,
    cambc::champion_draft::ryth, cambc::champion_draft::stellar,
    cambc::champion_draft::prism, cambc::champion_draft::willow,
    cambc::champion_draft::tavi, cambc::champion_draft::cassi_and_issac};

inline constexpr auto pair_preferences=[] {
    auto picks=original_preferences;
    auto ren=picks[3];picks[3]=picks.back();picks.back()=ren;
    return picks;
}();

template<std::size_t N, auto Preferences=original_preferences>
constexpr auto choice_prefix() {
    static_assert(N<=Preferences.size());
    std::array<cambc::champion_draft,N> result{};
    for(std::size_t i=0;i<N;++i)result[i]=Preferences[i];
    return result;
}

namespace detail {
struct Actors {std::array<cambc::champion_type,2> types;std::size_t count;};
constexpr Actors actors(cambc::champion_draft choice) {
    using D=cambc::champion_draft;using T=cambc::champion_type;
    // Draft and physical enum values diverge at the pair. Never cast between them.
    switch(choice) {
    case D::ryth:return {{T::ryth},1};
    case D::vesper_vale:return {{T::vesper_vale},1};
    case D::vendetta:return {{T::vendetta},1};
    case D::cassi_and_issac:return {{T::cassi,T::issac},2};
    case D::stellar:return {{T::stellar},1};
    case D::prism:return {{T::prism},1};
    case D::marcella:return {{T::marcella},1};
    case D::willow:return {{T::willow},1};
    case D::ren:return {{T::ren},1};
    case D::varg:return {{T::varg},1};
    case D::tavi:return {{T::tavi},1};
    case D::heart_of_ruin:return {{T::heart_of_ruin},1};
    }
    throw "invalid draft choice";
}
}

// Compile-time input gives an exactly sized array, with no runtime expansion or
// allocation. Callers never need to maintain a parallel physical-type table.
template<auto Choices>
constexpr auto expand() {
    constexpr auto count=[] {std::size_t n=0;for(auto c:Choices)n+=detail::actors(c).count;return n;}();
    std::array<cambc::champion_type,count> result{};std::size_t at=0;
    for(auto c:Choices) {
        auto actors=detail::actors(c);
        for(std::size_t i=0;i<actors.count;++i)result[at++]=actors.types[i];
    }
    return result;
}
inline constexpr auto original_routes=expand<choice_prefix<5>()>();
inline constexpr auto pair_routes=expand<choice_prefix<5,pair_preferences>()>();
struct Plan {
    std::span<const cambc::champion_draft> preferences;
    std::span<const cambc::champion_type> route_types;
};
// Legal map choice counts are 3, 4 and 5. Templates deliberately include the
// unused final choices; both consumers share these static, allocation-free views.
constexpr Plan plan(unsigned choices) {
    if(choices>=4)return {pair_preferences,pair_routes};
    return {original_preferences,original_routes};
}
}
