"""Dispatch draft and gameplay; a failed turn is logged and still yields."""
import cambc
from bot import Bot


PICK_ORDER = (2, 9, 0, 3, 10, 6, 8, 4, 7, 1, 5)


def main():
    bot = Bot()
    while True:
        try:
            if cambc.is_draft():
                chosen = {int(pick) for pick in cambc.draft.current_draft(cambc.Team.ALLY)}
                pick = next(candidate for candidate in PICK_ORDER if candidate not in chosen)
                cambc.draft.pick(pick)
            else:
                bot.play_turn()
        except Exception as error:
            phase = "draft" if cambc.is_draft() else "turn"
            print(f"LARP_ERROR|{phase}|{cambc.round_number()}|{error}", flush=True)
            if phase == "draft":
                try:
                    chosen = {int(pick) for pick in cambc.draft.current_draft(cambc.Team.ALLY)}
                    fallback = next((pick for pick in PICK_ORDER if pick not in chosen), None)
                    if fallback is not None:
                        cambc.draft.pick(fallback)
                except Exception as draft_error:
                    print(f"LARP_ERROR|draft_fallback|{cambc.round_number()}|{draft_error}", flush=True)

        cambc.end_turn()


if __name__ == "__main__":
    main()
