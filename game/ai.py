"""
Spiritbound - overworld AI helpers (sight + pursuit).

Pure, pygame-free tile math for active-hunting trainers (#8): a sight-cone test
(does an NPC spot the player?) and a step-toward-player pursuit step. Kept out of
overworld.py so the geometry is unit-testable without a display or input.

Written by LJ "HawaiizFynest" Eblacas
"""

_DIRV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def in_sight_cone(nx, ny, facing, px, py, sight=4):
    """True if the player at (px, py) is within an NPC's sight cone.

    The NPC at (nx, ny) looks along `facing`. The cone extends up to `sight`
    tiles ahead and widens by one tile of lateral spread per tile of depth (a
    45-degree cone), so a distant player must be more directly in front. The
    player's own tile (depth 0) is never "spotted" (that's a contact, not a
    sighting). Pure integer geometry.
    """
    if facing not in _DIRV or sight <= 0:
        return False
    dx, dy = _DIRV[facing]
    rel_x, rel_y = px - nx, py - ny
    # depth = distance along the facing axis; lateral = perpendicular offset
    if dx != 0:                       # looking left/right
        depth = rel_x * dx
        lateral = abs(rel_y)
    else:                             # looking up/down
        depth = rel_y * dy
        lateral = abs(rel_x)
    if depth < 1 or depth > sight:
        return False
    return lateral <= depth           # 45-degree widening cone


def step_toward(nx, ny, px, py):
    """A single cardinal step (dx, dy) moving (nx, ny) toward (px, py).

    Closes the larger axis gap first (so the chaser doesn't wobble), returning
    one of the four unit steps, or (0, 0) when already on the player's tile.
    """
    rel_x, rel_y = px - nx, py - ny
    if rel_x == 0 and rel_y == 0:
        return (0, 0)
    if abs(rel_x) >= abs(rel_y):
        return (1 if rel_x > 0 else -1, 0)
    return (0, 1 if rel_y > 0 else -1)


def facing_toward(nx, ny, px, py):
    """The cardinal facing name that points (nx, ny) at (px, py)."""
    dx, dy = step_toward(nx, ny, px, py)
    for name, v in _DIRV.items():
        if v == (dx, dy):
            return name
    return "down"
