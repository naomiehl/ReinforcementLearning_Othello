class MinimaxAgent:    
  """
    Minimax agent iterate though all the valid moves to find the best (highest value) move.
    For each, it needs to evaluate all the possible following moves by the opponent
    who tries to choose the best move which is the worst move for this agent.
    This traversing of possible move chains will be continued until we reach the max depth
    or there is no more move for both agents.
    """
    def __init__(self, depth = 5):
        self.depth = depth
    
    def minimax(self, board, color, depth):
        if depth == 0:
            return (self.score(), None)
        
        valid_moves = env.get_valid_moves(self.color)
        
            return (self.score(), None)
        
        best_score = -100000
        best_move = None
        
        if len(valid_moves) > 0:
            new_board = deepcopy(board)
            new_board.step(action)

            try_tuple = self.minimax(new_board, -color, depth-1)
            try_score = -try_tuple[0]

            if try_score > best_score:
                best_score = try_score
                best_move = move

            return (best_score, best_move)
    
        else:
            
            return None, 0
