import cambc
import suite


def main():
    drafted = False
    played = False
    while True:
        try:
            if cambc.is_draft():
                if not drafted:
                    suite.run_draft()
                    drafted = True
                chosen = cambc.draft.current_draft(cambc.Team.ALLY)
                cambc.draft.pick(next(p for p in range(11) if p not in chosen))
            elif not played:
                suite.run_game()
                played = True
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print("FATAL " + repr(exc), flush=True)
            raise
        cambc.end_turn()


main()
