# -*- coding: utf-8 -*-

import gym
from gym import spaces
import numpy as np
from collections import Counter

WHITE = 1
BLACK = -1
EMPTY = 0

class ASCII:
  WHITE = '⚪'
  BLACK = '⚫'
  EMPTY = '🟩'

  @classmethod
  def getsymbol(self, value):
    return self.WHITE if value == WHITE else self.BLACK if value == BLACK else self.EMPTY

# Increments to use depending on the direction to search the grid
direction2row = {1:-1, 2:-1, 3:0, 4:1, 5:1, 6:1, 7:0, 8:-1}
direction2col = {1:0, 2:1, 3:1, 4:1, 5:0, 6:-1, 7:-1, 8:-1}

class OthelloEnv(gym.Env):
    def __init__(self, n=8):
        
        self.done = False
        self.turn_passed = False # True when a player passes turn because no valid moves
        self.observation_space = spaces.Box(low = -1, high = 1, shape = (n, n), dtype = int)
        self.action_space = spaces.Discrete(n*n)
        self.n = n
        
    def reset(self):
        
        self.board = np.zeros([self.n, self.n])
        
        self.board[self.n//2-1, self.n//2] = self.board[self.n//2, self.n//2-1] = BLACK
        self.board[self.n//2-1, self.n//2-1] = self.board[self.n//2, self.n//2] = WHITE
        
        self.turn = WHITE
        self.valid_moves = self.get_valid_moves(self.turn)
        self.done = False
        
        return self.board
        
    def step(self, action):
        
        # Update the environment state based on the action chosen
        assert action in self.valid_moves, "Invalid move"
        self.board[action] = self.turn
        self.flip(action)
        self.valid_moves = self.get_valid_moves(-self.turn)
        
        # Calculate the reward for the new state
        score = self.score()
        self.done = (score is not None) and self.turn_passed
        self.turn_passed = score is not None
        self.reward = score if self.done else 0
        
        self.turn *= -1
        
        if self.turn_passed:
            self.turn *= -1
            self.valid_moves = self.get_valid_moves(self.turn)
            self.done = len(self.valid_moves) == 0
        
        return self.board, self.reward, self.done, {'turn': self.turn}
    
    def score(self):
        
        white, black, empty = self.do_count()
        
        if empty == 0:
            self.turn_passed = True
            return (white - black) / self.n**2

        if white == 0 or black == 0 or len(self.valid_moves) == 0:
            return (white - black) / self.n**2

        return None
    
    def get_valid_moves(self, color):
        
        places = []
        mat = np.where(self.board == color)
        positions = [(x,y) for x,y in zip(mat[0],mat[1])]
        for position in positions:
            for direction in range(1,9):
                p = self.get_direction_valid_moves(position, direction, color)
                if not p is None:
                    places.append(p)
                    
        places = list(set(places))
        
        return places
    
    def get_direction_valid_moves(self, position, direction, color):
        
        row_inc, col_inc = direction2row[direction], direction2col[direction]
        x, y = position
        k = 1
        flat = []
        while (x+row_inc*k>=0) and (y+col_inc*k>=0) and (x+row_inc*k<self.n) and (y+col_inc*k<self.n):
            flat.append((self.board[x+row_inc*k, y+col_inc*k], (x+row_inc*k, y+col_inc*k)))
            k += 1
        
        for i, (x, ind) in enumerate(flat):
            if x == EMPTY:
                if i == 0:
                    return
                elif flat[i-1][0] == -color:
                    return ind
                else:
                    return
            elif x == -color:
                continue
            else:
                return
        
        
    def flip(self, position):
        
        for direction in range(1,9):
            self.direction_flip(position, direction)
            
    def direction_flip(self, position, direction):
        
        row_inc, col_inc = direction2row[direction], direction2col[direction]
        x, y = position
        k = 1
        flat = []
        while (x+row_inc*k>=0) and (y+col_inc*k>=0) and (x+row_inc*k<self.n) and (y+col_inc*k<self.n):
            flat.append((self.board[x+row_inc*k, y+col_inc*k], (x+row_inc*k, y+col_inc*k)))
            k += 1
        
        to_flip = []
        for i, (x, ind) in enumerate(flat):
            if x == self.turn:
                break
            elif x == -self.turn:
                to_flip.append(ind)
                if i == len(flat)-1:
                    return
            else:
                return
        
        for ind in to_flip:
            self.board[ind]*=-1
        
    def do_count(self):
        
        flat = self.board.reshape(-1)
        counts = Counter(flat)
        white, black, empty = counts[WHITE], counts[BLACK], counts[EMPTY]
        
        return white, black, empty
    
    def render(self):
        
        return '\n'.join([''.join([ASCII.getsymbol(value) for value in row]) for row in self.board])
      
    def coord2ind(self, coord):
        x, y = coord
        return x * self.n + y

    def ind2coord(self, ind):
        return (ind // self.n, ind % self.n)
