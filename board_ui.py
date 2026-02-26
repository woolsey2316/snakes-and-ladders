"""Tkinter board UI for Snakes and Ladders with 3D animated dice."""

import tkinter as tk
from tkinter import font as tkfont
import math
import random
from snakes_and_ladders import Game, Board

CELL = 70
PADDING = 40
COLS = 10
ROWS = 10

PLAYER_COLORS = ["#E74C3C", "#3498DB", "#2ECC71", "#F39C12"]
SNAKE_COLOR   = "#C0392B"
LADDER_COLOR  = "#27AE60"
BOARD_LIGHT   = "#FDFDE8"
BOARD_DARK    = "#F0E6CC"
GRID_COLOR    = "#BDC3C7"
DICE_DOT      = "#2C3E50"


def cell_center(square: int) -> tuple[int, int]:
    """Return canvas (x, y) centre of a square (1-indexed)."""
    sq = square - 1
    row = sq // COLS
    col = sq % COLS
    if row % 2 == 1:
        col = (COLS - 1) - col
    canvas_row = (ROWS - 1) - row
    x = PADDING + col * CELL + CELL // 2
    y = PADDING + canvas_row * CELL + CELL // 2
    return x, y


# ---------------------------------------------------------------------------
# 3-D Dice
# ---------------------------------------------------------------------------

class DiceCube3D:
    """Perspective-projected spinning die rendered on a Tkinter Canvas."""

    SIZE = 110   # canvas pixels

    VERTICES = [
        (-1, -1, -1), ( 1, -1, -1), ( 1,  1, -1), (-1,  1, -1),
        (-1, -1,  1), ( 1, -1,  1), ( 1,  1,  1), (-1,  1,  1),
    ]

    # (vertex_indices, outward_normal, die_value)
    FACES = [
        ([4, 5, 6, 7], ( 0,  0,  1), 1),   # +Z front
        ([3, 2, 1, 0], ( 0,  0, -1), 6),   # -Z back
        ([7, 6, 2, 3], ( 0,  1,  0), 2),   # +Y top
        ([0, 1, 5, 4], ( 0, -1,  0), 5),   # -Y bottom
        ([1, 2, 6, 5], ( 1,  0,  0), 3),   # +X right
        ([4, 7, 3, 0], (-1,  0,  0), 4),   # -X left
    ]

    # (sx, sy) in face local coords, –1 … 1
    DOT_LAYOUT = {
        1: [(0, 0)],
        2: [(-0.4, -0.4), (0.4, 0.4)],
        3: [(-0.4, -0.4), (0, 0), (0.4, 0.4)],
        4: [(-0.4, -0.4), (0.4, -0.4), (-0.4, 0.4), (0.4, 0.4)],
        5: [(-0.4, -0.4), (0.4, -0.4), (0, 0), (-0.4, 0.4), (0.4, 0.4)],
        6: [(-0.4, -0.4), (0.4, -0.4),
            (-0.4,  0.0), (0.4,  0.0),
            (-0.4,  0.4), (0.4,  0.4)],
    }

    # Base (rx, ry) that brings each face's value toward the camera (+Z axis)
    _BASE_ANGLES = {
        1: (0,            0),
        6: (0,            math.pi),
        2: ( math.pi / 2, 0),
        5: (-math.pi / 2, 0),
        3: (0,           -math.pi / 2),
        4: (0,            math.pi / 2),
    }
    # Aesthetic tilt added on top so you see two faces
    _TILT = (-0.35, 0.42)

    def __init__(self, parent: tk.Widget):
        self.canvas = tk.Canvas(
            parent, width=self.SIZE, height=self.SIZE,
            bg="#2C3E50", highlightthickness=0,
        )
        self.canvas.pack(pady=(10, 4))

        self.rx = self._BASE_ANGLES[1][0] + self._TILT[0]
        self.ry = self._BASE_ANGLES[1][1] + self._TILT[1]
        self.current_value = 1
        self._after_id   = None
        self._callback   = None
        self._frame      = 0
        self._total_frames = 0
        self._start_rx = self.rx
        self._start_ry = self.ry
        self._target_rx = self.rx
        self._target_ry = self.ry
        self._draw()

    # ------------------------------------------------------------------
    # Internal maths
    # ------------------------------------------------------------------

    @staticmethod
    def _rotate(v, rx, ry):
        x, y, z = v
        # around X
        y2 = y * math.cos(rx) - z * math.sin(rx)
        z2 = y * math.sin(rx) + z * math.cos(rx)
        # around Y
        x3 =  x * math.cos(ry) + z2 * math.sin(ry)
        z3 = -x * math.sin(ry) + z2 * math.cos(ry)
        return x3, y2, z3

    def _project(self, v3d):
        x, y, z = v3d
        # Perspective: camera at +Z, vertices in [-1,1]; near = larger
        fov = 4.0
        s = fov / (fov - z)
        scale = self.SIZE * 0.30 * s
        cx = cy = self.SIZE / 2
        return cx + x * scale, cy - y * scale

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self):
        self.canvas.delete("all")

        # Soft drop shadow
        half = self.SIZE // 2
        r = int(self.SIZE * 0.38)
        self.canvas.create_oval(
            half - r + 6, half - r + 8,
            half + r + 6, half + r + 8,
            fill="#1A252F", outline="", stipple="gray50",
        )

        rotated = [self._rotate(v, self.rx, self.ry) for v in self.VERTICES]
        proj    = [self._project(v) for v in rotated]

        visible = []
        for indices, normal, value in self.FACES:
            nx, ny, nz = self._rotate(normal, self.rx, self.ry)
            if nz > 0:
                avg_z = sum(rotated[i][2] for i in indices) / 4
                visible.append((avg_z, indices, value, nx, ny, nz))

        visible.sort(key=lambda f: f[0])   # painter's algorithm

        # Fixed world-space directional light (front-upper-right), pre-normalised
        _lx, _ly, _lz = 0.326, 0.543, 0.776

        for avg_z, indices, value, nx, ny, nz in visible:
            pts = [proj[i] for i in indices]
            flat = [c for p in pts for c in p]

            # Lambertian diffuse + ambient
            diffuse    = max(0.0, nx * _lx + ny * _ly + nz * _lz)
            brightness = 0.30 + 0.70 * diffuse
            # Ivory/cream base colour
            ri = min(255, int(253 * brightness))
            gi = min(255, int(245 * brightness))
            bi = min(255, int(225 * brightness))
            face_color = f"#{ri:02x}{gi:02x}{bi:02x}"

            self.canvas.create_polygon(flat, fill=face_color,
                                       outline="#5A6A7A", width=1.5,
                                       smooth=False)
            self._draw_dots(pts, value)

    def _draw_dots(self, corners, value):
        """Draw pips on a face described by 4 projected 2-D corners."""
        p0, p1, p2, p3 = corners
        cx = (p0[0] + p1[0] + p2[0] + p3[0]) / 4
        cy = (p0[1] + p1[1] + p2[1] + p3[1]) / 4
        # Right and up vectors in screen space
        rx_ = ((p1[0] - p0[0] + p2[0] - p3[0]) / 4,
               (p1[1] - p0[1] + p2[1] - p3[1]) / 4)
        ry_ = ((p3[0] - p0[0] + p2[0] - p1[0]) / 4,
               (p3[1] - p0[1] + p2[1] - p1[1]) / 4)
        face_scale = math.hypot(*rx_)
        dot_r = max(2.5, face_scale * 0.13)
        for sx, sy in self.DOT_LAYOUT[value]:
            dx = cx + sx * rx_[0] + sy * ry_[0]
            dy = cy + sx * rx_[1] + sy * ry_[1]
            self.canvas.create_oval(
                dx - dot_r, dy - dot_r,
                dx + dot_r, dy + dot_r,
                fill=DICE_DOT, outline="",
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def roll(self, value: int, callback):
        """Spin the cube and land showing *value* on the front face."""
        if self._after_id:
            self.canvas.after_cancel(self._after_id)
            self._after_id = None

        self._callback = callback
        self.current_value = value

        base_rx, base_ry = self._BASE_ANGLES[value]
        self._target_rx = base_rx + self._TILT[0]
        self._target_ry = base_ry + self._TILT[1]

        # Add several full rotations at the *start* so it tumbles before landing
        extra = random.uniform(2.5, 3.5)
        direction = random.choice([-1, 1])
        self._start_rx = self.rx + extra * 2 * math.pi
        self._start_ry = self.ry + extra * 2 * math.pi * direction

        self._total_frames = 60
        self._frame = 0
        self._animate()

    def _animate(self):
        t = self._frame / self._total_frames
        # Quintic ease-out
        ease = 1 - (1 - t) ** 5
        self.rx = self._target_rx + (1 - ease) * (self._start_rx - self._target_rx)
        self.ry = self._target_ry + (1 - ease) * (self._start_ry - self._target_ry)
        self._draw()

        self._frame += 1
        if self._frame <= self._total_frames:
            self._after_id = self.canvas.after(16, self._animate)
        else:
            self.rx, self.ry = self._target_rx, self._target_ry
            self._draw()
            self._after_id = None
            if self._callback:
                self._callback()


# ---------------------------------------------------------------------------
# Main board UI
# ---------------------------------------------------------------------------

class BoardUI:
    def __init__(self, root: tk.Tk, game: Game):
        self.root  = root
        self.game  = game
        self.root.title("🐍 Snakes and Ladders 🪜")
        self.root.resizable(False, False)

        board_px = PADDING * 2 + COLS * CELL
        self.canvas = tk.Canvas(root, width=board_px, height=board_px, bg="#ECF0F1")
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)

        # ---- Side panel ----
        panel = tk.Frame(root, bg="#2C3E50", width=230)
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        panel.pack_propagate(False)

        title_font = tkfont.Font(family="Helvetica", size=13, weight="bold")
        info_font  = tkfont.Font(family="Helvetica", size=11)
        small_font = tkfont.Font(family="Helvetica", size=10)

        tk.Label(panel, text="🐍 Snakes & Ladders 🪜",
                 font=title_font, bg="#2C3E50", fg="white").pack(pady=(14, 4))

        # 3-D dice
        self.dice_cube = DiceCube3D(panel)

        # Roll value readout
        self.roll_value_var = tk.StringVar(value="")
        tk.Label(panel, textvariable=self.roll_value_var,
                 font=tkfont.Font(family="Helvetica", size=16, weight="bold"),
                 bg="#2C3E50", fg="#F1C40F").pack()

        tk.Frame(panel, bg="#4A4A4A", height=1).pack(fill=tk.X, padx=12, pady=8)

        # Player labels
        self.player_labels: list[tk.Label] = []
        for i, player in enumerate(game.players):
            color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
            lbl = tk.Label(panel, text=self._player_text(i),
                           font=info_font, bg="#2C3E50", fg=color,
                           anchor="w", justify=tk.LEFT)
            lbl.pack(fill=tk.X, padx=12, pady=2)
            self.player_labels.append(lbl)

        tk.Frame(panel, bg="#4A4A4A", height=1).pack(fill=tk.X, padx=12, pady=8)

        self.turn_var  = tk.StringVar(value="Press Roll to start!")
        self.event_var = tk.StringVar(value="")
        tk.Label(panel, textvariable=self.turn_var, font=small_font,
                 bg="#2C3E50", fg="#BDC3C7", wraplength=200,
                 anchor="w", justify=tk.LEFT).pack(fill=tk.X, padx=12)
        tk.Label(panel, textvariable=self.event_var, font=small_font,
                 bg="#2C3E50", fg="#F1C40F", wraplength=200,
                 anchor="w", justify=tk.LEFT).pack(fill=tk.X, padx=12, pady=(3, 0))

        tk.Frame(panel, bg="#4A4A4A", height=1).pack(fill=tk.X, padx=12, pady=8)

        self.roll_btn = tk.Button(
            panel, text="Roll Dice 🎲",
            font=title_font, bg="#E67E22", fg="white",
            activebackground="#D35400", activeforeground="white",
            relief=tk.FLAT, cursor="hand2", pady=8,
            command=self.take_turn,
        )
        self.roll_btn.pack(fill=tk.X, padx=12, pady=4)

        tk.Button(
            panel, text="New Game ↺",
            font=small_font, bg="#34495E", fg="#BDC3C7",
            activebackground="#2C3E50", activeforeground="white",
            relief=tk.FLAT, cursor="hand2", pady=6,
            command=self.new_game,
        ).pack(fill=tk.X, padx=12, pady=4)

        # Legend
        tk.Frame(panel, bg="#4A4A4A", height=1).pack(fill=tk.X, padx=12, pady=8)
        tk.Label(panel, text="Legend", font=small_font,
                 bg="#2C3E50", fg="#95A5A6").pack(anchor="w", padx=12)
        for sym, label, color in [("━━", "Ladder", LADDER_COLOR),
                                   ("━━", "Snake",  SNAKE_COLOR)]:
            row_f = tk.Frame(panel, bg="#2C3E50")
            row_f.pack(fill=tk.X, padx=12, pady=1)
            tk.Label(row_f, text=sym, font=small_font,
                     bg="#2C3E50", fg=color).pack(side=tk.LEFT)
            tk.Label(row_f, text=f" {label}", font=small_font,
                     bg="#2C3E50", fg="#BDC3C7").pack(side=tk.LEFT)

        self._draw_board()
        self._draw_players()

    # ------------------------------------------------------------------
    # Board drawing
    # ------------------------------------------------------------------

    def _draw_board(self):
        self.canvas.delete("board")
        for sq in range(1, 101):
            x, y   = cell_center(sq)
            x0, y0 = x - CELL // 2, y - CELL // 2
            x1, y1 = x + CELL // 2, y + CELL // 2
            fill = BOARD_LIGHT if sq % 2 == 0 else BOARD_DARK
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill,
                                         outline=GRID_COLOR, tags="board")
            self.canvas.create_text(x0 + 5, y0 + 4, text=str(sq),
                                    anchor="nw", font=("Helvetica", 7),
                                    fill="#95A5A6", tags="board")
        for bottom, top in self.game.board.ladders.items():
            self._draw_ladder(bottom, top)
        for head, tail in self.game.board.snakes.items():
            self._draw_snake(head, tail)

    def _draw_ladder(self, bottom: int, top: int):
        bx, by = cell_center(bottom)
        tx, ty = cell_center(top)
        dx = 6
        angle = math.atan2(ty - by, tx - bx) + math.pi / 2
        ox, oy = math.cos(angle) * dx, math.sin(angle) * dx
        for ox_, oy_ in [(ox, oy), (-ox, -oy)]:
            self.canvas.create_line(bx - ox_, by - oy_, tx - ox_, ty - oy_,
                                    fill=LADDER_COLOR, width=4, tags="board",
                                    capstyle=tk.ROUND)
        steps = max(2, int(math.hypot(tx - bx, ty - by) // 22))
        for i in range(1, steps + 1):
            t = i / (steps + 1)
            mx, my = bx + (tx - bx) * t, by + (ty - by) * t
            self.canvas.create_line(mx - ox, my - oy, mx + ox, my + oy,
                                    fill=LADDER_COLOR, width=3, tags="board")

    def _draw_snake(self, head: int, tail: int):
        hx, hy = cell_center(head)
        tx, ty = cell_center(tail)
        length = math.hypot(tx - hx, ty - hy)
        angle  = math.atan2(ty - hy, tx - hx)
        perp   = angle + math.pi / 2
        wave   = min(length * 0.25, 40)
        c1x = hx + (tx - hx) * 0.33 + math.cos(perp) * wave
        c1y = hy + (ty - hy) * 0.33 + math.sin(perp) * wave
        c2x = hx + (tx - hx) * 0.66 - math.cos(perp) * wave
        c2y = hy + (ty - hy) * 0.66 - math.sin(perp) * wave
        pts, N = [], 30
        for i in range(N + 1):
            t = i / N
            x = (1-t)**3*hx + 3*(1-t)**2*t*c1x + 3*(1-t)*t**2*c2x + t**3*tx
            y = (1-t)**3*hy + 3*(1-t)**2*t*c1y + 3*(1-t)*t**2*c2y + t**3*ty
            pts += [x, y]
        self.canvas.create_line(*pts, fill=SNAKE_COLOR, width=5,
                                smooth=True, tags="board", capstyle=tk.ROUND)
        r = 8
        self.canvas.create_oval(hx-r, hy-r, hx+r, hy+r,
                                fill=SNAKE_COLOR, outline="white", width=2,
                                tags="board")
        tongue_len = 10
        dx = math.cos(angle + math.pi) * tongue_len
        dy = math.sin(angle + math.pi) * tongue_len
        for sign in (0.4, -0.4):
            fx = math.cos(angle + math.pi + sign) * 5
            fy = math.sin(angle + math.pi + sign) * 5
            self.canvas.create_line(hx, hy, hx+dx, hy+dy,
                                    fill="#FF6B6B", width=2, tags="board")
            self.canvas.create_line(hx+dx, hy+dy, hx+dx+fx, hy+dy+fy,
                                    fill="#FF6B6B", width=2, tags="board")

    def _draw_players(self, override: dict[int, int] | None = None,
                      exclude: set[int] | None = None):
        """Draw all player circles.
        override maps player_idx → temporary square.
        exclude is a set of player indices to skip entirely."""
        self.canvas.delete("player")
        buckets: dict[int, list[int]] = {}
        for i, p in enumerate(self.game.players):
            if exclude and i in exclude:
                continue
            sq = override[i] if (override and i in override) else p.position
            buckets.setdefault(sq, []).append(i)
        for sq, indices in buckets.items():
            if sq == 0:
                continue
            cx, cy = cell_center(sq)
            offsets = self._ring_offsets(len(indices))
            for j, i in enumerate(indices):
                color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
                ox, oy = offsets[j]
                r = 12
                self.canvas.create_oval(cx+ox-r, cy+oy-r, cx+ox+r, cy+oy+r,
                                        fill=color, outline="white", width=2,
                                        tags="player")
                self.canvas.create_text(cx+ox, cy+oy, text=str(i+1),
                                        font=("Helvetica", 9, "bold"),
                                        fill="white", tags="player")

    @staticmethod
    def _ring_offsets(n: int) -> list[tuple[int, int]]:
        if n == 1:
            return [(0, 0)]
        r = 14
        return [(int(r * math.cos(2 * math.pi * k / n)),
                 int(r * math.sin(2 * math.pi * k / n)))
                for k in range(n)]

    def _player_text(self, i: int) -> str:
        p = self.game.players[i]
        return f"P{i+1} {p.name}: sq {p.position}"

    # ------------------------------------------------------------------
    # Game actions
    # ------------------------------------------------------------------

    def take_turn(self):
        if self.game.winner:
            return
        self.roll_btn.config(state=tk.DISABLED)
        self.roll_value_var.set("")
        self.event_var.set("")

        # Capture who is moving and where they start BEFORE the turn advances
        player_idx = self.game.current_index
        start_pos  = self.game.players[player_idx].position
        result     = self.game.take_turn()

        self.roll_value_var.set(f"⚄ {result['roll']}")

        def on_dice_done():
            roll_text = (f"Turn {result['turn']}: {result['player']} "
                         f"rolled {result['roll']}")
            if not result["moved"]:
                roll_text += " (overshoot!)"
            self.turn_var.set(roll_text)

            if not result["moved"]:
                self._finish_turn(result, {})
                return

            # Walk one square at a time to the intermediate square (pre-snake/ladder)
            intermediate = start_pos + result["roll"]
            roll_path = list(range(start_pos + 1, intermediate + 1))

            def on_roll_walk_done(override):
                if not result["event"]:
                    self._finish_turn(result, override)
                    return
                # Brief pause so the player "lands" visibly before the slide
                self.event_var.set(result["event"])
                final = result["position"]
                # Ladders slide upward (~700 ms), snakes drop down (~500 ms)
                duration = 700 if final > intermediate else 500
                self.root.after(300, lambda: self._pixel_slide(
                    player_idx, intermediate, final, duration,
                    lambda: self._finish_turn(result, {}),
                ))

            self._animate_steps(player_idx, roll_path, {}, 160, on_roll_walk_done)

        self.dice_cube.roll(result["roll"], on_dice_done)

    def _animate_steps(self, player_idx: int, path: list[int],
                       override: dict, delay_ms: int, on_done):
        """Step player_idx along path one square at a time, then call on_done(override)."""
        if not path:
            on_done(override)
            return
        sq, rest = path[0], path[1:]
        override = {**override, player_idx: sq}
        self._draw_players(override)
        self.root.after(delay_ms,
                        lambda: self._animate_steps(player_idx, rest,
                                                    override, delay_ms, on_done))

    def _pixel_slide(self, player_idx: int, from_sq: int, to_sq: int,
                     duration_ms: int, on_done):
        """Smoothly slide player_idx in a straight line from from_sq to to_sq."""
        x0, y0 = cell_center(from_sq)
        x1, y1 = cell_center(to_sq)
        total_frames = max(20, duration_ms // 16)
        color = PLAYER_COLORS[player_idx % len(PLAYER_COLORS)]
        label = str(player_idx + 1)

        # All other players stay at their real positions throughout
        self._draw_players(exclude={player_idx})

        def step(frame):
            t = frame / total_frames
            # Smooth ease-in-out (smoothstep)
            t_ease = t * t * (3 - 2 * t)
            x = x0 + (x1 - x0) * t_ease
            y = y0 + (y1 - y0) * t_ease
            self.canvas.delete("sliding_player")
            r = 12
            self.canvas.create_oval(x - r, y - r, x + r, y + r,
                                    fill=color, outline="white", width=2,
                                    tags=("player", "sliding_player"))
            self.canvas.create_text(x, y, text=label,
                                    font=("Helvetica", 9, "bold"),
                                    fill="white",
                                    tags=("player", "sliding_player"))
            if frame < total_frames:
                self.root.after(16, lambda: step(frame + 1))
            else:
                on_done()

        step(0)

    def _finish_turn(self, result: dict, override: dict):
        """Settle final positions, update labels, re-enable button."""
        for i in range(len(self.game.players)):
            self.player_labels[i].config(text=self._player_text(i))
        self._draw_players()   # use real game positions

        if result["winner"]:
            self.turn_var.set(f"🏆 {result['winner']} wins!")
            self.event_var.set(f"Finished in {result['turn']} turns!")
            self.roll_btn.config(state=tk.DISABLED, text="Game Over")
        else:
            self.roll_btn.config(state=tk.NORMAL)

    def new_game(self):
        names = [p.name for p in self.game.players]
        self.game = Game(player_names=names)
        self.turn_var.set("Press Roll to start!")
        self.event_var.set("")
        self.roll_value_var.set("")
        self.roll_btn.config(state=tk.NORMAL, text="Roll Dice 🎲")
        for i in range(len(self.game.players)):
            self.player_labels[i].config(text=self._player_text(i))
        self._draw_board()
        self._draw_players()
        self.dice_cube.rx = DiceCube3D._BASE_ANGLES[1][0] + DiceCube3D._TILT[0]
        self.dice_cube.ry = DiceCube3D._BASE_ANGLES[1][1] + DiceCube3D._TILT[1]
        self.dice_cube._draw()


def main():
    root = tk.Tk()
    game = Game(player_names=["Alice", "Bob", "Charlie"])
    BoardUI(root, game)
    root.mainloop()


if __name__ == "__main__":
    main()
