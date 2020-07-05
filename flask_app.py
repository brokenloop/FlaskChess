import io
import doctest
import glob
import os
import re
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

OPENINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openings")

POSITION = "position"
REWIND = "rewind"

NOTES_KEY = "notes"
HALF_MOVE_KEY = "half-move"
PURE_MOVE_KEY = "move"
FINISHED = "finished"

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


def get_openings(stub):
    """Get the opening that matches this stub.
    """
    games = [os.path.join(OPENINGS, f) for f in os.listdir(OPENINGS) if f.lower().startswith(stub.lower())]
    return games


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
    with open(fp) as f:
        contents = f.read(-1)

    # split into lines and return non-empty ones
    return [l for l in contents.split("\n") if l]


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

    This is for use for chess games from macOS, because those from MPGN already have move numbers.

    >>> "1.e4 e5<br/>2.Nc3" == san_history_to_html(["e4", "e5", "Nc3"])
    True
    >>> "1.e4 e5<br/>2.Nc3" == san_history_to_html(["1.e4", "e5", "2.Nc3"])
    True
    """
    output = []
    move_number = 1

    for i, line in enumerate(san_history):
        white = (0 == i % 2)
        if white:
            if 0 < i:
                output.append("<br/>")
            prefix = str(move_number) + "."
            if not line.startswith(prefix):
                output.append(prefix)
        else:
            output.append(" ")
            move_number += 1
        output.append("" + line)

    return "".join(output)


def parse_mpgn_line(mpgn_line):
    """Converts my notation of game to the corresponding details: half-move, pure
    move, and notes.
    
    >>> res = parse_mpgn_line("1. e4")
    >>> 0 == res[HALF_MOVE_KEY]
    True
    >>> "e4" == res[PURE_MOVE_KEY]
    True
    >>> res = parse_mpgn_line("1...e6 French Defence")
    >>> 1 == res[HALF_MOVE_KEY]
    True
    >>> "French Defence" == res[NOTES_KEY]
    True
    >>> res = parse_mpgn_line("2...c5")
    >>> 3 == res[HALF_MOVE_KEY]
    True
    >>> FINISHED == parse_mpgn_line("final comments")[HALF_MOVE_KEY]
    True

    """

    res = dict()

    # Maybe I should upgrade to regular expressions?
    if not mpgn_line[0].isdigit():
        res[NOTES_KEY] = mpgn_line
        res[HALF_MOVE_KEY] = FINISHED
        return res
    
    dot_index = mpgn_line.index(".")
    move_number_str = mpgn_line[:dot_index]
    
    move_number = int(move_number_str)
    white = ("." != mpgn_line[dot_index + 1])

    res[HALF_MOVE_KEY] = move_number * 2 - white - 1

    notes = ""
    start_index = dot_index
    while True:
        start_index += 1
        if mpgn_line[start_index] not in [".", " "]:
            break
    end_index = mpgn_line.find(" ", start_index)
    if -1 == end_index:
        pure_move = mpgn_line[start_index:]
    else:
        pure_move = mpgn_line[start_index:end_index]
        notes = mpgn_line[(end_index + 1):]
    
    res[NOTES_KEY] = notes
    res[PURE_MOVE_KEY] = pure_move

    return res    


def mpgn_to_mainline(mpgn, current_line):
    """Finds the game line that leads to the current line.

    >>> single_line = ["1. e4", "1...e5", "2. Nc3"]
    >>> result, branch_length = mpgn_to_mainline(single_line, 2)
    >>> result == single_line
    True
    >>> 3 == branch_length
    True
    >>> double_line = single_line + ["1...c5"]
    >>> result, branch_length = mpgn_to_mainline(double_line, 3)
    >>> result == ["1. e4", "1...c5"]
    True
    >>> 1 == branch_length
    True
    """
    mainline = []
    last_branch_length = 0

    # If the game went over, truncate the line
    if current_line >= len(mpgn):
        current_line = len(mpgn) - 1
        global CURRENT_LINE
        CURRENT_LINE = current_line
        
    for source_line in range(1 + current_line):
        line = mpgn[source_line]
        half_move = parse_mpgn_line(line)[HALF_MOVE_KEY]

        if FINISHED == half_move:
            pass
        elif len(mainline) <= half_move:
            last_branch_length += 1
        else:
            mainline = mainline[:half_move]
            last_branch_length = 1
        mainline.append(line)
    return mainline, last_branch_length


def mpgn_moves_to_state(mpgn_moves):

    global CURRENT_LINE, REWOUND
    
    # Find mainline
    mainline, last_branch_length = mpgn_to_mainline(mpgn_moves, CURRENT_LINE)

    if 0 < CURRENT_LINE and 1 == last_branch_length:
        # This is a rewind. Have we already shown the rewind?
        if REWOUND:
            # reset for next branch
            REWOUND = False
        else:
            REWOUND = True
            CURRENT_LINE -= 1
            mainline = mainline[:-1]

    # Iterate on mainline to produce a game in SAN
    last_notes = ""
    finished = False
    san_history = []
    for i in range(len(mainline)):
        details = parse_mpgn_line(mainline[i])
        half_move = details[HALF_MOVE_KEY]
        if not FINISHED == half_move:
            if 0 == half_move % 2:
                move = str(1 + half_move // 2) + "."
            else:
                move = " "
            move += details[PURE_MOVE_KEY]
            san_history.append(move)
        notes = details[NOTES_KEY]
        if "" != notes:
            last_notes = notes

    if 0 <= CURRENT_LINE and bool(san_history):
        pgn = io.StringIO("".join(san_history))
        game = chess.pgn.read_game(pgn)
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
    else:
        board = chess.Board()
            
    return board.fen(), san_history, last_notes


def state():
    """Returns the state of the board from the global variables CURRENT_LINE and FILEPATH.
    """

    moves = load_game(FILEPATH)

    if MACOS_GAME:
        fen, san_history = uci_moves_to_state(moves, CURRENT_LINE)
        last_notes = ""
    else:
        fen, san_history, last_notes = mpgn_moves_to_state(moves)
    
    san_html = san_history_to_html(san_history)
    action = REWIND if REWOUND else POSITION 
    return "\n".join([action, fen, san_html, last_notes])
    

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


    if 2 > len(sys.argv):
        FILEPATH = get_game_in_downloads()
    else:
        # If an argument was given, use that as the filepath, possibly with completion
        FILEPATH = sys.argv[1]
        if not os.path.exists(FILEPATH):
            games = get_openings(FILEPATH)
            print("Games = " + str(games))
            assert 1 == len(games), "Ambiguous filepath: %s, games matched = %d" % (sys.argv[1], len(games))
            FILEPATH = games[0]

    subprocess.check_output("open -a Safari http://localhost:5000/", shell=True)
    app.run(debug=True)
