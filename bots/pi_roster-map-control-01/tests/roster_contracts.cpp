#include "roster.h"
using D=cambc::champion_draft;using T=cambc::champion_type;
using namespace lp::roster;
constexpr std::array order{D::heart_of_ruin,D::marcella,D::vesper_vale,D::ren,D::vendetta,D::varg,D::ryth,D::stellar,D::prism,D::willow,D::tavi,D::cassi_and_issac};
static_assert(preferences==order);
constexpr std::array physical{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren,T::vendetta,T::varg,T::ryth,T::stellar,T::prism,T::willow,T::tavi,T::cassi,T::issac};
static_assert(expand<order>()==physical); // Every named SDK mapping, including shifted values.
static_assert(route_types==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren,T::vendetta});
static_assert(expand<choice_prefix<3>()>()==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale});
static_assert(expand<choice_prefix<4>()>()==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren});
static_assert(expand<choice_prefix<5>()>()==route_types);
constexpr bool unique(auto values) {
    for(std::size_t i=0;i<values.size();++i)for(std::size_t j=0;j<i;++j)if(values[i]==values[j])return false;
    return true;
}
static_assert(unique(preferences)&&unique(expand<order>())&&unique(route_types));
// Explicit fixture only: never selected by the production policy.
constexpr std::array pair2{D::cassi_and_issac,D::heart_of_ruin};
constexpr std::array pair4{D::cassi_and_issac,D::heart_of_ruin,D::ren,D::vendetta};
constexpr std::array pair5{D::cassi_and_issac,D::heart_of_ruin,D::ren,D::vendetta,D::marcella};
static_assert(expand<pair2>()==std::array{T::cassi,T::issac,T::heart_of_ruin});
static_assert(expand<pair4>()==std::array{T::cassi,T::issac,T::heart_of_ruin,T::ren,T::vendetta});
static_assert(expand<pair5>()==std::array{T::cassi,T::issac,T::heart_of_ruin,T::ren,T::vendetta,T::marcella});
static_assert(expand<std::array<D,0>{}>().empty());
