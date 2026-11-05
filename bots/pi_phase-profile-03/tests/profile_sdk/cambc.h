#pragma once
// Minimal public SDK surface for exercising the production output adapter.
#include <cstdint>
namespace cambc {
enum class handle_champion_t : std::uint32_t {};
struct champion {
    handle_champion_t handle;
    operator handle_champion_t() const noexcept { return handle; }
};
inline champion actor{};
inline unsigned self_calls=0, round=1;
inline std::uint64_t fuel=100000;
inline std::uint64_t fuel_step=0;
inline unsigned round_calls=0, fuel_calls=0;
inline champion& self() { ++self_calls;return actor; }
inline unsigned round_number() { ++round_calls;return round; }
inline std::uint64_t fuel_remaining() { ++fuel_calls;auto value=fuel;fuel-=fuel_step;return value; }
}
