import chess
import random

class Engine:

    def __init__(self, fen):
        self.board = chess.Board()
        self.piece_values = {
            # pawn
            1:10,
            # bishop
            2:30,
            # knight
            3:30,
            # rook
            4:50,
            # queen
            5:90,
            # king
            6:999
        }
        self.board.set_fen(fen)
        self.leaves_reached = 0


    def random_response(self):
        response = random.choice(list(self.board.legal_moves))
        return str(response)


    def material_eval(self):
        score = 0
        # iterate through the pieces
        for i in range(1, 7):
            score += len(self.board.pieces(i, chess.WHITE)) * self.piece_values[i]
            score -= len(self.board.pieces(i, chess.BLACK)) * self.piece_values[i]

        return score


    def minimax(self, depth, move, maximiser):
        if depth == 0:
            return move, self.material_eval()

        if maximiser:
            best_move = None
            best_score = -9999

            moves = list(self.board.legal_moves)

            for move in moves:
                self.leaves_reached += 1
                self.board.push(move)
                new_move, new_score = self.minimax(depth - 1, move, False)
                if new_score > best_score:
                    best_score, best_move = new_score, move
                self.board.pop()

            return best_move, best_score

        if not maximiser:
            best_move = None
            best_score = 9999

            moves = list(self.board.legal_moves)

            for move in moves:
                self.leaves_reached += 1
                self.board.push(move)
                new_move, new_score = self.minimax(depth - 1, move, True)
                if new_score < best_score:
                    best_score, best_move = new_score, move
                self.board.pop()

            return best_move, best_score


    def alpha_beta(self, depth, move, alpha, beta, maximiser):
        if depth == 0:
            return move, self.material_eval()

        if maximiser:
            best_move = None

            moves = list(self.board.legal_moves)

            for move in moves:
                self.leaves_reached += 1
                self.board.push(move)
                new_move, new_score = self.alpha_beta(depth - 1, move, alpha, beta, False)
                if new_score > alpha:
                    alpha, best_move = new_score, move
                self.board.pop()
                if alpha > beta:
                    break

            return best_move, alpha

        if not maximiser:
            best_move = None

            moves = list(self.board.legal_moves)

            for move in moves:
                self.leaves_reached += 1
                self.board.push(move)
                new_move, new_score = self.alpha_beta(depth - 1, move, alpha, beta, True)
                if new_score < beta:
                    beta, best_move = new_score, move
                self.board.pop()
                if alpha > beta:
                    break

            return best_move, beta


    def calculate(self, depth):
        # This shows up true for white & false for black
        maximiser = self.board.turn

        best_move, best_score = self.minimax(depth, None, maximiser)
        return str(best_move)


    def calculate_ab(self, depth):
        maximiser = self.board.turn

        best_move, best_score = self.alpha_beta(depth, None, -9999, 9999, maximiser)
        return str(best_move)


    def total_leaves(self):
        leaves = self.leaves_reached
        self.leaves_reached = 0
        return leaves


if __name__=="__main__":
    fen = "rnbqkbnr/ppppp1pp/8/5P2/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"

    newengine = Engine(fen)

    # print(newengine.board)

    # print(type(newengine.material_eval()))
    print(newengine.calculate_ab(2))
    print(newengine.total_leaves())
    print(newengine.calculate(2))
    print(newengine.total_leaves())
    # print(newengine.board)