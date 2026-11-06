#include "bot.h"
using namespace lp;
void Bot::play_turn() {
    const int round=round_number();
    if(executing_round>=0&&executing_round!=round)++stats.resumes;
    executing_round=round;
    if(!turn_ledger.begin({id(self()),memory.life,round,observation_version()},fuel_remaining()))return;
    struct Close {
        action::Ledger& ledger;int& executing;
        ~Close()noexcept{ledger.finish();executing=-1;}
    } close{turn_ledger,executing_round};
    LiveTurn turn(turn_ledger,memory,id(self()));
    world.init();TurnBudget budget{round,turn_ledger};
    if(!budget.current())return;
    economy.play(world,memory,budget,recovery_runtime,turn,stats);
}
