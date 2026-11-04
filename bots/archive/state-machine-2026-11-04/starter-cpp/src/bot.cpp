#include <cambc.h>
#include "bot.h"
#include "protocol.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <span>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using namespace cambc;

const char* current_bot_stage = "startup";

namespace {

constexpr float leader_health_min = 0.50f;
constexpr float flee_health = 0.35f;
constexpr std::uint32_t bank_threshold = 20;
constexpr std::uint32_t rally_stale = 3;
constexpr std::uint32_t attack_lifetime = 12;

std::uint32_t state_color(BotState state) {
    switch (state) {
    case BotState::lead_team: return 0x2563EB;
    case BotState::follow_leader: return 0x06B6D4;
    case BotState::capture_point: return 0xF97316;
    case BotState::protect_point: return 0x9333EA;
    case BotState::prepare_gem_banking: return 0xCA8A04;
    case BotState::bank_gems: return 0xFACC15;
    case BotState::rally: return 0xDB2777;
    case BotState::run_away: return 0xDC2626;
    case BotState::recall: return 0x4F46E5;
    case BotState::healing: return 0x16A34A;
    case BotState::defend_spawn: return 0x991B1B;
    case BotState::death: return 0x6B7280;
    }
    return 0xFFFFFF;
}

void draw_state_marker(const champion& me, BotState state) {
    if (me.is_visible()) debug::draw_dot(me.position(), state_color(state));
}

const char* message_name(party::Message message) {
    switch (message) {
    case party::Message::none: return "none";
    case party::Message::moving: return "moving";
    case party::Message::work_camp: return "work_camp";
    case party::Message::protect_camp: return "protect_camp";
    case party::Message::bank_approach: return "bank_approach";
    case party::Message::bank_channel: return "bank_channel";
    case party::Message::hold: return "hold";
    case party::Message::objective_finished: return "objective_finished";
    }
    return "unknown";
}

const char* rally_name(party::Rally rally) {
    switch (rally) {
    case party::Rally::none: return "none";
    case party::Rally::bank: return "bank";
    case party::Rally::attack: return "attack";
    }
    return "unknown";
}

std::string slot_name(std::uint8_t slot) {
    return slot == party::none ? "none" : "s" + std::to_string(slot);
}

void print_shared_status(const champion& me, std::uint8_t slot, std::uint64_t word, std::uint32_t round) {
    std::ostringstream out;
    out << "[SHARED] round=" << round << " body=" << slot_name(slot)
        << '(' << to_string(me.champion_name()) << ") bytes=";
    for (int i = 0; i < 8; ++i) {
        if (i != 0) out << ' ';
        out << std::uppercase << std::hex << std::setw(2) << std::setfill('0')
            << static_cast<unsigned>((word >> (8 * i)) & 0xff);
    }
    out << std::dec << std::setfill(' ');

    if (!party::initialized(word)) {
        out << " initialized=no";
        std::cout << out.str() << std::endl;
        return;
    }

    const auto leader = static_cast<std::uint8_t>(party::get(word, party::leader_slot_bit, 3));
    const auto message = static_cast<party::Message>(party::get(word, party::leader_message_bit, 3));
    const auto anchor = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
    const auto rally = static_cast<party::Rally>(party::get(word, party::rally_type_bit, 2));
    const auto rally_target = static_cast<std::uint8_t>(party::get(word, party::rally_target_bit, 6));
    const auto enemy_chunk = static_cast<std::uint8_t>(party::get(word, party::enemy_chunk_bit, 6));
    const auto enemy_count = static_cast<std::uint8_t>(party::get(word, party::enemy_count_bit, 3));
    const auto runner = party::runner_slot(word);

    out << " initialized=yes leader=" << slot_name(leader)
        << " command=" << message_name(message) << " anchor=";
    if (anchor == party::invalid_id) out << "none";
    else if (message == party::Message::work_camp || message == party::Message::protect_camp) out << "camp:" << unsigned(anchor);
    else if (message == party::Message::bank_approach || message == party::Message::bank_channel) out << "altar:" << unsigned(anchor);
    else if (message == party::Message::moving) out << "chunk:" << unsigned(anchor);
    else out << unsigned(anchor);

    out << " rally=" << rally_name(rally) << ':';
    if (rally == party::Rally::none || rally_target == party::invalid_id) out << "none";
    else out << (rally == party::Rally::bank ? "altar:" : "chunk:") << unsigned(rally_target);
    out << " rally_owner=" << (rally == party::Rally::none ? "none" : slot_name(party::rally_owner(word)));
    if (rally != party::Rally::none) {
        const auto refreshed_age = ((round & 7) - party::rally_refreshed(word)) & 7;
        const auto created_age = ((round & 15) - party::rally_created(word)) & 15;
        out << " rally_age=" << refreshed_age << " rally_created_age=" << created_age;
    }

    out << " enemies=";
    if (enemy_count == 0 || enemy_chunk == party::invalid_id) out << "none";
    else out << unsigned(enemy_count) << "@chunk:" << unsigned(enemy_chunk);

    out << " runner=" << slot_name(runner);
    if (runner != party::none) {
        out << " ack=" << (party::runner_ack(word) ? "yes" : "no")
            << " skipped=" << (party::runner_skipped(word) ? "yes" : "no")
            << " issue_parity=" << unsigned(party::runner_issue_parity(word));
    } else {
        out << " ack=no skipped=" << (party::runner_skipped(word) ? "yes" : "no");
    }

    out << " offers={";
    for (std::uint8_t i = 0; i < 6; ++i) {
        if (i != 0) out << ',';
        const auto age = ((round & 3) - party::get(word, party::stamp_bit + 2 * i, 2)) & 3;
        out << 's' << unsigned(i) << ':' << (party::get(word, party::offer_bit + i, 1) ? "eligible" : "no")
            << "/age=" << age << (party::fresh(word, i, round) ? " fresh" : " stale");
    }
    out << '}';
    std::cout << out.str() << std::endl;
}

int cheb(vec2 a, vec2 b) { return static_cast<int>(a.chebyshev_distance(b)); }

std::uint32_t handle_id(const champion& c) {
    return static_cast<std::uint32_t>(static_cast<handle_champion_t>(c));
}

std::vector<champion> roster() {
    auto result = cambc::champions(team::ally);
    std::sort(result.begin(), result.end(), [](const champion& a, const champion& b) { return handle_id(a) < handle_id(b); });
    return result;
}

std::vector<map::camp_group> camps_by_id() {
    auto result = map::camp_groups();
    auto anchor = [](const map::camp_group& g) {
        vec2 p{ 1000, 1000 };
        for (const auto& c : g.camps()) {
            const auto q = c.spawn_position();
            if (q.y < p.y || (q.y == p.y && q.x < p.x)) p = q;
        }
        return p;
    };
    std::sort(result.begin(), result.end(), [&](const auto& a, const auto& b) {
        const auto x = anchor(a), y = anchor(b);
        return x.y != y.y ? x.y < y.y : x.x < y.x;
    });
    return result;
}

std::vector<vec2> altars_by_id() {
    auto result = map::altars().positions();
    std::sort(result.begin(), result.end(), [](vec2 a, vec2 b) { return a.y != b.y ? a.y < b.y : a.x < b.x; });
    return result;
}

int chunk_id(vec2 p) {
    const int cols = (map::width() + 14) / 15;
    const int rows = (map::height() + 14) / 15;
    const int col = std::min(cols - 1, p.x * cols / map::width());
    const int row = std::min(rows - 1, p.y * rows / map::height());
    return row * cols + col;
}

vec2 chunk_center(std::uint8_t id) {
    const int cols = (map::width() + 14) / 15;
    const int rows = (map::height() + 14) / 15;
    if (id >= cols * rows) return { map::width() / 2, map::height() / 2 };
    const int col = id % cols, row = id / cols;
    const int x0 = col * map::width() / cols, x1 = (col + 1) * map::width() / cols;
    const int y0 = row * map::height() / rows, y1 = (row + 1) * map::height() / rows;
    return { (x0 + x1 - 1) / 2, (y0 + y1 - 1) / 2 };
}

std::uint8_t slot_of(const std::vector<champion>& team, const champion& who) {
    for (std::uint8_t i = 0; i < team.size() && i < 6; ++i) if (team[i] == who) return i;
    return party::none;
}

std::vector<std::uint8_t> leader_order(const std::vector<champion>& team) {
    const std::array pref{ champion_type::ren, champion_type::marcella, champion_type::vendetta };
    std::vector<std::uint8_t> result;
    for (auto t : pref)
        for (std::uint8_t i = 0; i < team.size() && i < 6; ++i)
            if (team[i].is_visible() && team[i].champion_name() == t) result.push_back(i);
    std::vector<std::pair<float, std::uint8_t>> rest;
    for (std::uint8_t i = 0; i < team.size() && i < 6; ++i)
        if (std::find(result.begin(), result.end(), i) == result.end()) {
            float max_health = 0;
            if (team[i].is_visible()) max_health = team[i].base_stats().base_health;
            rest.emplace_back(max_health, i);
        }
    std::stable_sort(rest.begin(), rest.end(), [](auto a, auto b) { return a.first != b.first ? a.first > b.first : a.second < b.second; });
    for (auto [_, i] : rest) result.push_back(i);
    return result;
}

std::vector<std::uint8_t> runner_order(const std::vector<champion>& team) {
    const std::array pref{ champion_type::vendetta, champion_type::vesper_vale, champion_type::marcella };
    std::vector<std::uint8_t> result;
    for (auto type : pref)
        for (std::uint8_t i = 0; i < team.size() && i < 6; ++i)
            if (team[i].is_visible() && team[i].champion_name() == type) result.push_back(i);
    for (std::uint8_t i = 0; i < team.size() && i < 6; ++i)
        if (std::find(result.begin(), result.end(), i) == result.end()) result.push_back(i);
    return result;
}

bool on_spawn(vec2 p) { return map::spawn_region(team::ally).is_set(p); }

bitboard blocked_now(vec2 self) {
    auto blocked = map::walls() | map::holes() | map::altars() | map::spawn_region(team::enemy)
        | vision::champion_tiles() | vision::camp_tiles() | vision::teleport_tiles();
    blocked.set(self, false);
    return blocked;
}

bool move_to_goals(champion& me, bitboard goals) {
    if (!me.can_move()) return false;
    const auto origin = me.position();
    if (goals.is_set(origin)) return false;
    auto blocked = blocked_now(origin);
    // A camp spawn tile is a valid capture goal even though camp_tiles marks it occupied.
    goals &= (~blocked | vision::camp_tiles());
    if (goals.is_empty()) return false;
    if (goals.count() == 1 && !blocked.is_set(goals.positions()[0]))
        return me.move_towards(goals.positions()[0]);
    auto walls = blocked & ~goals;
    bitboard self_tile;
    self_tile.set(origin);
    bitboard visited;
    distance_field field;
    field.compute_to(walls, goals, self_tile, visited);
    auto step = origin;
    auto best = field.get(origin);
    for (const auto p : blocked.reachable_tiles(origin, static_cast<std::uint16_t>(me.base_stats().base_move_speed)).positions()) {
        const auto d = field.get(p);
        if (d < best) { best = d; step = p; }
    }
    return step != origin && me.move_absolute(step);
}

bool attack_if_ready(champion& me, const unit& target) {
    try {
        if (!me.can_attack() || !target.is_visible()) return false;
        if (!me.attack_tiles().is_set(target.position())) return false;
        me.attack(target);
        return true;
    } catch (const cambc::error& e) {
        if (e.code() == error_code::api_not_found || e.code() == error_code::api_not_in_vision) return false;
        throw;
    }
}

bool attack_lock_if_ready(champion& me, const altar_lock& target) {
    try {
        if (!me.can_attack() || !me.attack_tiles().is_set(target.position())) return false;
        me.attack(target);
        return true;
    } catch (const cambc::error& e) {
        if (e.code() == error_code::api_not_found || e.code() == error_code::api_not_in_vision) return false;
        throw;
    }
}

bool cast_if_ready(champion& me, const unit& target, bool camp_target) {
    try {
        if (!me.can_cast() || !target.is_visible()) return false;
        const auto abilities = me.abilities();
        for (const auto& ability : abilities) {
            if (!ability.is_ready() || (camp_target ? !ability.can_target_camps() : !ability.can_target_enemies())) continue;
            if (!ability.valid_tiles().is_set(target.position())) continue;
            if (const auto* c = dynamic_cast<const camp*>(&target)) ability.use(*c);
            else if (const auto* enemy = dynamic_cast<const champion*>(&target)) ability.use(*enemy);
            else continue;
            return true;
        }
    } catch (const cambc::error& e) {
        if (e.code() == error_code::api_not_found || e.code() == error_code::api_not_in_vision) return false;
        throw;
    }
    return false;
}

bool camp_threatens_position(const camp& target, vec2 position) {
    try {
        return target.is_visible() && target.attack_tiles().is_set(position);
    } catch (const cambc::error& e) {
        if (e.code() == error_code::api_not_found || e.code() == error_code::api_not_in_vision) return false;
        throw;
    }
}

bool local_enemy_threat() {
    const auto pos = cambc::self().position();
    current_bot_stage = "danger.enemy_champions";
    for (const auto& enemy : vision::champions(team::enemy))
        if (enemy.is_alive() && enemy.attack_tiles().is_set(pos)) return true;
    current_bot_stage = "danger.camps";
    for (const auto& group : vision::camp_groups()) {
        if (!std::holds_alternative<map::camp_group_alive>(group.state())) continue;
        for (const auto& camp : group.camps())
            if (camp_threatens_position(camp, pos)) return true;
    }
    return false;
}

std::optional<std::uint8_t> closest_camp_id(const std::vector<map::camp_group>& groups, vec2 origin, bool small_only = false, std::uint8_t exclude = party::invalid_id) {
    int best_distance = std::numeric_limits<int>::max();
    std::optional<std::uint8_t> best;
    for (std::uint8_t i = 0; i < groups.size() && i < 63; ++i) {
        if (i == exclude) continue;
        const auto& g = groups[i];
        if (small_only && !std::all_of(g.camps().begin(), g.camps().end(), [](const camp& c) { return c.is_gem_cluster() || c.is_gold_cluster(); })) continue;
        int d = std::numeric_limits<int>::max();
        for (const auto& c : g.camps()) d = std::min(d, cheb(origin, c.spawn_position()));
        if (d < best_distance) { best_distance = d; best = i; }
    }
    return best;
}

std::optional<std::uint8_t> closest_altar_id(const std::vector<vec2>& altars, vec2 origin) {
    int best = std::numeric_limits<int>::max();
    std::optional<std::uint8_t> index;
    for (std::uint8_t i = 0; i < altars.size() && i < 63; ++i) {
        const int d = cheb(origin, altars[i]);
        if (d < best) { best = d; index = i; }
    }
    return index;
}

bool group_is_visible(const map::camp_group& group) {
    const auto visible = vision::visible_tiles();
    return std::any_of(group.camps().begin(), group.camps().end(), [&](const camp& c) { return visible.is_set(c.spawn_position()); });
}

bool move_to_camp(champion& me, const map::camp_group& group, bool capture) {
    bitboard goals;
    goals.clear();
    if (capture) {
        goals = group.spawn_tiles();
    } else {
        const int radius = std::max(1, me.attack_range());
        for (const auto& member : group.camps()) goals.draw_chebyshev(member.spawn_position(), radius);
    }
    return move_to_goals(me, goals);
}

void attack_local_target(champion& me) {
    current_bot_stage = "run_state.local_attack.enemies";
    for (const auto& enemy : vision::champions(team::enemy))
        if (enemy.is_alive() && (cast_if_ready(me, enemy, false) || attack_if_ready(me, enemy))) return;
    current_bot_stage = "run_state.local_attack.camps";
    for (const auto& camp : vision::camps())
        if (camp.is_visible() && camp.health() > 0 && (cast_if_ready(me, camp, true) || attack_if_ready(me, camp))) return;
}

bool recall_safe() {
    current_bot_stage = "safety.enemies";
    if (!vision::champions(team::enemy).empty()) return false;
    const auto p = cambc::self().position();
    current_bot_stage = "safety.camps";
    for (const auto& group : vision::camp_groups()) {
        if (!std::holds_alternative<map::camp_group_alive>(group.state())) continue;
        for (const auto& c : group.camps()) if (camp_threatens_position(c, p)) return false;
    }
    return true;
}

void write_leader(std::uint64_t& word, std::uint8_t owner, party::Message msg, std::uint8_t anchor) {
    word = party::put(word, party::leader_slot_bit, 3, owner);
    word = party::put(word, party::leader_message_bit, 3, static_cast<std::uint8_t>(msg));
    word = party::put(word, party::leader_anchor_bit, 6, anchor);
}

void release_leader(std::uint64_t& word, std::uint8_t old, const std::vector<champion>& allies, const std::vector<std::uint8_t>& order) {
    auto owner = party::none;
    for (auto candidate : order)
        if (candidate != old && candidate < allies.size()
            && party::get(word, party::offer_bit + candidate, 1)
            && party::fresh(word, candidate, round_number()) && allies[candidate].is_alive()) { owner = candidate; break; }
    word = party::put(word, party::leader_slot_bit, 3, owner);
    if (owner == party::none) word = party::put(word, party::leader_message_bit, 3, 0);
    word = party::put(word, party::enemy_count_bit, 3, 0);
    word = party::put(word, party::enemy_chunk_bit, 6, party::invalid_id);
}

bool rally_live(std::uint64_t word, std::uint32_t round) {
    const auto type = party::get(word, party::rally_type_bit, 2);
    if (type < 1 || type > 2) return false;
    const auto last = party::rally_refreshed(word);
    if ((((round & 7) - last) & 7) > rally_stale) return false;
    if (type == static_cast<std::uint8_t>(party::Rally::attack)) {
        const auto created = party::rally_created(word);
        if ((((round & 15) - created) & 15) >= attack_lifetime) return false;
    }
    return true;
}

} // namespace

void Bot::do_shop(bool dead) {
    auto& me = cambc::self();
    if ((!dead && !on_spawn(me.position())) || !me.can_buy(item_type::power_shard_of_strength, 1)) return;
    const auto name = me.champion_name();
    item_type first = item_type::durability_shard_of_health;
    item_type second = item_type::power_shard_of_strength;
    if (name == champion_type::ren || name == champion_type::prism || name == champion_type::willow)
        second = item_type::monster_shard_of_focus;
    if (name == champion_type::vesper_vale) first = item_type::treasure_shard_of_strength;
    if (name == champion_type::vendetta || name == champion_type::ryth) second = item_type::monster_shard_of_strength;
    const auto first_phase_count = me.item_count()[first];
    const auto second_phase_count = me.item_count()[second];
    auto chosen = shop_phase_ == 0 ? first : second;
    if (shop_phase_ == 0 && first_phase_count >= 5) { shop_phase_ = 1; chosen = second; }
    else if (shop_phase_ == 1 && second_phase_count >= 5) { shop_phase_ = 2; chosen = item_type::power_shard_of_health; }
    if (me.can_buy(chosen, 1)) {
        const auto count = std::min<std::uint32_t>(8, me.gold_count() / chosen.cost());
        if (count) me.buy(chosen, count);
    }
    if (me.can_buy(consumable_type::altar_lock)) me.buy(consumable_type::altar_lock);
}

void Bot::publish_protocol(std::uint64_t& word, bool eligible) {
    party::publish_offer(word, slot_, eligible, round_number());
}

void Bot::try_ward(std::uint64_t word) {
    auto& me = cambc::self();
    if (!me.is_alive() || me.is_recalling() || me.is_submitting_gems() || me.is_teleporting()
        || state_ == BotState::run_away || state_ == BotState::recall || state_ == BotState::healing
        || state_ == BotState::death || me.ward_cooldown() > 0 || me.restrictions().contains(buff_restrictions::ward)
        || fuel_remaining() < 35000) return;
    vec2 anchor = me.position();
    std::uint8_t anchor_id = party::get(word, party::leader_anchor_bit, 6);
    if (state_ == BotState::prepare_gem_banking && altar_target_ < altars_by_id().size()) anchor = altars_by_id()[altar_target_];
    else if (camp_target_ < camps_by_id().size()) {
        const auto known_camps = camps_by_id();
        const auto& group = known_camps[camp_target_];
        if (!group.camps().empty()) anchor = group.camps().front().spawn_position();
    } else if (state_ == BotState::defend_spawn) {
        const auto enemies = vision::champions(team::enemy);
        if (!enemies.empty()) anchor = enemies.front().position();
    } else {
        const auto leader = static_cast<std::uint8_t>(party::get(word, party::leader_slot_bit, 3));
        const auto allies = roster();
        if (leader < allies.size() && allies[leader].is_alive() && allies[leader].is_visible()) anchor = allies[leader].position();
    }
    const auto old_positions = me.ward_positions();
    if (!old_positions.empty()) {
        const auto old = old_positions.front();
        if (has_ward_position_ && anchor_id == last_ward_anchor_ && cheb(old, last_ward_position_) < 6) return;
        last_ward_position_ = old;
    }
    const auto visible = vision::visible_tiles();
    auto blocked = map::walls() | map::holes() | map::altars() | map::spawn_region(team::enemy)
        | vision::champion_tiles() | vision::camp_tiles() | vision::teleport_tiles() | vision::ward_tiles(team::ally);
    auto candidates = me.ward_placement_tiles() & visible & ~blocked;
    auto region = bitboard{};
    region.clear();
    region.draw_chebyshev(anchor, 6);
    bitboard old_cover;
    old_cover.clear();
    if (!old_positions.empty()) old_cover = ward::visible_tiles_from(old_positions.front()) & region;
    const auto tiles = candidates.positions();
    int best_gain = 7;
    int best_distance = std::numeric_limits<int>::max();
    vec2 best{};
    int examined = 0;
    for (const auto tile : tiles) {
        if (examined++ >= 4) break;
        const auto coverage = ward::visible_tiles_from(tile) & region;
        const int gain = static_cast<int>(coverage.count()) - static_cast<int>(old_cover.count());
        const int d = cheb(tile, anchor);
        if (gain > best_gain || (gain == best_gain && d < best_distance)
            || (gain == best_gain && d == best_distance && (tile.y < best.y || (tile.y == best.y && tile.x < best.x)))) {
            best_gain = gain; best_distance = d; best = tile;
        }
    }
    if (best_gain >= 8 && me.place_ward(best)) {
        last_ward_position_ = best;
        last_ward_anchor_ = anchor_id;
        has_ward_position_ = true;
    }
}

void Bot::play_turn() {
    auto& me = cambc::self();
    current_bot_stage = "roster";
    const auto allies = roster();
    slot_ = slot_of(allies, me);
    if (slot_ >= 6) return;
    party::initialize_if_slot_zero(slot_);
    auto word = party::read_word();
    print_shared_status(me, slot_, word, round_number());
    if (!party::initialized(word) || !me.is_alive()) return;

    const auto round = round_number();
    const auto camp_groups = camps_by_id();
    const auto altars = altars_by_id();
    const bool alive = me.is_alive();

    if (!alive) {
        state_ = BotState::death;
        auto leader = party::get(word, party::leader_slot_bit, 3);
        publish_protocol(word, false);
        if (leader == slot_) release_leader(word, slot_, allies, leader_order(allies));
        if (party::rally_owner(word) == slot_) {
            word = party::put(word, party::rally_type_bit, 2, 0);
            word = party::put(word, party::rally_target_bit, 6, party::invalid_id);
        }
        party::write_word(word);
        do_shop(true);
        draw_state_marker(me, state_);
        return;
    }

    const auto pos = me.position();
    const bool spawn = on_spawn(pos);
    current_bot_stage = "local_threat";
    const bool threat = local_enemy_threat();
    const bool low_health = me.health() <= me.max_health() * flee_health;
    const auto gems = me.gem_count();
    const bool bank_needed = gems >= bank_threshold || (gems > 0 && bank_was_started_);
    auto shared_leader = static_cast<std::uint8_t>(party::get(word, party::leader_slot_bit, 3));
    bool owns_leader = shared_leader == slot_;
    const auto message = static_cast<party::Message>(party::get(word, party::leader_message_bit, 3));
    const auto runner = party::runner_slot(word);
    const bool committed = state_ == BotState::capture_point || state_ == BotState::protect_point || state_ == BotState::bank_gems || state_ == BotState::rally;
    bool eligible = !threat && !committed && !low_health && !bank_needed && me.health() > me.max_health() * leader_health_min;
    publish_protocol(word, eligible);

    if (!rally_live(word, round) && party::get(word, party::rally_type_bit, 2) != 0) {
        word = party::put(word, party::rally_type_bit, 2, 0);
        word = party::put(word, party::rally_target_bit, 6, party::invalid_id);
    }
    shared_leader = static_cast<std::uint8_t>(party::get(word, party::leader_slot_bit, 3));
    if (shared_leader < allies.size()) {
        bool leader_alive = false;
        try { leader_alive = allies[shared_leader].is_alive(); } catch (...) {}
        if (!leader_alive || !party::fresh(word, shared_leader, round, 2)) {
            word = party::put(word, party::leader_slot_bit, 3, party::none);
            word = party::put(word, party::leader_message_bit, 3, 0);
            word = party::put(word, party::enemy_count_bit, 3, 0);
            word = party::put(word, party::enemy_chunk_bit, 6, party::invalid_id);
            shared_leader = party::none;
        }
    }
    if (shared_leader == party::none) {
        for (auto candidate : leader_order(allies)) {
            if (candidate >= allies.size() || !party::get(word, party::offer_bit + candidate, 1)
                || !party::fresh(word, candidate, round) || !allies[candidate].is_alive()) continue;
            if (candidate != slot_) break;
            if (!eligible) break;
            shared_leader = candidate;
            word = party::put(word, party::enemy_count_bit, 3, 0);
            word = party::put(word, party::enemy_chunk_bit, 6, party::invalid_id);
            write_leader(word, slot_, party::Message::moving, chunk_id(pos));
            break;
        }
    }
    owns_leader = shared_leader == slot_;

    current_bot_stage = "shop";
    do_shop();
    if (me.is_recalling()) {
        state_ = BotState::recall;
        if (threat) { me.cancel_recall(); state_ = BotState::run_away; }
        else { party::write_word(word); draw_state_marker(me, state_); return; }
    }
    if (me.is_submitting_gems()) {
        state_ = BotState::bank_gems;
        bank_was_started_ = true;
        if (gems == 0) bank_was_started_ = false;
        party::write_word(word);
        draw_state_marker(me, state_);
        return;
    }
    if (me.is_teleporting()) { party::write_word(word); draw_state_marker(me, state_); return; }

    // A threatened spawn is defended in place before any party task.
    if (spawn && threat) state_ = BotState::defend_spawn;
    else if (spawn && me.health() < me.max_health()) state_ = BotState::healing;
    else if (threat && low_health) state_ = BotState::run_away;
    else if (low_health && !spawn) state_ = recall_safe() ? BotState::recall : BotState::run_away;
    else if (bank_needed) state_ = BotState::prepare_gem_banking;
    else if (owns_leader && message == party::Message::work_camp && runner == party::none && state_ != BotState::lead_team) {
        const auto task = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
        if (task < camp_groups.size()) { camp_target_ = task; state_ = BotState::capture_point; }
        else state_ = BotState::lead_team;
    }
    else if (owns_leader && eligible) state_ = BotState::lead_team;
    else if (state_ == BotState::capture_point && camp_target_ < camp_groups.size()) state_ = BotState::capture_point;
    else if (state_ == BotState::protect_point && camp_target_ < camp_groups.size()) state_ = BotState::protect_point;
    else if (rally_live(word, round) && !owns_leader) state_ = BotState::rally;
    else if (shared_leader < allies.size()) state_ = BotState::follow_leader;
    else state_ = BotState::follow_leader;

    if (state_ == BotState::follow_leader || state_ == BotState::rally || state_ == BotState::lead_team) {
        for (std::uint8_t i = 0; i < allies.size() && i < 6; ++i) {
            const auto& carrier = allies[i];
            if (!carrier.is_alive() || !carrier.is_visible() || !carrier.is_submitting_gems()) continue;
            if (cheb(pos, carrier.position()) <= 2) {
                bank_carrier_slot_ = i;
                if (auto altar = closest_altar_id(altars, carrier.position())) altar_target_ = *altar;
                protect_bank_ = true;
                state_ = BotState::protect_point;
                break;
            }
        }
    }

    if ((state_ == BotState::lead_team) && !eligible) {
        release_leader(word, slot_, allies, leader_order(allies));
        state_ = BotState::follow_leader;
    }
    if (party::get(word, party::leader_slot_bit, 3) == slot_ && state_ != BotState::lead_team) {
        publish_protocol(word, false);
        release_leader(word, slot_, allies, leader_order(allies));
    }
    current_bot_stage = "run_state";
    run_state(word);
    current_bot_stage = "state_marker";
    draw_state_marker(me, state_);

    current_bot_stage = "ward";
    try_ward(word);

    // Publish the leader's latest chunk unless its anchor is currently an exact static camp ID.
    current_bot_stage = "enemy_report";
    if (state_ == BotState::lead_team && party::get(word, party::leader_slot_bit, 3) == slot_
        && party::get(word, party::runner_bit, 3) == party::none)
        write_leader(word, slot_, party::Message::moving, chunk_id(me.position()));

    // A small, optional enemy concentration report: visible champions only, deterministic chunk tie-break.
    if (state_ == BotState::lead_team && party::get(word, party::leader_slot_bit, 3) == slot_
        && fuel_remaining() > 25000 && round != last_enemy_report_round_) {
        std::array<std::uint8_t, 49> counts{};
        for (const auto& enemy : vision::champions(team::enemy)) if (enemy.is_alive()) {
            const auto id = chunk_id(enemy.position());
            if (id >= 0 && id < 49 && counts[id] < 7) ++counts[id];
        }
        std::uint8_t best = party::invalid_id, count = 0;
        for (std::uint8_t i = 0; i < counts.size(); ++i)
            if (counts[i] > count) { best = i; count = counts[i]; }
        if (count > 0) {
            word = party::put(word, party::enemy_chunk_bit, 6, best);
            word = party::put(word, party::enemy_count_bit, 3, count);
        }
        if (count > 0 && best != party::invalid_id) last_enemy_report_round_ = round;
        else if (party::get(word, party::enemy_count_bit, 3) > 0 && round - last_enemy_report_round_ > 3) {
            word = party::put(word, party::enemy_count_bit, 3, 0);
            word = party::put(word, party::enemy_chunk_bit, 6, party::invalid_id);
        }
    }
    party::write_word(word);
}

void Bot::run_state(std::uint64_t& word) {
    current_bot_stage = "run_state.snapshot";
    auto& me = cambc::self();
    const auto pos = me.position();
    const auto camp_groups = camps_by_id();
    const auto altars = altars_by_id();
    const auto allies = roster();
    const auto leader_slot = static_cast<std::uint8_t>(party::get(word, party::leader_slot_bit, 3));
    const auto message = static_cast<party::Message>(party::get(word, party::leader_message_bit, 3));


    if (state_ == BotState::death) return;
    if (state_ == BotState::healing) { if (on_spawn(pos)) return; }
    if (state_ == BotState::defend_spawn) {
        current_bot_stage = "run_state.defend_spawn";
        attack_local_target(me);
        for (vec2 p : map::spawn_region(team::ally).positions()) if (pos != p && on_spawn(p) && me.can_move()) {
            me.move_towards(p); break;
        }
        return;
    }
    if (state_ == BotState::recall) {
        current_bot_stage = "run_state.recall";
        if (recall_safe()) me.recall(); else state_ = BotState::run_away;
        return;
    }
    if (state_ == BotState::run_away) {
        current_bot_stage = "run_state.run_away";
        attack_local_target(me);
        vec2 anchor = map::spawn_region(team::ally).positions().empty() ? pos : map::spawn_region(team::ally).positions()[0];
        int best = std::numeric_limits<int>::max();
        for (const auto& ally : vision::champions(team::ally)) {
            if (!ally.is_visible() || !ally.is_alive() || ally == me || local_enemy_threat()) continue;
            const auto d = cheb(pos, ally.position());
            if (d < best) { best = d; anchor = ally.position(); }
        }
        if (on_spawn(pos) && !local_enemy_threat()) state_ = BotState::healing;
        else if (me.can_move()) me.move_towards(anchor);
        return;
    }
    if (state_ == BotState::prepare_gem_banking) {
        current_bot_stage = "run_state.prepare_banking";
        if (me.gem_count() == 0) { bank_was_started_ = false; state_ = BotState::follow_leader; return; }
        if (local_enemy_threat() && (me.health() <= me.max_health() * 0.35f || on_spawn(pos))) { state_ = BotState::run_away; return; }
        const auto altar_id = closest_altar_id(altars, pos);
        if (altar_id && *altar_id < altars.size()) {
            altar_target_ = *altar_id;
            const auto altar = altars[*altar_id];
            if (cheb(pos, altar) <= 1 && !vision::has_altar_lock(altar)) {
                me.submit_gems(altar);
                if (me.is_submitting_gems()) { state_ = BotState::bank_gems; bank_was_started_ = true; return; }
            }
            const auto old_rally = static_cast<party::Rally>(party::get(word, party::rally_type_bit, 2));
            const auto old_owner = party::rally_owner(word);
            const auto old_target = static_cast<std::uint8_t>(party::get(word, party::rally_target_bit, 6));
            if (me.gem_count() >= bank_threshold && (old_rally == party::Rally::none || old_rally == party::Rally::attack
                || (old_rally == party::Rally::bank && old_owner == slot_ && old_target == *altar_id))) {
                word = party::put(word, party::rally_target_bit, 6, *altar_id);
                word = party::put(word, party::rally_type_bit, 2, static_cast<std::uint8_t>(party::Rally::bank));
                word = party::put(word, party::rally_owner_bit, 3, slot_);
                word = party::put(word, party::rally_owner_bit + 3, 3, round_number() & 7);
                if (old_rally != party::Rally::bank || old_owner != slot_ || old_target != *altar_id)
                    word = party::put(word, party::rally_owner_bit + 6, 4, round_number() & 15);
            }
            if (!vision::has_altar_lock(altar)) {
                bitboard goals;
                goals.clear();
                goals.draw_chebyshev(altar, 1);
                move_to_goals(me, goals);
            } else {
                for (const auto& lock : vision::altar_locks(team::enemy))
                    if (attack_lock_if_ready(me, lock)) break;
            }
            return;
        }
    }
    if (state_ == BotState::bank_gems) return;

    // A runner assignment is exact, acknowledged, and not broadcast as a party work order.
    const auto runner = party::runner_slot(word);
    if (runner == slot_ && camp_target_ == party::invalid_id) {
        camp_target_ = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
        if (camp_target_ < camp_groups.size()) {
            auto v = word;
            party::set_runner(v, runner, true, party::runner_skipped(word), round_number());
            party::write_word(v);
            word = v;
            state_ = BotState::capture_point;
        }
    }
    if (state_ == BotState::capture_point && camp_target_ < camp_groups.size()) {
        current_bot_stage = "run_state.capture_point";
        const auto& group = camp_groups[camp_target_];
        if (group_is_visible(group)) {
            const auto status = group.state();
            if (std::holds_alternative<map::camp_group_respawning>(status)) {
                state_ = BotState::follow_leader;
                if (runner == slot_) { auto v = word; party::clear_runner(v, true); party::write_word(v); word = v; }
                else if (runner == party::none) { auto v = word; party::clear_runner(v, false); party::write_word(v); word = v; }
                camp_target_ = party::invalid_id;
                return;
            }
            if (std::holds_alternative<map::camp_group_alive>(status)) {
                for (const auto& camp : group.camps()) if (camp.is_visible() && attack_if_ready(me, camp)) return;
                move_to_camp(me, group, false);
                for (const auto& camp : group.camps()) if (camp.is_visible() && attack_if_ready(me, camp)) return;
                return;
            }
            bool occupied = false;
            for (const auto& ally : vision::champions(team::ally))
                if (ally != me && ally.is_alive() && group.spawn_tiles().is_set(ally.position())) occupied = true;
            if (occupied) {
                state_ = BotState::protect_point;
                return;
            }
            move_to_camp(me, group, true);
            return;
        }
        move_to_camp(me, group, false);
        return;
    }
    if (state_ == BotState::protect_point && camp_target_ < camp_groups.size()) {
        current_bot_stage = "run_state.protect_camp";
        const auto& group = camp_groups[camp_target_];
        attack_local_target(me);
        if (group_is_visible(group) && std::holds_alternative<map::camp_group_respawning>(group.state())) {
            state_ = BotState::follow_leader;
            camp_target_ = party::invalid_id;
        }
        return;
    }

    if (state_ == BotState::protect_point && protect_bank_) {
        current_bot_stage = "run_state.protect_bank";
        if (bank_carrier_slot_ >= allies.size() || !allies[bank_carrier_slot_].is_alive()) {
            protect_bank_ = false;
            bank_carrier_slot_ = party::none;
            state_ = BotState::follow_leader;
            return;
        }
        const auto& carrier = allies[bank_carrier_slot_];
        if (carrier.is_visible()) {
            if (!carrier.is_submitting_gems() && carrier.gem_count() == 0) {
                protect_bank_ = false;
                bank_carrier_slot_ = party::none;
                state_ = BotState::follow_leader;
                return;
            }
            const auto carrier_pos = carrier.position();
            attack_local_target(me);
            if (cheb(pos, carrier_pos) > 2 && me.can_move()) me.move_towards(carrier_pos);
        } else {
            attack_local_target(me);
            if (altar_target_ < altars.size()) {
                bitboard goals; goals.clear(); goals.draw_chebyshev(altars[altar_target_], 2); move_to_goals(me, goals);
            }
        }
        return;
    }

    if (state_ == BotState::rally) {
        current_bot_stage = "run_state.rally";
        if (!rally_live(word, round_number())) { state_ = BotState::follow_leader; return; }
        if (static_cast<party::Rally>(party::get(word, party::rally_type_bit, 2)) == party::Rally::attack) {
            const auto enemies = vision::champions(team::enemy);
            if (!enemies.empty()) attack_local_target(me);
            else me.move_towards(chunk_center(static_cast<std::uint8_t>(party::get(word, party::rally_target_bit, 6))));
        }
        const auto target = static_cast<std::uint8_t>(party::get(word, party::rally_target_bit, 6));
        if (static_cast<party::Rally>(party::get(word, party::rally_type_bit, 2)) == party::Rally::bank && target < altars.size()) {
            for (std::uint8_t i = 0; i < allies.size() && i < 6; ++i)
                if (i != slot_ && allies[i].is_alive() && allies[i].is_visible() && allies[i].is_submitting_gems()
                    && cheb(pos, allies[i].position()) <= 2) {
                    bank_carrier_slot_ = i;
                    if (auto altar = closest_altar_id(altars, allies[i].position())) altar_target_ = *altar;
                    protect_bank_ = true; state_ = BotState::protect_point; return;
                }
            bitboard goals; goals.clear(); goals.draw_chebyshev(altars[target], 2); move_to_goals(me, goals);
        }
        return;
    }

    if (state_ == BotState::lead_team) {
        current_bot_stage = "run_state.lead_team";
        const auto visible_enemies = vision::champions(team::enemy);
        const auto rally_type = static_cast<party::Rally>(party::get(word, party::rally_type_bit, 2));
        const auto rally_owner_id = party::rally_owner(word);
        if (!visible_enemies.empty() && (rally_type == party::Rally::none
            || (rally_type == party::Rally::attack && rally_owner_id == slot_))) {
            const auto target_chunk = static_cast<std::uint8_t>(chunk_id(visible_enemies.front().position()));
            const auto old_target = static_cast<std::uint8_t>(party::get(word, party::rally_target_bit, 6));
            if (rally_type != party::Rally::attack || old_target != target_chunk) {
                word = party::put(word, party::rally_target_bit, 6, target_chunk);
                word = party::put(word, party::rally_type_bit, 2, static_cast<std::uint8_t>(party::Rally::attack));
                word = party::put(word, party::rally_owner_bit, 3, slot_);
                word = party::put(word, party::rally_owner_bit + 6, 4, round_number() & 15);
                attack_lost_contact_turns_ = 0;
            }
            word = party::put(word, party::rally_owner_bit + 3, 3, round_number() & 7);
            attack_lost_contact_turns_ = 0;
        } else if (rally_type == party::Rally::attack && rally_owner_id == slot_) {
            if (++attack_lost_contact_turns_ >= 2) {
                // Clear only the attack record still owned by this body and matching its target.
                if (party::rally_owner(word) == slot_ && party::get(word, party::rally_type_bit, 2) == 2) {
                    word = party::put(word, party::rally_type_bit, 2, 0);
                    word = party::put(word, party::rally_target_bit, 6, party::invalid_id);
                }
                attack_lost_contact_turns_ = 0;
            }
        }
        attack_local_target(me);
        if (runner < 6 && runner != slot_) {
            const auto detached_camp = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
            if (!party::runner_ack(word) && party::runner_issue_parity(word) != (round_number() & 1)) {
                // Missing next-turn acknowledgement cancels the detached job; the party takes it together.
                party::clear_runner(word, false);
                if (detached_camp < camp_groups.size()) {
                    camp_target_ = detached_camp;
                    write_leader(word, slot_, party::Message::work_camp, detached_camp);
                    release_leader(word, slot_, allies, leader_order(allies));
                    state_ = BotState::capture_point;
                    return;
                }
            }
            // The anchor remains the exact detached camp ID while the leader travels by observation.
            const auto next = closest_camp_id(camp_groups, pos, false, detached_camp);
            if (next) move_to_camp(me, camp_groups[*next], false);
            return;
        }
        if (party::runner_skipped(word) && message == party::Message::work_camp) {
            const auto skipped = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
            const auto next = closest_camp_id(camp_groups, pos, false, skipped);
            party::clear_runner(word, false);
            if (next) {
                camp_target_ = *next;
                write_leader(word, slot_, party::Message::work_camp, *next);
                release_leader(word, slot_, allies, leader_order(allies));
                state_ = BotState::capture_point;
                return;
            }
        }
        if (camp_target_ >= camp_groups.size()) {
            const auto target = closest_camp_id(camp_groups, pos);
            if (target) {
                const auto& group = camp_groups[*target];
                const bool small = std::all_of(group.camps().begin(), group.camps().end(), [](const camp& c) { return c.is_gem_cluster() || c.is_gold_cluster(); });
                const auto moving_party = vision::champions(team::ally).size();
                int group_distance = std::numeric_limits<int>::max();
                for (const auto& member : group.camps()) group_distance = std::min(group_distance, cheb(pos, member.spawn_position()));
                if (small && group_distance <= 2 && party::runner_slot(word) == party::none && !party::runner_skipped(word) && moving_party > 2) {
                    for (auto candidate : runner_order(allies)) {
                        if (candidate >= allies.size() || candidate == slot_) continue;
                        const auto& body = allies[candidate];
                        if (body.is_alive() && body.is_visible() && body.health() >= body.max_health() * 0.60f
                            && body.gem_count() < bank_threshold && cheb(body.position(), pos) <= 3) {
                            bool runner_threatened = false;
                            for (const auto& enemy : vision::champions(team::enemy))
                                if (enemy.is_alive() && cheb(enemy.position(), body.position()) <= 6) runner_threatened = true;
                            current_bot_stage = "run_state.runner_safety.camps";
                            for (const auto& camp : vision::camps())
                                if (camp_threatens_position(camp, body.position())) runner_threatened = true;
                            current_bot_stage = "run_state";
                            if (runner_threatened) continue;
                            party::set_runner(word, candidate, false, true, round_number());
                            write_leader(word, slot_, party::Message::work_camp, *target);
                            party::write_word(word);
                            return;
                        }
                    }
                }
                camp_target_ = *target;
                write_leader(word, slot_, party::Message::work_camp, *target);
                release_leader(word, slot_, allies, leader_order(allies));
                state_ = BotState::capture_point;
                return;
            }
        }
        if (camp_target_ < camp_groups.size()) {
            state_ = BotState::capture_point;
            return;
        }
        return;
    }

    if (state_ == BotState::follow_leader) {
        current_bot_stage = "run_state.follow_leader";
        if (message == party::Message::work_camp && runner < 6 && runner != slot_) {
            // During a detached job the anchor remains the exact camp ID; follow visible/cached leader position.
            if (leader_slot < allies.size() && allies[leader_slot].is_alive() && allies[leader_slot].is_visible()) {
                last_leader_position_ = allies[leader_slot].position(); has_leader_position_ = true;
            }
            if (has_leader_position_ && cheb(pos, last_leader_position_) > 2) me.move_towards(last_leader_position_);
            return;
        }
        if (message == party::Message::work_camp && party::get(word, party::leader_slot_bit, 3) != slot_) {
            const auto target = static_cast<std::uint8_t>(party::get(word, party::leader_anchor_bit, 6));
            if (target < camp_groups.size()) { camp_target_ = target; state_ = BotState::capture_point; return; }
        }
        if (leader_slot < allies.size() && allies[leader_slot].is_alive() && allies[leader_slot].is_visible()) {
            last_leader_position_ = allies[leader_slot].position(); has_leader_position_ = true;
            if (cheb(pos, last_leader_position_) > 2) me.move_towards(last_leader_position_);
        } else if (has_leader_position_ && cheb(pos, last_leader_position_) > 2) me.move_towards(last_leader_position_);
        else if (leader_slot == party::none) state_ = BotState::follow_leader;
        if (rally_live(word, round_number()) && party::rally_owner(word) != slot_) state_ = BotState::rally;
        return;
    }
}

