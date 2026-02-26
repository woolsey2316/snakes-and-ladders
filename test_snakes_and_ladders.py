"""Tests for the Snakes and Ladders game."""

import pytest
from unittest.mock import patch
from snakes_and_ladders import Board, Dice, Game, Ladder, Player, Snake


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

class TestDice:
    def test_roll_within_range(self):
        dice = Dice()
        for _ in range(200):
            result = dice.roll()
            assert 1 <= result <= 6

    def test_custom_sides(self):
        dice = Dice(sides=12)
        for _ in range(200):
            assert 1 <= dice.roll() <= 12


# ---------------------------------------------------------------------------
# Snake / Ladder validation
# ---------------------------------------------------------------------------

class TestSnake:
    def test_valid_snake(self):
        s = Snake(head=50, tail=20)
        assert s.head == 50 and s.tail == 20

    def test_invalid_snake_raises(self):
        with pytest.raises(ValueError):
            Snake(head=10, tail=50)


class TestLadder:
    def test_valid_ladder(self):
        l = Ladder(bottom=5, top=40)
        assert l.bottom == 5 and l.top == 40

    def test_invalid_ladder_raises(self):
        with pytest.raises(ValueError):
            Ladder(bottom=60, top=30)


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class TestBoard:
    def setup_method(self):
        self.board = Board(
            snakes=[Snake(50, 10)],
            ladders=[Ladder(20, 60)],
        )

    def test_snake_slides_down(self):
        pos, event = self.board.resolve(50)
        assert pos == 10
        assert "Snake" in event

    def test_ladder_climbs_up(self):
        pos, event = self.board.resolve(20)
        assert pos == 60
        assert "Ladder" in event

    def test_plain_square(self):
        pos, event = self.board.resolve(35)
        assert pos == 35
        assert event is None

    def test_default_board_loads(self):
        board = Board()
        assert len(board.snakes) > 0
        assert len(board.ladders) > 0


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class TestPlayer:
    def test_initial_position(self):
        p = Player("Alice")
        assert p.position == 0

    def test_normal_move(self):
        p = Player("Alice")
        moved = p.move(5, 100)
        assert moved is True
        assert p.position == 5

    def test_overshoot_stays_put(self):
        p = Player("Alice")
        p.position = 98
        moved = p.move(5, 100)
        assert moved is False
        assert p.position == 98

    def test_exact_win(self):
        p = Player("Alice")
        p.position = 94
        p.move(6, 100)
        assert p.has_won

    def test_not_won_initially(self):
        assert not Player("Alice").has_won


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class TestGame:
    def test_requires_minimum_players(self):
        with pytest.raises(ValueError):
            Game(["Solo"])

    def test_initial_state(self):
        game = Game(["Alice", "Bob"])
        assert game.current_player.name == "Alice"
        assert game.winner is None

    def test_turn_advances_player(self):
        game = Game(["Alice", "Bob"])
        with patch.object(game.dice, "roll", return_value=3):
            game.take_turn()
        assert game.current_player.name == "Bob"

    def test_overshoot_does_not_advance_turn(self):
        game = Game(["Alice", "Bob"])
        game.players[0].position = 99
        with patch.object(game.dice, "roll", return_value=6):
            result = game.take_turn()
        assert result["moved"] is False
        assert result["position"] == 99
        # Turn still passes to the next player
        assert game.current_player.name == "Bob"

    def test_snake_event_in_result(self):
        board = Board(snakes=[Snake(10, 3)], ladders=[])
        game = Game(["Alice", "Bob"], board=board)
        game.players[0].position = 4
        with patch.object(game.dice, "roll", return_value=6):
            result = game.take_turn()
        assert result["position"] == 3
        assert result["event"] is not None and "Snake" in result["event"]

    def test_ladder_event_in_result(self):
        board = Board(snakes=[], ladders=[Ladder(10, 50)])
        game = Game(["Alice", "Bob"], board=board)
        game.players[0].position = 4
        with patch.object(game.dice, "roll", return_value=6):
            result = game.take_turn()
        assert result["position"] == 50
        assert result["event"] is not None and "Ladder" in result["event"]

    def test_winner_detected(self):
        game = Game(["Alice", "Bob"])
        game.players[0].position = 94
        with patch.object(game.dice, "roll", return_value=6):
            result = game.take_turn()
        assert result["winner"] == "Alice"
        assert game.winner is not None

    def test_no_moves_after_win(self):
        game = Game(["Alice", "Bob"])
        game.players[0].position = 94
        with patch.object(game.dice, "roll", return_value=6):
            game.take_turn()
        result = game.take_turn()
        assert "error" in result

    def test_full_game_produces_winner(self):
        game = Game(["Alice", "Bob"])
        winner = game.play(verbose=False)
        assert winner is not None
        assert winner.position == 100

    def test_board_summary_contains_sections(self):
        game = Game(["Alice", "Bob"])
        summary = game.board_summary()
        assert "Snakes" in summary
        assert "Ladders" in summary
