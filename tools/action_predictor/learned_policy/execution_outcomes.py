"""Additive SDK return contract; frozen L00 execution sources stay unchanged.

The learned likelihood represents command families, with an explicit movement
outcome split only. A failed cast/ward/consumable is NOT a successful effect and
is NOT relabeled as blocked movement. Its issued family can condition the command
filter; the unmodeled SDK result must remain available to the caller and next PRE.
Historical mapping of these false-return attempts is not certified by this port.
"""
from dataclasses import dataclass
from typing import Any
from .execution import Command, SDK4Executor


@dataclass(frozen=True)
class CommandOutcome:
    requested: Command
    api_returned: bool
    accepted_attempt: bool | None
    api_result: Any
    filter_action: str | None
    effect_status: str
    effect_completed: bool | None
    exception_type: str | None = None

    @property
    def actual_action(self):
        """Legacy actor interface: family observation, not an effect-success label."""
        if not self.api_returned or self.filter_action is None:
            raise ValueError('No returned command-family observation to assimilate')
        return self.filter_action

    @property
    def result(self):
        return self.api_result


class OutcomeExecutor(SDK4Executor):
    """Same SDK dispatch, preserving request, accepted attempt and reported effect.

    Both actors may consume actual_action for command-family filtering. They do
    not consume effect_completed: their frozen representation has no such input.
    Returned False is recorded separately; it never certifies a successful ward,
    cast, or consumable. A live bridge must observe the resulting personal PRE.
    No new benchmark labels or successful-effect observations are fabricated.
    """
    def __init__(self, sdk, cancel_channel):
        super().__init__(sdk, cancel_channel)
        self.last_outcome = None

    def execute(self, command, compatible_targets=()):
        try:
            execution = super().execute(command, compatible_targets)
        except Exception as error:
            # The wrapper cannot establish whether an arbitrary exception was
            # raised before or after a host-side effect. Do not invent acceptance.
            self.last_outcome = CommandOutcome(command, False, None, None, None,
                                               'exception_effect_unknown', None,
                                               type(error).__name__)
            raise
        boolean_api = command.action in ('move', 'blocked', 'cast_0', 'cast_1',
                                         'ward', 'altar', 'teleport')
        if boolean_api and type(execution.result) is not bool:
            self.last_outcome = CommandOutcome(command, True, None, execution.result,
                                               None, 'unexpected_return_type', None)
            raise TypeError('SDK boolean-return command did not return bool')
        completed = execution.result if boolean_api else None
        effect = ('sdk_reported_completion' if completed else
                  'newly_revealed_obstruction') if boolean_api else 'not_reported'
        self.last_outcome = CommandOutcome(command, True, True, execution.result,
                                           execution.actual_action, effect, completed)
        return self.last_outcome
