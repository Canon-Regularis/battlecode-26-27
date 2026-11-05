// Dispatch draft and gameplay; a failed turn is logged and still yields.
#include <cambc.h>
#include <iostream>
#include "bot.h"
#include "phase_profile.h"
#include "draft.h"

int main() {
    Bot bot;
    while (true) {
        try {
            if (cambc::is_draft())
                play_draft();
            else
                bot.play_turn();
        } catch (const cambc::error& error) {
            if(error.code()==cambc::error_code::api_not_in_vision||error.code()==cambc::error_code::api_not_found)
                bot.stale();
            else bot.error(error.what());
        } catch (const std::exception& error) {
            bot.error(error.what());
        } catch (...) {
            bot.error("unknown exception");
        }

        PPFX_SAFE_POINT()
        cambc::end_turn();
    }
}
