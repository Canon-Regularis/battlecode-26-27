"""D1 entry point: a standalone economic policy with a small action loop."""

import cambc
import draft


def main():
    bot = None
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                if bot is None:
                    from d1 import D1
                    bot = D1()
                bot.turn()
        except Exception as error:
            phase = "draft" if cambc.is_draft() else "turn"
            print(f"D1_ERROR|{phase}|{cambc.round_number()}|{error}", flush=True)
        cambc.end_turn()


if __name__ == "__main__":
    main()
