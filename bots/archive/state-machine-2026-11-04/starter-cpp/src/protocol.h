#pragma once

#include <cambc.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace party {

constexpr std::uint8_t none = 7;
constexpr std::uint8_t invalid_id = 63;
constexpr int leader_anchor_bit = 0;
constexpr int leader_slot_bit = 6;
constexpr int leader_message_bit = 9;
constexpr int rally_target_bit = 12;
constexpr int rally_type_bit = 18;
constexpr int enemy_chunk_bit = 20;
constexpr int enemy_count_bit = 26;
constexpr int stamp_bit = 29;
constexpr int offer_bit = 41;
constexpr int runner_bit = 47;
constexpr int rally_owner_bit = 53;
constexpr int initialized_bit = 63;

enum class Message : std::uint8_t { none, moving, work_camp, protect_camp, bank_approach, bank_channel, hold, objective_finished };
enum class Rally : std::uint8_t { none, bank, attack };

inline std::uint64_t read_word() {
    std::array<std::byte, 8> bytes{};
    cambc::shared_memory.read(0, bytes);
    std::uint64_t value = 0;
    for (int i = 0; i < 8; ++i) value |= std::uint64_t(std::to_integer<unsigned char>(bytes[i])) << (i * 8);
    return value;
}

inline void write_word(std::uint64_t value) {
    std::array<std::byte, 8> bytes{};
    for (int i = 0; i < 8; ++i) bytes[i] = std::byte((value >> (i * 8)) & 0xff);
    cambc::shared_memory.write(0, bytes);
}

inline std::uint64_t get(std::uint64_t word, int start, int width) {
    return (word >> start) & ((std::uint64_t{1} << width) - 1);
}

inline std::uint64_t put(std::uint64_t word, int start, int width, std::uint64_t value) {
    const auto mask = ((std::uint64_t{1} << width) - 1) << start;
    return (word & ~mask) | ((value << start) & mask);
}

inline bool initialized(std::uint64_t word) { return get(word, initialized_bit, 1) == 1; }

inline void initialize_if_slot_zero(std::uint8_t slot) {
    auto word = read_word();
    if (initialized(word) || slot != 0) return;
    word = 0;
    word = put(word, leader_slot_bit, 3, none);
    word = put(word, leader_anchor_bit, 6, invalid_id);
    word = put(word, leader_message_bit, 3, 0);
    word = put(word, rally_target_bit, 6, invalid_id);
    word = put(word, rally_type_bit, 2, 0);
    word = put(word, enemy_chunk_bit, 6, invalid_id);
    word = put(word, enemy_count_bit, 3, 0);
    for (int i = 0; i < 6; ++i) {
        word = put(word, stamp_bit + 2 * i, 2, cambc::round_number() & 3);
        word = put(word, offer_bit + i, 1, 0);
    }
    word = put(word, runner_bit, 3, none);
    word = put(word, rally_owner_bit, 10, 0);
    word = put(word, initialized_bit, 1, 1);
    write_word(word);
}

inline bool fresh(std::uint64_t word, std::uint8_t slot, std::uint32_t round, std::uint32_t max_age = 1) {
    const auto then = get(word, stamp_bit + 2 * slot, 2);
    return (((round & 3) - then) & 3) <= max_age;
}

inline void publish_offer(std::uint64_t& word, std::uint8_t slot, bool eligible, std::uint32_t round) {
    word = put(word, stamp_bit + 2 * slot, 2, round & 3);
    word = put(word, offer_bit + slot, 1, eligible ? 1 : 0);
}

inline std::uint8_t runner_slot(std::uint64_t word) { return get(word, runner_bit, 3); }
inline bool runner_ack(std::uint64_t word) { return get(word, runner_bit + 3, 1) != 0; }
inline bool runner_skipped(std::uint64_t word) { return get(word, runner_bit + 4, 1) != 0; }
inline std::uint8_t runner_issue_parity(std::uint64_t word) { return get(word, runner_bit + 5, 1); }

inline void set_runner(std::uint64_t& word, std::uint8_t slot, bool ack, bool skipped, std::uint32_t round) {
    word = put(word, runner_bit, 3, slot);
    word = put(word, runner_bit + 3, 1, ack);
    word = put(word, runner_bit + 4, 1, skipped);
    word = put(word, runner_bit + 5, 1, round & 1);
}

inline void clear_runner(std::uint64_t& word, bool keep_skip = false) {
    const bool skipped = keep_skip && runner_skipped(word);
    set_runner(word, none, false, skipped, cambc::round_number());
}

inline std::uint8_t rally_owner(std::uint64_t word) { return get(word, rally_owner_bit, 3); }
inline std::uint8_t rally_refreshed(std::uint64_t word) { return get(word, rally_owner_bit + 3, 3); }
inline std::uint8_t rally_created(std::uint64_t word) { return get(word, rally_owner_bit + 6, 4); }

} // namespace party
