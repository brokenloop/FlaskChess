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

    This is for use for chess games from macOS, because those from MPGN have input like
    ['0.0.e4', 'e5', '1.0.Bc4', 'Bc5', '2.0.Qh5', 'g6']

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
    last_notes = ""
    for source_line in range(1 + current_line):
        line = mpgn[source_line]
        half_move = parse_mpgn_line(line)[HALF_MOVE_KEY]
        
        if len(mainline) <= half_move:
            last_branch_length += 1
        else:
            mainline = mainline[:half_move]
            last_branch_length = 1
        mainline.append(line)
    return mainline, last_branch_length


def mpgn_moves_to_state(mpgn_moves, current_line):

    # Find mainline
    mainline, last_branch_length = mpgn_to_mainline(mpgn_moves, current_line)

    # TODO: add rewinding with length of last_branch_length

    # Iterate on mainline to produce a game in SAN
    last_notes = ""
    finished = False
    san_history = []
    for i in range(len(mainline)):
        details = parse_mpgn_line(mainline[i])
        half_move = details[HALF_MOVE_KEY]
        if FINISHED == half_move:
            finished = True
        else:
            move = ""
            if 0 == half_move % 2:
                move += str(half_move / 2) + "."
            move += details[PURE_MOVE_KEY]
            san_history.append(move)
        notes = details[NOTES_KEY]
        if "" != notes:
            last_notes = notes

    pgn = io.StringIO(" " .join(san_history))
    game = chess.pgn.read_game(pgn)
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    
    return board.fen(), san_history, last_notes


def state():
    """Returns the state of the board from the global variables CURRENT_LINE and FILEPATH.
    """

    moves = load_game(FILEPATH)

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
        fen, san_history, last_notes = mpgn_moves_to_state(moves, CURRENT_LINE)
        san_html = san_history_to_html(san_history)
        print(san_history)
        print(san_html)
        return "\n".join([POSITION, fen, san_html, last_notes])
    

# TODO: refactor this into a state function, so it works well
# with CURRENT_LINE = 22

"""
def next_move(increment = 1):
    global CURRENT_LINE, GAME_MOVES, MOVE_MAINLINE, REWOUND

    CURRENT_LINE += increment

    line = GAME_MOVES[CURRENT_LINE]

    # Games from macOS have a unique line of play
    if MACOS_GAME:
        action = "move"
        return "\n".join([action, line])



    # Find the pure move and notes
    start_index = dot_index

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
"""                     

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

    single_line = ["1. e4", "1...e5", "2. Nc3"]
    double_line = single_line + ["1...c5"]
    result, branch_length = mpgn_to_mainline(double_line, 3)
    print(result)
    print(branch_length)

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
