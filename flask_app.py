import io
import subprocess
import sys

import chess.pgn
from flask import Flask, render_template
#from chess_engine import *

app = Flask(__name__)

global GAME_LINE
GAME_LINE = -1

global MOVE_MAINLINE
MOVE_MAINLINE = []

MOVE_SPLITTER = " ** "

global REWOUND
REWOUND = False

@app.route('/')
def index():
    return render_template("index.html")


def get_game_in_downloads():
    """Get the only game in the Downloads folder.
    """
    games = glob.glob(os.path.join(DOWNLOADS, "*.game"))
    assert 1 == len(games)
    return games[0]


def load_game(fp):
    """Loads a game from macOS in .game format."""
    with open(fp) as f:
        contents = f.read(-1)

    start_cue = "<string>"
    end_cue = "</string>"

    start_index = contents.find("<key>Moves</key>")
    start_index = contents.find(start_cue, start_index) + len(start_cue)
    end_index = contents.find(end_cue, start_index)

    moves = contents[start_index:end_index].strip().split("\n")

    position = contents.find("<key>Position</key>")
    start_index = contents.find(start_cue, start_index) + len(start_cue)
    end_index = contents.find(end_cue, start_index)
    position = contents[start_index:end_index].strip()
    
    return moves, position


def load_pgn_pure(fp):
    """Loads a game in pure Portable Game Notation."""
    with open(fp) as f:
        contents = f.read(-1)

    lines = contents.split("\n")

    moves = []
    for line in lines:
        fields = line.split(" ")
        moves.append(fields[0] + " " + fields[1])

        if 2 < len(fields):
            moves.append(fields[0] + ".." + fields[2])

    return moves


def load_mpgn(fp):
    """Loads a game with multiple development lines in my adaptation of Portable Game Notation."""
    with open(fp) as f:
        contents = f.read(-1)

    return contents.split("\n")


def mainline_to_html_pgn(mainline):
    output = []
    for i, line in enumerate(mainline):
        if 0 < i and 0 == i % 2:
            output.append("<br/>")
        else:
            output.append(" ")
        output.append(line)

    return "".join(output)

def next_move():
    global GAME_LINE, GAME_MOVES, MOVE_MAINLINE, REWOUND

    GAME_LINE += 1
    line = GAME_MOVES[GAME_LINE]

    if 0 > GAME_LINE:
        print("already at beginning!")
        return None

    if len(GAME_MOVES) <= GAME_LINE:
        print("at end of game!")
        return "finished"

    # Compute the place of this half-move
    dot_index = line.index(".")
    move_number_str = line[:dot_index]
    if not move_number_str.isdigit():
        return "finished\n" + GAME_MOVES[GAME_LINE]
    
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

    print(notes)

    move_place = move_number * 2 - white - 1

    # Add this move to the game history
    action = "move"
    if len(MOVE_MAINLINE) > move_place:
        # Rewind
        MOVE_MAINLINE = MOVE_MAINLINE[:move_place]

        if not REWOUND:
            REWOUND = True
            GAME_LINE -= 1
            action = "rewind"
    else:
        REWOUND = False

    if not REWOUND:
        if white:
            new_move = str(move_number) + ". " + pure_move
        else:
            new_move = " " + pure_move
        
        MOVE_MAINLINE.append(new_move)

    # Compute the board's position from python-chess
    print(" ".join(MOVE_MAINLINE))
    pgn = io.StringIO(" ".join(MOVE_MAINLINE))
    game = chess.pgn.read_game(pgn)
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)  # to update and render the board
    answer = [action, board.fen(), mainline_to_html_pgn(MOVE_MAINLINE)]
    if notes:
        answer.append(notes)
    return "\n".join(answer)
                     

@app.route('/next/')
def next():
    return next_move()

"""
@app.route('/previous/')
def previous_move():
    return next_move(-1)
"""

@app.route('/test/<string:tester>')
def test_get(tester):
    return tester


if __name__ == '__main__':

    global GAME_MOVES

    # If an argument was given, use that as the filename
    if 2 <= len(sys.argv):
        fp = sys.argv[1]
        GAME_MOVES = load_mpgn(fp)
    else:
        GAME_MOVES = load_moves_from_downloads()

    print(GAME_MOVES)

    subprocess.check_output("open -a Safari http://localhost:5000/", shell=True)
    app.run(debug=True)
