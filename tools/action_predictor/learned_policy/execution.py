"""Strategy-free command dispatch; no farming, routing or economic preferences."""
from dataclasses import dataclass
from typing import Any

class UnsupportedCommand(ValueError):pass
class AmbiguousTarget(ValueError):pass

@dataclass(frozen=True)
class Command:
    action:str
    position:tuple[int,int]|None=None
    priority:int|None=None
    target_kind:str|None=None
    item:Any=None
    count:int|None=None

@dataclass(frozen=True)
class Execution:
    requested:Command
    actual_action:str
    result:Any

class SDK4Executor:
    """Dispatch only, with personal live handles supplied by the observation bridge.

    A tile does not uniquely establish original target identity. Mixed ground/unit
    casts require an explicit target kind; otherwise execution is refused. Missing
    purchases are never replaced with a hand-designed shopping strategy.
    """
    def __init__(self,sdk,cancel_channel):
        self.sdk=sdk;self.cancel_channel=cancel_channel
    def execute(self,command,compatible_targets=()):
        me=self.sdk.me();name=command.action;tile=None
        if command.position is not None:tile=self.sdk.Vec2(*command.position)
        def target():
            if len(compatible_targets)!=1:raise AmbiguousTarget('Exactly one personally visible compatible target is required')
            if tile is None:raise UnsupportedCommand('Missing learned target coordinate')
            pos=compatible_targets[0].position()
            if (pos.x,pos.y)!=command.position:raise UnsupportedCommand('Visible handle does not match the learned target coordinate')
            return compatible_targets[0]
        if name in ('move','blocked'):
            if tile is None:raise UnsupportedCommand('Missing attempted destination')
            result=me.move_absolute(tile);return Execution(command,'move' if result else 'blocked',result)
        if name=='attack':result=me.attack(target())
        elif name in ('cast_0','cast_1'):
            ability=me.abilities()[int(name[-1])];mask=int(ability.valid_targets());kind=command.target_kind
            if kind is None:
                if mask==0:kind='none'
                elif mask==16:kind='ground'
                elif not mask&16:kind='unit'
                else:raise AmbiguousTarget('Mixed ground/unit command requires a learned or recorded target kind')
            if kind=='unit':result=ability.use(target())
            elif kind=='ground' and mask&16 and tile is not None:result=ability.use(tile)
            elif kind=='none' and mask==0:result=ability.use()
            else:raise UnsupportedCommand('Target kind does not match available SDK ability mask')
        elif name=='priority':
            if type(command.priority) is not int:raise UnsupportedCommand('Exact integer priority required')
            result=me.set_priority(command.priority)
        elif name=='recall':result=me.recall()
        elif name=='cancel':result=self.cancel_channel()
        elif name=='end':result=me.end_turn()
        elif name=='ward':
            if tile is None:raise UnsupportedCommand('Missing ward destination')
            result=me.place_ward(tile)
        elif name=='submit':
            if tile is None:raise UnsupportedCommand('Missing altar tile')
            result=me.submit_gems(tile)
        elif name in ('altar','teleport'):
            if tile is None:raise UnsupportedCommand('Missing consumable destination')
            kind=self.sdk.ConsumableType.ALTAR_LOCK if name=='altar' else self.sdk.ConsumableType.TP_CRYSTAL;slots=[c for c in me.consumables() if c.kind()==kind]
            if len(slots)!=1:raise UnsupportedCommand('No unique SDK consumable slot')
            result=slots[0].use(tile)
        elif name=='shop':
            if command.item is None or type(command.count) is not int or command.count<=0:raise UnsupportedCommand('Original purchase arguments unavailable; no fabricated purchase')
            result=me.buy(command.item,command.count)
        else:raise UnsupportedCommand('No executable command for '+name)
        return Execution(command,name,result)
