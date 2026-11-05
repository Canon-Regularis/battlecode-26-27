"""Competition entry point. Bot instances persist across their owner turns."""

import cambc
import draft
from strategy_config import ENABLE_EXPERIMENTAL_POLICY


def main():
    bot = None
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                if bot is None:
                    if ENABLE_EXPERIMENTAL_POLICY:
                        from policy import Bot
                    else:
                        from fast_policy import Bot
                    bot = Bot()
                bot.play_turn()
        except Exception as error:
            # A faulty tactical branch must not turn fuel exhaustion into
            # repeated suspended turns. The trace is present in replay logs.
            print(f"GD_ERROR|{cambc.round_number()}|{type(error).__name__}|{error}", flush=True)
        cambc.end_turn()


if __name__ == "__main__":
    main()
