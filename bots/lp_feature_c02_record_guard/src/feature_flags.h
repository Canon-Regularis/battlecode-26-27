#define PARTY_FEATURE_MASK 278528ULL
#pragma once
#include <cstdint>
#ifndef PARTY_FEATURE_MASK
#define PARTY_FEATURE_MASK 0ULL
#endif
namespace lp {
struct Features {
static constexpr std::uint64_t mask=PARTY_FEATURE_MASK;
static constexpr bool shared=(mask&(1ULL<<0))!=0;
static constexpr bool leader=(mask&(1ULL<<1))!=0;
static constexpr bool follow=(mask&(1ULL<<2))!=0;
static constexpr bool inspect=(mask&(1ULL<<3))!=0;
static constexpr bool bank_rally=(mask&(1ULL<<4))!=0;
static constexpr bool attack_rally=(mask&(1ULL<<5))!=0;
static constexpr bool camp_commit=(mask&(1ULL<<6))!=0;
static constexpr bool bank_commit=(mask&(1ULL<<7))!=0;
static constexpr bool patrol=(mask&(1ULL<<8))!=0;
static constexpr bool bank_reacquire=(mask&(1ULL<<9))!=0;
static constexpr bool redispatch=(mask&(1ULL<<10))!=0;
static constexpr bool ally_retreat=(mask&(1ULL<<11))!=0;
static constexpr bool escape_hysteresis=(mask&(1ULL<<12))!=0;
static constexpr bool enemy_reports=(mask&(1ULL<<13))!=0;
static constexpr bool channel_guards=(mask&(1ULL<<14))!=0;
static constexpr bool legal_range=(mask&(1ULL<<15))!=0;
static constexpr bool ward_field=(mask&(1ULL<<16))!=0;
static constexpr bool aoe=(mask&(1ULL<<17))!=0;
static constexpr bool bank_record=(mask&(1ULL<<18))!=0;
static constexpr bool strict_follow=(mask&(1ULL<<19))!=0;
static constexpr bool preferred_priority=(mask&(1ULL<<20))!=0;
static constexpr bool own_safety=(mask&(1ULL<<21))!=0;
static constexpr bool safe_support=(mask&(1ULL<<22))!=0;
};
}
