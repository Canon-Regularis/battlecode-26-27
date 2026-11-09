"""Decision-only V59 destination dispatch; the caller's action choice is frozen.

One instance per actor. Predict before observing the actual command. Every own
turn (including unavailable observations) must be completed, and real gaps reset
the adapter. The movement network advances once per turn, at the first observed
nonadministrative command, matching its training chronology. The current command
never determines whether its own prediction is eligible.
"""
from .data import ADMIN


def dispatch(prediction, coordinate, movement, eligible):
    """Return an offset ID without reading a target or changing the action type."""
    if prediction != 8 or not eligible or movement is None:
        return coordinate
    dx, dy = movement
    if type(dx) is not int or type(dy) is not int or max(abs(dx), abs(dy)) > 1:
        raise ValueError('Expected a supported one-step movement offset')
    return (dy + 8) * 17 + dx + 8


class TurnMovementAdapter:
    def __init__(self, predictor=None):
        if predictor is None:
            from .trajectory_movement_predictor import TrajectoryMovementPredictor
            predictor = TrajectoryMovementPredictor()
        self.predictor = predictor
        self.state = None
        self.active = False

    def begin_turn(self):
        if self.active:
            raise RuntimeError('Finish the preceding turn first')
        self.active = True
        self.seen_nonadmin = False
        self.next_state = None
        self.pending = None

    def predict(self, current, route, round_number, previous, previous_mask, previous_moves):
        if not self.active or self.pending is not None:
            raise RuntimeError('Predict once, then observe that command')
        if self.seen_nonadmin:
            self.pending = dict(eligible=False, movement=None, forecast=None)
            return self.pending
        value = self.predictor.predict(current, route, round_number, previous,
                                       previous_mask, self.state, previous_moves=previous_moves)
        destination = value['conditional_movement']
        movement = None
        if destination is not None:
            origin = current['observation']['own']['position']
            movement = (int(destination[0] - origin['x']), int(destination[1] - origin['y']))
        self.pending = dict(eligible=True, movement=movement, forecast=value)
        return self.pending

    def observe(self, family):
        if not self.active or self.pending is None:
            raise RuntimeError('Prediction must precede command assimilation')
        if not self.seen_nonadmin and family not in ADMIN:
            self.seen_nonadmin = True
            self.next_state = self.pending['forecast']['state']
        self.pending = None

    def skip_admin(self):
        """Advance an unavailable administrative command without reading its future."""
        if not self.active or self.pending is not None:
            raise RuntimeError('Invalid administrative skip')

    def finish_turn(self, route, round_number, previous, previous_mask, previous_moves):
        if not self.active or self.pending is not None:
            raise RuntimeError('Assimilate the last command before finishing')
        if not self.seen_nonadmin:
            value = self.predictor.predict(None, route, round_number, previous,
                                           previous_mask, self.state, previous_moves=previous_moves)
            self.next_state = value['state']
        self.state = self.next_state
        self.active = False

