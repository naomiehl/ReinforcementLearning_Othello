# -*- coding: utf-8 -*-
"""deep-Qlearning.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1d5WIbMaHFeSy3R4HHceV4j8xScpXnfXU
"""

from environment import OthelloEnv
import torch
from torch import nn
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from collections import namedtuple
from itertools import count
import random
from copy import deepcopy
from torch.utils.tensorboard import SummaryWriter

writer = SummaryWriter(log_dir='runs_2')
env = OthelloEnv(n=8)
env.reset()
device = torch.device(
    'cuda') if torch.cuda.is_available() else torch.device('cpu')
EPS_START = 0.9
EPS_END = 0.1
EPS_DECAY = 1e7
BATCH_SIZE = 64
NUM_EPISODES_EVAL = 100
GAMMA = 1.0
LR = 0.1
N_CHANNELS = 3
MINIMAX_DEPTH = 3
PATH = "dqn_state_dict.pt"
NB_EPISODES_PER_AGENT = 1
TARGET_UPDATE = 10000
PRINT_STEP = 1000
SELF_PLAY = True


class DQN(nn.Module):
    """Deep Q neural network."""

    def __init__(self, n=8, n_channels=N_CHANNELS):
        """Initilize."""
        super(DQN, self).__init__()
        self.n_channels = n_channels
        self.convo = nn.Sequential(
            nn.Conv2d(n_channels, 64, 3, stride=1, padding=1),
            nn.LeakyReLU(),
            # nn.BatchNorm2d(4),
            # nn.Conv2d(64, 128, 3, stride=1, padding=1),
            # nn.LeakyReLU(),
            # # nn.BatchNorm2d(8),
            # nn.Conv2d(128, 128, 3, stride=1, padding=1),
            # nn.LeakyReLU(),
            # nn.BatchNorm2d(16),
        )

        self.head = nn.Sequential(
            nn.Linear(n*n*64, n*n*16),
            nn.LeakyReLU(),
            # nn.BatchNorm1d(n*n*2),
            nn.Linear(n*n*16, n*n)
        )

    def forward(self, states):
        """Forward."""
        states = nn.functional.one_hot(states + 1, num_classes=self.n_channels)
        states = states.to(torch.float).transpose(2, -1).squeeze(1)

        x = self.convo(states)
        # x = states.to(torch.float)

        x = x.view(x.shape[0], -1)
        x = self.head(x)

        return x


class DQNAgent:
    """An agent with DQN policy."""

    def __init__(self, env, color, device=device, n_channels=3, lr=LR):
        """Initialize."""
        self.steps_done = 0
        self.q_model = DQN(env.n, n_channels).to(device)
        self.target_model = DQN(env.n, n_channels).to(device)
        self.update_target_model()
        self.target_model.eval()
        self.optimizer = torch.optim.RMSprop(self.q_model.parameters(), lr=lr)
        self.buffer = ReplayBuffer(100000)
        self.color = color

    def draw_action(self, env, s, epsilon=None):
        """Draw an action based on state s and DQN."""
        s *= self.color
        if epsilon is None:
            epsilon = EPS_START + (EPS_START - EPS_END) / \
                EPS_DECAY * self.steps_done
            epsilon = max(epsilon, EPS_END)

        with torch.no_grad():
            values = self.q_model(s).reshape(-1)
        valid_moves = env.get_valid_moves(self.color)
        if len(valid_moves) > 0:
            if np.random.rand() <= 1 - epsilon:
                valid_moves_ind = [env.coord2ind(p) for p in valid_moves]
                probs = values[valid_moves_ind]
                probs = F.softmax(probs, dim=0)
                action = np.random.choice(
                    valid_moves_ind, p=probs.cpu().numpy())
                return env.ind2coord(action), values[action]
            else:
                action = valid_moves[np.random.randint(0, len(valid_moves))]
                return action, values[env.coord2ind(action)]

        else:
            print(env.render())
            return None, 0

    def draw_action_minimax(self, env, s, depth=MINIMAX_DEPTH, alpha=np.NINF, beta=np.PINF):
        """Draw an action by combining DQN with minimax algorithm."""

        maximizer = env.turn * self.color  # 1 if True, -1 if False

        s *= env.turn
        with torch.no_grad():
            values = self.q_model(s).reshape(-1).cpu().numpy()
        valid_moves = env.get_valid_moves(env.turn)
        if len(valid_moves) == 0:
            return None, 0
        valid_moves = np.array([env.coord2ind(m) for m in valid_moves])

        # print('depth', depth)
        # print('maximizer: ', maximizer)

        if depth == 1:
            best_action = valid_moves[np.argsort(values[valid_moves])][-1]
            best_value = values[best_action]
            best_action = env.ind2coord(best_action)
            
            # actions = valid_moves[np.argsort(values[valid_moves])][-2:]
            # values = values[actions]
            # print(values)
            # print(actions)

            return best_action, best_value * maximizer

        # Select 2 most possible actions
        actions = valid_moves[np.argsort(values[valid_moves])][-2:]
        values = values[actions]
        # print(values)
        # print(actions)

        best_action = None
        if maximizer > 0:
            best_value = np.NINF
        else:
            best_value = np.PINF

        for v, a in zip(values, actions):
            env_ = deepcopy(env)
            state, reward, done, info = env_.step(env.ind2coord(a))
            s = state_numpy_to_tensor(state)
            _, value = self.draw_action_minimax(env_, s,
                                                depth=depth-1,
                                                alpha=alpha, beta=beta)
            if reward * self.color > 0:
                value = np.PINF
            elif reward * self.color < 0:
                value = np.NINF

            if maximizer > 0 and best_value <= value:
                best_value = value
                best_action = a
                alpha = max(alpha, best_value)

                if beta <= alpha:
                    break
            if maximizer < 0 and best_value >= value:
                best_value = value
                best_action = a
                beta = min(beta, best_value)

                if beta <= alpha:
                    break

        # print('Best_action ', best_action)

        return env.ind2coord(best_action), best_value

    def update_target_model(self):
        """Copy state_dict of q_model to target_model."""
        if self.steps_done % TARGET_UPDATE == 0:
            self.target_model.load_state_dict(self.q_model.state_dict())


class RandomAgent:
    """An agent with random policy."""

    def __init__(self, color):
        """Initialize."""
        self.color = color

    def draw_action(self, env, s, epsilon):
        """Draw an action randomly."""
        valid_moves = env.get_valid_moves(self.color)
        if len(valid_moves) > 0:
            action = valid_moves[np.random.randint(0, len(valid_moves))]
            return action, 1. / len(valid_moves)
        else:
            return None, 0

    def update_target_model(self):
        """Undefined."""
        pass


class OthelloGame:
    """A pool of two Othello agents competing in a game."""

    def __init__(self, agent_white, agent_black):
        """Initialize."""
        self.white = agent_white
        self.black = agent_black

    def get_agent(self, color):
        """Get an agent of color."""
        if color == 1:
            return self.white
        else:
            return self.black

    def sync(self, color_optimized, color_update):
        """Copy model state of agent color_optimized to agent color_update."""
        self.get_agent(color_update).q_model.load_state_dict(
            self.get_agent(color_optimized).q_model.state_dict())


Transition = namedtuple('Transition',
                        ('state', 'action', 'next_state', 'reward'))


class ReplayBuffer(object):
    """A replay buffer to store transitions."""

    def __init__(self, capacity):
        """Initialize."""
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, *args):
        """Push a transition."""
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = Transition(*args)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        """Sample a batch of transition from the replay buffer."""
        return random.sample(self.memory, batch_size)

    def __len__(self):
        """Get length of the replay buffer."""
        return len(self.memory)


def optimize_model(agent, batch_size=BATCH_SIZE, device=device, gamma=GAMMA):
    """Perform a step of optimizing the model associated with the agent."""
    agent.q_model.train()

    if len(agent.buffer) < batch_size:
        agent.q_model.eval()
        return

    transitions = agent.buffer.sample(batch_size)
    batch = Transition(*zip(*transitions))

    non_final_mask = torch.tensor(tuple(map(lambda s: s is not None,
                                            batch.next_state)),
                                  device=device,
                                  dtype=torch.bool)
    non_final_next_states = torch.cat(
        [s for s in batch.next_state if s is not None])

    reward_batch = torch.tensor(batch.reward, device=device)
    state_batch = torch.cat(batch.state)
    action_batch = torch.cat(batch.action)

    state_action_values = agent.q_model(state_batch).gather(1, action_batch)

    next_state_values = torch.zeros(batch_size, device=device)
    a_max_of_next_state = agent.q_model(non_final_next_states).argmax(
        1, keepdim=True)

    next_state_values[non_final_mask] = torch.gather(
        agent.target_model(non_final_next_states).detach(),
        1,
        a_max_of_next_state
    ).reshape(-1)

    expected_state_action_values = next_state_values * gamma + reward_batch

    loss = F.smooth_l1_loss(state_action_values,
                            expected_state_action_values.unsqueeze(1))

    agent.optimizer.zero_grad()
    loss.backward()
    for param in agent.q_model.parameters():
        param.grad.data.clamp_(-1, 1)
    agent.optimizer.step()
    agent.steps_done += 1
    agent.update_target_model()
    agent.q_model.eval()


def state_numpy_to_tensor(state, device=device):
    """Convert a state from numpy array to torch.Tensor."""
    state = torch.from_numpy(state.astype(np.int64)).unsqueeze(0).unsqueeze(0)
    return state.to(device)


def train_one_episode(env, game, color, device=device, batch_size=BATCH_SIZE, gamma=GAMMA, epsilon=None):
    """Perform the training on one episode."""
    game.get_agent(color).q_model.eval()
    if SELF_PLAY:
        game.get_agent(-color).q_model.eval()

    state = env.reset()
    state = state_numpy_to_tensor(state)
    done = False

    while not done:
        # Player plays
        this_turn = env.turn
        action, value = game.get_agent(
            env.turn).draw_action(env, state, epsilon)
        if action is not None:
            opp_state, reward, done, info = env.step(action)
            action = torch.tensor(
                [[env.coord2ind(action)]], device=device, dtype=torch.int64)
            opp_state = state_numpy_to_tensor(opp_state)

            if reward * color > 0:
                reward = 1.
            elif reward * color < 0:
                reward = -1.
        else:
            raise ValueError("No valid move!")

        if this_turn != color:
            # If this is not the turn of player color, then skip to next turn
            continue
        if this_turn == env.turn or done:
            # The opponent skipped his turn or the match ended
            new_state = opp_state
        else:
            # Opponent plays
            while env.turn != color and not done:
                opp_action, _ = game.get_agent(
                    env.turn).draw_action(env, opp_state, epsilon)
                if opp_action is not None:
                    new_state, reward, done, info = env.step(opp_action)
                    new_state = state_numpy_to_tensor(new_state)

                    if reward * color > 0:
                        reward = 1.
                    elif reward * color < 0:
                        reward = -1.
                else:
                    raise ValueError("No valid move!")

        reward = torch.tensor([reward], device=device, dtype=torch.float)
        # Push the transition into player color's replay buffer
        game.get_agent(color).buffer.push(
            state * color, action, new_state * color, reward)

        optimize_model(game.get_agent(color), batch_size, device, gamma)

        # Next turn
        state = new_state


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

        # print(i)
        state = env.reset()
        state = state_numpy_to_tensor(state)
        done = False
        mu = 1.0
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


if __name__ == "__main__":
    np.random.seed(0)
    torch.manual_seed(0)
    random.seed(0)

    if SELF_PLAY:
        game = OthelloGame(DQNAgent(env, 1, lr=LR), DQNAgent(env, -1, lr=LR))
        game.sync(1, -1)
    else:
        game = OthelloGame(DQNAgent(env, 1, lr=LR), RandomAgent(-1))

    color = 1
    best_score_cons = 0.0  # Best score over 5 consecutive evaluations
    num_cons_evals = 0
    best_score = 0.0  # Best score overall

    for i in tqdm(range(200001)):
        train_one_episode(env, game, color)

        # if i % 100 == 0:
        #     print(env.render())
        #     print(env.score())

        if SELF_PLAY and i % NB_EPISODES_PER_AGENT == 0:
            game.sync(color, -color)  # Update model for the other player
            color *= -1

        if i % PRINT_STEP == 0:
            num_cons_evals += 1

            print("Scoring...")
            num_success_white, _, _, _ = score_multi_episode(env, game, 1)
            print("White ... Episode: {}, Number of wins: {}".format(
                i, num_success_white))
            if SELF_PLAY:
                num_success_black, _, _, _ = score_multi_episode(env, game, -1)
                print("Black ... Episode: {}, Number of wins: {}".format(
                    i, num_success_black))
                score = (num_success_white + num_success_black) * 0.5
            else:
                score = num_success_white

            if score >= best_score:
                best_score = score
                torch.save(game.get_agent(color).q_model.state_dict(), PATH)
                print("Model saved")

            best_score_cons = max(score, best_score_cons)
            if num_cons_evals % 5 == 0:
                writer.add_scalar('Score', best_score_cons, i)
                best_score_cons = 0.0
    writer.close()
