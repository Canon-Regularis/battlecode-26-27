"""Drawing only: route links are not literal terrain-following paths."""

COLORS = (("green", 0x00DD88), ("cyan", 0x00BBFF), ("orange", 0xFFAA22),
          ("purple", 0xCC66FF), ("pink", 0xFF5588))
ROUNDS_PER_LOOP = 8


def loop_index(round_number, count):
    return max(0, round_number - 1) // ROUNDS_PER_LOOP % max(1, count)


def camp_members(plan):
    """Resolve static group tiles once; no visibility or live-state queries."""
    import cambc

    members = {}
    for _, camps in plan.routes:
        for anchor in camps:
            if anchor not in members:
                group = cambc.game_map.camp(cambc.Vec2(*anchor)).camp_group()
                members[anchor] = tuple(group.spawn_tiles().positions())
    return members


def draw_route(altar, camps, rank, members):
    import cambc

    color = COLORS[rank % len(COLORS)][1]
    points = [altar, *camps, altar]
    for start, end in zip(points, points[1:]):
        a, b = cambc.Vec2(*start), cambc.Vec2(*end)
        cambc.debug.draw_line(a, b, color)
        # Integer-coordinate arrowheads show the traversal order.
        dx = (end[0] > start[0]) - (end[0] < start[0])
        dy = (end[1] > start[1]) - (end[1] < start[1])
        if not dx and not dy:
            continue
        for sign in (-1, 1):
            wing = cambc.Vec2(end[0] - dx - sign * dy, end[1] - dy + sign * dx)
            if cambc.game_map.is_in_bounds(wing):
                cambc.debug.draw_line(wing, b, color)
    # An anchor may be a gold cluster in a mixed group. Mark all the group's
    # monster/cluster tiles, not just the representative used for routing.
    for anchor in camps:
        for position in members[anchor]:
            cambc.debug.draw_dot(position, color)
    cambc.debug.draw_dot(cambc.Vec2(*altar), 0xFFFFFF)


def draw_plan(plan, rank=None, members=None):
    if members is None:
        members = camp_members(plan)
    routes = plan.routes
    if rank is not None:
        altar, camps = routes[rank]
        draw_route(altar, camps, rank, members)
    else:
        # Draw the best last so it remains visible on shared edges.
        for index in reversed(range(len(routes))):
            draw_route(*routes[index], index, members)


class LoopOverlay:
    """Redraw after draft so the visualiser has drawings on champion turns."""

    def __init__(self):
        self.plan = None
        self.members = None
        self.previous_rank = None

    def draw(self):
        import cambc
        from protocol import Plan

        if self.plan is None:
            self.plan = Plan.decode(bytes(cambc.draft_memory))
            self.members = camp_members(self.plan)
        rank = loop_index(cambc.round_number(), len(self.plan.routes))
        draw_plan(self.plan, rank, self.members)
        if rank != self.previous_rank:
            self.previous_rank = rank
            print(f"Loop overlay #{rank + 1} ({COLORS[rank % len(COLORS)][0]}): "
                  "waypoint arrows, not walking paths")
