#pragma once
// Public integration seam specified in economic-bank-adapter-01. Implementation
// completed locally after that Pi job terminated without a returned commit.
#include "economic_scene.h"
#include "live_turn.h"
namespace lp {
enum class BankStop { action, complete, channel, approach, hidden, unsafe, allowance, unsupported, blocked };
struct BankChoice {BankStop stop=BankStop::blocked;action::Request request;};
bool bank_position_safe(const economic::Scene&);
BankChoice choose_bank(const economic::Scene&,const economic::Task&,const action::Ledger&);
action::Result perform_bank(const economic::Scene&,const BankChoice&,LiveTurn&);
}
