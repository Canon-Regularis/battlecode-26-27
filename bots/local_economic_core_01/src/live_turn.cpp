#include "live_turn.h"
namespace lp {
bool LiveTurn::preflight(action::Op op) {
    using action::Op;
    check();auto& me=self();
    const auto state=read([&]{return me.state();});
    ledger_.channel_history(state.contains(champion_state::recall_started),
        state.contains(champion_state::recall_cancelled),
        state.contains(champion_state::submit_gems_started));
    const bool alive=state.contains(champion_state::alive);
    const bool channeling=state.contains(champion_state::recalling)||
        state.contains(champion_state::submitting_gems)||state.contains(champion_state::teleporting);
    if(op==Op::priority)return !channeling;
    if(op==Op::item_buy||op==Op::consumable_buy)return !channeling&&
        (!alive||!read([&]{return me.restrictions();}).contains(buff_restrictions::shop));
    if(!alive||state.contains(champion_state::completed_turn)||
        state.contains(champion_state::submitting_gems)||state.contains(champion_state::teleporting))return false;
    if(read([&]{return me.buffs().has_stun();}))return false;
    if(op==Op::cancel_recall)return state.contains(champion_state::recalling)&&
        !state.contains(champion_state::recall_cancelled);
    if(state.contains(champion_state::recalling))return false;
    const auto restrictions=read([&]{return me.restrictions();});
    switch(op) {
    case Op::step:return state.contains(champion_state::can_move)&&!restrictions.contains(buff_restrictions::move);
    case Op::dash:return state.contains(champion_state::can_cast)&&
        !restrictions.contains(buff_restrictions::move)&&!restrictions.contains(buff_restrictions::cast);
    case Op::basic:case Op::lock_basic:return state.contains(champion_state::can_attack)&&
        !restrictions.contains(buff_restrictions::attack);
    case Op::reset:case Op::shield:case Op::heal:case Op::cast:return state.contains(champion_state::can_cast)&&
        !restrictions.contains(buff_restrictions::cast);
    case Op::recall:return !state.contains(champion_state::recall_started)&&!state.contains(champion_state::recall_cancelled);
    case Op::submit:return !state.contains(champion_state::submit_gems_started);
    case Op::lock_use:return !restrictions.contains(buff_restrictions::consumable);
    case Op::ward:return !restrictions.contains(buff_restrictions::ward);
    default:return false;
    }
}
}
