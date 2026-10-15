"""Dispatch draft and gameplay with the SDK template lifecycle."""
import cambc
import draft


def main():
    bot = None
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                # Keep draft execution lightweight. The draft is a separate
                # runtime phase and must submit picks before gameplay modules
                # are imported.
                if bot is None:
                    from simple_policy import Bot
                    bot = Bot()
                bot.play_turn()
        except Exception as error:
            phase = "draft" if cambc.is_draft() else "turn"
            print(f"LARP_ERROR|{phase}|{cambc.round_number()}|{error}", flush=True)
        cambc.end_turn()


if __name__ == "__main__":
    main()
