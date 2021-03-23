# -*- coding: utf-8 -*-

from environment import OthelloEnv
import torch
from torch import nn
import torch.nn.functional as F
import numpy as np
from deep_qlearning import OthelloGame, DQNAgent, RandomAgent, state_numpy_to_tensor
import time
import random

env = OthelloEnv(n=8)
game = OthelloGame(DQNAgent(env, 1), DQNAgent(env, -1))
game.get_agent(1).q_model.load_state_dict(torch.load("../../Downloads/dqn_state_dict.pt", 'cpu'))
game.sync(1, -1)
np.random.seed(0)
torch.manual_seed(0)
# random.seed(0)


def score_multi_episode(env, game, color, depth=4, device='cpu',
                        num_episodes=100, epsilon=.0):
    """Evaluate the performance of the model over multiple games."""
    trained_agent = game.get_agent(color)
    eval_agent = RandomAgent(-color)

    num_success = 0
    num_cons_success = [0]
    results = []
    score = .0

    for i in range(num_episodes):

        print(i)
        state = env.reset()
        state = state_numpy_to_tensor(state)
        done = False
        mu = 0.0
        mu_incre = 0.0
        # No use of minimax
        while not done:
            # print(env.render())
            if env.turn == color:
                if np.random.rand() < mu:
                    action, value = trained_agent.draw_action_minimax(
                        env, state, depth)
                    # print("minimax...")
                else:
                    action, value = trained_agent.draw_action(
                        env, state, epsilon)
            else:
                action, value = eval_agent.draw_action(env, state, epsilon)
            if action is not None:
                state, reward, done, info = env.step(action)
                state = state_numpy_to_tensor(state)
            else:
                done = env.score() is not None and env.turn_passed
                env.turn *= -1
            mu += mu_incre
            # alpha += alpha_incre

        # print(env.render())
        if reward * color > 0:
            num_success += 1
            num_cons_success[-1] += 1
            score += 1.
        else:
            num_cons_success.append(0)
            if env.score() != 0:
                score -= 1.

        results.append(reward)
    return num_success, max(num_cons_success), score, results

st = time.time()
s, _, _, _ = score_multi_episode(env, game, 1)
print(time.time() - st)
print(s)
