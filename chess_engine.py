import chess
import random



def random_response(fen):
    board = chess.Board()
    board.set_fen(fen)
    response = random.choice(list(board.legal_moves))
    return str(response)

if __name__=="__main__":
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    print(type(random_response(fen)))