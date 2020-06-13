import io
import doctest
import glob
import os
import subprocess
import sys

import chess.pgn
from flask import Flask, render_template
#from chess_engine import *

app = Flask(__name__)

DOWNLOADS = os.path.expanduser("~/Downloads")

global CURRENT_LINE
CURRENT_LINE = -1

global REWOUND
REWOUND = False

global FILEPATH

POSITION = "position"

@app.route('/')
def index():
    return render_template("index.html")


#
#
# IO functions
#
#

def get_game_in_downloads():
    """Get the only game in the Downloads folder.
    """
    games = glob.glob(os.path.join(DOWNLOADS, "*.game"))
    assert 1 == len(games)
    return games[0]


def load_macos_game(fp):
    """Loads a game from macOS in .game format."""
    with open(fp) as f:
        contents = f.read(-1)

    start_cue = "<string>"
    end_cue = "</string>"

    start_index = contents.find("<key>Moves</key>")
    start_index = contents.find(start_cue, start_index) + len(start_cue)
    end_index = contents.find(end_cue, start_index)

    moves = contents[start_index:end_index].strip().split("\n")

    return moves


def load_mpgn_game(fp):
    """Loads a game in my version of PGN.
    """


def load_game(fp):
    global MACOS_GAME
    if fp.endswith(".game"):
        MACOS_GAME = True
        return load_macos_game(fp);
    elif fp.endswith(".mpgn"):
        MACOS_GAME = False
        return load_mpgn_game(fp)
    else:
        assert False, "Unknown extension: %s" % fp


#
#
# Functions for PGN games
#
#

"""
def pgn_to_mpgn(moves):
    "Converts a game from pure PGN to my PGN.
    
    >>> pgn = "".join(["1.e4 e5", "2.d4"])
    >>> mpgn = ["1. e4", "1...e5", "2. d4"]
    >>> mpgn == pgn_to_mpgn(pgn)
    True
    "
    
    lines = moves.split("\n")

    mpgn = []
    for line in lines:
        fields = line.split(" ")
        mpgn.append(fields[0] + " " + fields[1])

        if 2 < len(fields):
            mpgn.append(fields[0] + ".." + fields[2])
    return mpgn
"""

def uci_moves_to_state(moves, current_line):
    board = chess.Board()
    san_history = []
    for i in range(1 + current_line):
        move = chess.Move.from_uci(moves[i])
        san_history.append(board.san(move))
        board.push(move)
    return board.fen(), san_history


def san_history_to_html(san_history):
    """Converts a history of moves in Standard Algebraic Notation (SAN) to HTML that
    can be displayed.

    >>> "1. e4 e5<br/>2. Nc3" == san_history_to_html(["e4", "e5", "Nc3"])
    True
    """
    output = []
    move_number = 1

    for i, line in enumerate(san_history):
        white = (0 == i % 2)
        if white:
            if 0 < i:
                output.append("<br/>")
            output.append(str(move_number) + ".")
        else:
            move_number += 1
        output.append(" " + line)

    return "".join(output)


def state():
    """Returns the state of the board from the global variables CURRENT_LINE and FILEPATH.
    """

    moves = load_game(FILEPATH)
    print(CURRENT_LINE)

    if len(moves) <= CURRENT_LINE:
        print("at end of game!")
        return "finished"

    if MACOS_GAME:
        fen, san_history = uci_moves_to_state(moves, CURRENT_LINE)
        print(san_history)
        san_html = san_history_to_html(san_history)
        print(san_html)
        return "\n".join([POSITION, fen, san_html])
    else:
        assert False
    

# TODO: refactor this into a state function, so it works well
# with CURRENT_LINE = 22

def next_move(increment = 1):
    global CURRENT_LINE, GAME_MOVES, MOVE_MAINLINE, REWOUND

    CURRENT_LINE += increment

    line = GAME_MOVES[CURRENT_LINE]

    # Games from macOS have a unique line of play
    if MACOS_GAME:
        action = "move"
        return "\n".join([action, line])


    # Compute the place of this half-move
    dot_index = line.index(".")
    move_number_str = line[:dot_index]
    if not move_number_str.isdigit():
        return "finished\n" + GAME_MOVES[CURRENT_LINE]
    
    move_number = int(move_number_str)
    white = ("." != line[dot_index + 1])

    # Find the pure move and notes
    start_index = dot_index
    notes = ""
    while True:
        start_index += 1
        if line[start_index] not in [".", " "]:
            break
    end_index = line.find(" ", start_index)
    if -1 == end_index:
        pure_move = line[start_index:]
    else:
        pure_move = line[start_index:end_index]
        notes = line[(end_index + 1):]

    move_place = move_number * 2 - white - 1

    print("Current game line = %d, line = %s, move_place = %d " % (CURRENT_LINE, line, move_place))
    
    # Add this move to the game history
    action = "position"
    if len(MOVE_MAINLINE) > move_place and 0 < increment:
        # Rewind from the text (not from "previous" button)
        MOVE_MAINLINE = MOVE_MAINLINE[:move_place]

        if not REWOUND:
            REWOUND = True
            CURRENT_LINE -= 1
            action = "rewind"
    else:
        REWOUND = False

    if not REWOUND:
        if white:
            new_move = str(move_number) + ". " + pure_move
        else:
            new_move = " " + pure_move
        print(new_move)
        
        MOVE_MAINLINE.append(new_move)

    # Compute the board's position from python-chess
    print("PGN = " + " ".join(MOVE_MAINLINE))
    pgn = io.StringIO(" ".join(MOVE_MAINLINE))
    game = chess.pgn.read_game(pgn)
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)  # to update and render the board
    answer = [action, board.fen(), mainline_to_html_pgn(MOVE_MAINLINE)]
    if notes:
        answer.append(notes)
    return "\n".join(answer)
                     

@app.route('/next')
def next():
    global CURRENT_LINE
    CURRENT_LINE += 1
    return state()


@app.route('/previous')
def previous_move():
    global CURRENT_LINE
    CURRENT_LINE -= 1
    return state()


# TODO: add GET parameter for ability to set the line
@app.route("/reset")
def reset(line = -1):
    print("reset!")
    global CURRENT_LINE
    CURRENT_LINE = line
    return state()


@app.route('/test/<string:tester>')
def test_get(tester):
    return tester


if __name__ == '__main__':

    doctests = doctest.testmod()
    assert 0 == doctests.failed, "Some doc-tests failed, exiting..."

    global FILEPATH

    # If an argument was given, use that as the filepath
    if 2 <= len(sys.argv):
        FILEPATH = sys.argv[1]
    else:
        FILEPATH = get_game_in_downloads()

    subprocess.check_output("open -a Safari http://localhost:5000/", shell=True)
    app.run(debug=True)
