// Dispatch draft and gameplay; a failed turn is logged and still yields.
#include <cambc.h>
#include <iostream>
#include "bot.h"
#include "draft.h"

int main() {
    Bot bot;
    while (true) {
        try {
            if (cambc::is_draft())
                play_draft();
            else
                bot.play_turn();
        } catch (const lp::TurnExpired&) {
            bot.stale();
        } catch (const lp::TurnDeferred&) {
            bot.stale();
        } catch (const cambc::error& error) {
            if(error.code()==cambc::error_code::api_not_in_vision||error.code()==cambc::error_code::api_not_found)
                bot.stale();
            else bot.error(error.what());
        } catch (const std::exception& error) {
            bot.error(error.what());
        } catch (...) {
            bot.error("unknown exception");
        }

        cambc::end_turn();
    }
}
