#include <cambc.h>
#include "bot.h"

#include <algorithm>
#include <array>
#include <vector>

void play_draft() {
    const auto chosen = cambc::draft::current_draft(cambc::team::ally);
    // Prefer durable front-line bodies, then ranged damage/support. The same ordered
    // policy is applied on every draft turn, so both sides make deterministic picks.
    const std::array preference{
        cambc::champion_draft::ren,
        cambc::champion_draft::marcella,
        cambc::champion_draft::vendetta,
        cambc::champion_draft::vesper_vale,
        cambc::champion_draft::willow,
        cambc::champion_draft::tavi,
        cambc::champion_draft::varg,
        cambc::champion_draft::ryth,
        cambc::champion_draft::prism,
        cambc::champion_draft::stellar,
        cambc::champion_draft::cassi_and_issac,
    };
    for (auto pick : preference) {
        if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) {
            cambc::draft::pick(pick);
            return;
        }
    }
}
