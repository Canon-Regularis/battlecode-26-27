#include "roster.h"
using D=cambc::champion_draft;using T=cambc::champion_type;
using namespace lp::roster;
constexpr std::array order{D::heart_of_ruin,D::marcella,D::vesper_vale,D::ren,D::vendetta,D::varg,D::ryth,D::stellar,D::prism,D::willow,D::tavi,D::cassi_and_issac};
static_assert(original_preferences==order);
constexpr std::array active_order{D::heart_of_ruin,D::marcella,D::vesper_vale,D::cassi_and_issac,D::vendetta,D::varg,D::ryth,D::stellar,D::prism,D::willow,D::tavi,D::ren};
static_assert(pair_preferences==active_order);
constexpr std::array physical{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren,T::vendetta,T::varg,T::ryth,T::stellar,T::prism,T::willow,T::tavi,T::cassi,T::issac};
static_assert(expand<order>()==physical); // Every named SDK mapping, including shifted values.
static_assert(original_routes==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren,T::vendetta});
static_assert(expand<choice_prefix<3>()>()==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale});
static_assert(expand<choice_prefix<4>()>()==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::ren});
static_assert(expand<choice_prefix<5>()>()==original_routes);
constexpr bool unique(auto values) {
    for(std::size_t i=0;i<values.size();++i)for(std::size_t j=0;j<i;++j)if(values[i]==values[j])return false;
    return true;
}
static_assert(unique(original_preferences)&&unique(pair_preferences)&&unique(expand<order>())&&unique(original_routes));
static_assert(pair_routes==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::cassi,T::issac,T::vendetta});
static_assert(expand<choice_prefix<3>()>().size()==3);
static_assert(expand<choice_prefix<4,pair_preferences>()>()==std::array{T::heart_of_ruin,T::marcella,T::vesper_vale,T::cassi,T::issac});
static_assert(expand<choice_prefix<5,pair_preferences>()>()==pair_routes);
static_assert(unique(pair_routes));
static_assert(plan(3).preferences[3]==D::ren&&plan(3).route_types.size()==5);
static_assert(plan(4).preferences[3]==D::cassi_and_issac&&plan(4).route_types.size()==6);
static_assert(plan(5).preferences.back()==D::ren&&plan(5).route_types.size()==6);
// Additional named expansion fixtures.
constexpr std::array pair2{D::cassi_and_issac,D::heart_of_ruin};
constexpr std::array pair4{D::cassi_and_issac,D::heart_of_ruin,D::ren,D::vendetta};
constexpr std::array pair5{D::cassi_and_issac,D::heart_of_ruin,D::ren,D::vendetta,D::marcella};
static_assert(expand<pair2>()==std::array{T::cassi,T::issac,T::heart_of_ruin});
static_assert(expand<pair4>()==std::array{T::cassi,T::issac,T::heart_of_ruin,T::ren,T::vendetta});
static_assert(expand<pair5>()==std::array{T::cassi,T::issac,T::heart_of_ruin,T::ren,T::vendetta,T::marcella});
static_assert(expand<std::array<D,0>{}>().empty());
