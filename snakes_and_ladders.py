"""Snakes and Ladders game using object-oriented design."""

import random
from dataclasses import dataclass, field
from typing import Optional


class Dice:
    """A six-sided dice."""

    def __init__(self, sides: int = 6):
        self.sides = sides

    def roll(self) -> int:
        return random.randint(1, self.sides)


@dataclass
class Snake:
    """A snake with a head (higher) and tail (lower) position."""

    head: int
    tail: int

    def __post_init__(self):
        if self.head <= self.tail:
            raise ValueError(f"Snake head ({self.head}) must be above tail ({self.tail})")


@dataclass
class Ladder:
    """A ladder with a bottom (lower) and top (higher) position."""

    bottom: int
    top: int

    def __post_init__(self):
        if self.bottom >= self.top:
            raise ValueError(f"Ladder bottom ({self.bottom}) must be below top ({self.top})")


class Board:
    """A 10x10 Snakes and Ladders board."""

    SIZE = 100

    # Classic Snakes and Ladders layout
    DEFAULT_SNAKES = [
        Snake(99, 7),
        Snake(95, 56),
        Snake(92, 53),
        Snake(73, 19),
        Snake(62, 19),
        Snake(54, 34),
        Snake(17, 7),
    ]

    DEFAULT_LADDERS = [
        Ladder(4, 56),
        Ladder(9, 31),
        Ladder(20, 38),
        Ladder(28, 84),
        Ladder(40, 59),
        Ladder(51, 67),
        Ladder(63, 81),
        Ladder(71, 91),
    ]

    def __init__(
        self,
        snakes: Optional[list[Snake]] = None,
        ladders: Optional[list[Ladder]] = None,
    ):
        self.snakes: dict[int, int] = {}   # head -> tail
        self.ladders: dict[int, int] = {}  # bottom -> top

        for snake in (snakes if snakes is not None else self.DEFAULT_SNAKES):
            self.snakes[snake.head] = snake.tail

        for ladder in (ladders if ladders is not None else self.DEFAULT_LADDERS):
            self.ladders[ladder.bottom] = ladder.top

    def resolve(self, position: int) -> tuple[int, Optional[str]]:
        """Return final position and event description after landing on a square."""
        if position in self.snakes:
            new_pos = self.snakes[position]
            return new_pos, f"🐍 Snake! Slides down from {position} to {new_pos}"
        if position in self.ladders:
            new_pos = self.ladders[position]
            return new_pos, f"🪜 Ladder! Climbs up from {position} to {new_pos}"
        return position, None


@dataclass
class Player:
    """A player with a name and board position."""

    name: str
    position: int = 0

    def move(self, steps: int, board_size: int) -> bool:
        """Move the player. Returns True if the move was applied, False if it overshoots."""
        new_position = self.position + steps
        if new_position > board_size:
            return False  # overshoot — stay put
        self.position = new_position
        return True

    @property
    def has_won(self) -> bool:
        return self.position == Board.SIZE


class Game:
    """Orchestrates a game of Snakes and Ladders."""

    def __init__(self, player_names: list[str], board: Optional[Board] = None):
        if len(player_names) < 2:
            raise ValueError("At least 2 players are required.")
        self.board = board or Board()
        self.dice = Dice()
        self.players: list[Player] = [Player(name) for name in player_names]
        self.current_index: int = 0
        self.winner: Optional[Player] = None
        self.turn_number: int = 0

    @property
    def current_player(self) -> Player:
        return self.players[self.current_index]

    def take_turn(self) -> dict:
        """Execute one turn and return a summary of what happened."""
        if self.winner:
            return {"error": f"Game already won by {self.winner.name}!"}

        self.turn_number += 1
        player = self.current_player
        roll = self.dice.roll()

        moved = player.move(roll, self.board.SIZE)
        event: Optional[str] = None

        if moved:
            player.position, event = self.board.resolve(player.position)

        result = {
            "turn": self.turn_number,
            "player": player.name,
            "roll": roll,
            "moved": moved,
            "position": player.position,
            "event": event,
            "winner": None,
        }

        if player.has_won:
            self.winner = player
            result["winner"] = player.name
        else:
            self.current_index = (self.current_index + 1) % len(self.players)

        return result

    def play(self, verbose: bool = True) -> Player:
        """Play a full game and return the winner."""
        if verbose:
            print("=" * 50)
            print("🎲 SNAKES AND LADDERS")
            print("=" * 50)
            names = ", ".join(p.name for p in self.players)
            print(f"Players: {names}\n")

        while not self.winner:
            result = self.take_turn()
            if verbose:
                self._print_turn(result)

        if verbose:
            print("=" * 50)
            print(f"🏆 {self.winner.name} wins in {self.turn_number} turns!")
            print("=" * 50)

        return self.winner

    def _print_turn(self, result: dict) -> None:
        parts = [
            f"Turn {result['turn']:>3} | {result['player']:<12} | "
            f"Rolled {result['roll']} | Position: {result['position']:>3}"
        ]
        if not result["moved"]:
            parts.append("(overshoot — stayed put)")
        if result["event"]:
            parts.append(f"| {result['event']}")
        if result["winner"]:
            parts.append(f"| 🏆 WINS!")
        print("  ".join(parts))

    def board_summary(self) -> str:
        """Return a formatted summary of snakes and ladders on the board."""
        lines = ["Board Layout:", "  Snakes (head → tail):"]
        for head, tail in sorted(self.board.snakes.items(), reverse=True):
            lines.append(f"    {head:>3} → {tail:>3}")
        lines.append("  Ladders (bottom → top):")
        for bottom, top in sorted(self.board.ladders.items()):
            lines.append(f"    {bottom:>3} → {top:>3}")
        return "\n".join(lines)


if __name__ == "__main__":
    game = Game(player_names=["Alice", "Bob", "Charlie"])
    print(game.board_summary())
    print()
    game.play(verbose=True)
