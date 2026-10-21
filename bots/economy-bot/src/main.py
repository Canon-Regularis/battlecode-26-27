"""Entry point for economy-bot."""
import cambc
import draft
from bot import Bot
from visualization import LoopOverlay


def main():
    bot = Bot()
    overlay = LoopOverlay()
    while True:
        try:
            if cambc.is_draft():
                draft.play()
            else:
                overlay.draw()
                bot.play_turn()
        except Exception as error:
            print(f"bot error: {error}", flush=True)

        cambc.end_turn()


if __name__ == "__main__":
    main()
