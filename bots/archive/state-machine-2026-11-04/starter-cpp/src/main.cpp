// Dispatch draft and gameplay; a failed turn is logged and still yields.
#include <cambc.h>
#include <iostream>
#include "bot.h"
#include "draft.h"

int main() {
    Bot bot;
    while (true) {
        try {
            if (cambc::is_draft()) { current_bot_stage = "draft"; play_draft(); }
            else { current_bot_stage = "gameplay"; bot.play_turn(); }
        } catch (const std::exception& error) {
            std::cout << "bot error [" << current_bot_stage << "]: " << error.what() << std::endl;
        } catch (...) {
            std::cout << "bot error: unknown exception" << std::endl;
        }

        cambc::end_turn();
    }
}
