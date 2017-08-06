#!/usr/bin/env python
import sys
sys.path.append('/home/scotty/qzq/git/CarSim/intersection_project')
import logging
import numpy as np
import tensorflow as tf
import json
from network.ActorNetwork import ActorNetwork
from network.CriticNetwork import CriticNetwork
from network.ReplayBuffer import ReplayBuffer
from utilities.toolfunc import ToolFunc
from inter_sim import InterSim
from keras import backend as keras
import time

__author__ = 'qzq'


LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

if len(sys.argv) > 1:
    level_name = sys.argv[1]
    level = LEVELS.get(level_name, logging.NOTSET)
    logging.basicConfig(level=level)


class ReinAcc(object):
    tools = ToolFunc()

    Tau = 1. / 30
    gamma = 0.99
    epsilon = 1.

    buffer_size = 100000
    batch_size = 100
    tau = 0.0001            # Target Network HyperParameters
    LRA = 0.001             # Learning rate for Actor
    LRC = 0.001             # Learning rate for Critic

    explore_iter = 100000
    episode_count = 20000
    max_steps = 2000

    action_dim = 1          # Steering/Acceleration/Brake
    action_size = 1

    # Tensorflow GPU optimization
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    tf_sess = tf.Session(config=config)
    keras.set_session(tf_sess)

    def __init__(self):
        self.sim = InterSim()
        self.state_t = None
        self.total_reward = 0
        self.loss = 0.
        self.if_pass = False
        self.if_done = False

        self.actor_network = ActorNetwork(self.tf_sess, 9, self.action_dim, 10, self.tau, self.LRA)
        self.critic_network = CriticNetwork(self.tf_sess, 9, self.action_dim, 10, self.tau, self.LRC)
        self.buffer = ReplayBuffer()

        self.batch = None
        self.batch_state = None
        self.batch_action = None
        self.batch_reward = None
        self.batch_new_state = None
        self.batch_if_done = None
        self.batch_output = None

        self.start_time = time.time()
        self.end_time = time.time()

    def load_weights(self):
        logging.info('...... Loading weight ......')
        try:
            self.actor_network.model.load_weights("actormodel.h5")
            self.critic_network.model.load_weights("criticmodel.h5")
            self.actor_network.target_model.load_weights("actormodel.h5")
            self.critic_network.target_model.load_weights("criticmodel.h5")
            logging.info("Weight load successfully")
        except:
            logging.warn("Cannot find the weight !")

    def update_weights(self):
        logging.info('...... Updating weight ......')
        self.actor_network.model.save_weights("actormodel.h5", overwrite=True)
        with open("actormodel.json", "w") as outfile:
            json.dump(self.actor_network.model.to_json(), outfile)
        self.critic_network.model.save_weights("criticmodel.h5", overwrite=True)
        with open("criticmodel.json", "w") as outfile:
            json.dump(self.critic_network.model.to_json(), outfile)

    def update_batch(self):
        logging.info('...... Updating batch ......')
        self.batch = self.buffer.get_batch(self.batch_size)
        self.batch_state = np.squeeze(np.asarray([e[0] for e in self.batch]), axis=1)
        self.batch_action = np.asarray([e[1] for e in self.batch])
        self.batch_reward = np.asarray([e[2] for e in self.batch])
        self.batch_new_state = np.squeeze(np.asarray([e[3] for e in self.batch]), axis=1)
        self.batch_if_done = np.asarray([e[4] for e in self.batch])
        self.batch_output = np.asarray([e[2] for e in self.batch])
        target_q_values = self.critic_network.target_model.predict(
            [self.batch_new_state, self.actor_network.target_model.predict(self.batch_new_state)])
        for k, done in enumerate(self.batch_if_done):
            self.batch_output[k] = self.batch_reward[k] if done else self.batch_reward[k] + self.gamma * target_q_values[k]

    def update_loss(self):
        logging.info('...... Updating loss ......')
        self.loss += self.critic_network.model.train_on_batch([self.batch_state, self.batch_action], self.batch_output)
        actor_predict = self.actor_network.model.predict(self.batch_state)
        actor_grad = self.critic_network.gradients(self.batch_state, actor_predict)
        self.actor_network.train(self.batch_state, actor_grad)
        self.actor_network.target_train()
        self.critic_network.target_train()

    def get_action(self, train_indicator):
        logging.info('...... Getting action ......')
        self.epsilon -= 1.0 / self.explore_iter
        noise = []
        action_ori = self.sim.Cft_Accel * self.actor_network.model.predict(self.state_t)
        print("Action ", action_ori)
        for i in range(self.action_size):
            a = action_ori[0][i]
            noise.append(train_indicator * max(self.epsilon, 0) * self.tools.ou(a, 0.00, 0.01, 0.01))
        action = np.zeros([1, self.action_size])
        for i in range(self.action_size):
            action[0][i] = action_ori[0][i] + noise[i]
        return action

    def update_reward(self, action, train_indicator, e, j):
        logging.info('...... Updating reward ......')
        old_av_y = self.sim.av_pos['y']
        old_av_velocity = self.sim.av_pos['vy']
        state_t = self.state_t
        reward_t, collision = self.sim.get_reward(action[0][0])
        self.end_time = time.time()
        logging.debug('Episode: ', e, 'Step: ', j, 'loc: ', old_av_y, 'velocity: ', old_av_velocity,
                      'reward: ', reward_t, 'loss: ', self.loss)
        logging.debug('Training time: ',  self.end_time - self.start_time)
        state_t1 = self.sim.update_vehicle(action[0][0])
        self.start_time = time.time()

        self.buffer.add(state_t, action[0][0], reward_t, state_t1, self.if_done)
        self.update_batch()
        if train_indicator:
            self.update_loss()
        self.total_reward += reward_t

        if old_av_y >= self.sim.Stop_Line - 0.1 or collision > 0:
            self.if_pass = old_av_y >= self.sim.Stop_Line - 0.1 and (old_av_velocity <= 0.01)
            self.if_done = True
        else:
            self.if_pass = False
        self.state_t = state_t1
        return collision, self.if_pass

    def launch_train(self, train_indicator=1):  # 1 means Train, 0 means simply Run
        print 'Launch Training Process'
        np.random.seed(1337)
        self.state_t = self.sim.get_state()
        state_dim = self.sim.state_dim
        self.actor_network = ActorNetwork(self.tf_sess, state_dim, self.action_size, self.batch_size, self.tau, self.LRA)
        self.critic_network = CriticNetwork(self.tf_sess, state_dim, self.action_size, self.batch_size, self.tau, self.LRC)
        self.buffer = ReplayBuffer(self.buffer_size)
        self.load_weights()

        total_correct = 0.
        total_wrong = 0.

        for e in range(self.episode_count):
            print("Episode : " + str(e) + " Replay Buffer " + str(self.buffer.count()))
            for j in range(self.max_steps):
                self.loss = 0
                self.total_reward = 0
                self.state_t = self.sim.get_state()
                action_t = self.get_action(train_indicator)
                collision, if_pass = self.update_reward(action_t, train_indicator, e, j)

                if self.if_done:
                    self.sim = InterSim()
                    self.state_t = None
                    self.if_done = False
                    break

            if train_indicator:
                self.update_weights()

            total_correct += int(collision <= 0 and self.if_pass)
            total_wrong += int(collision > 0)
            accuracy = 0
            all_accuracy = []
            if total_correct + total_wrong:
                accuracy = total_correct / (total_correct + total_wrong)
            if np.mod(e, 100) == 0:
                all_accuracy.append(accuracy)
                total_correct = 0
                total_wrong = 0

            print("TOTAL REWARD @ " + str(e) + "-th Episode  : Reward " + str(self.total_reward) +
                  " Collision " + str(collision > 0) + " Accuracy " + str(accuracy) +
                  " All Accuracy " + str(all_accuracy))
            print("")
        print("Finish.")


if __name__ == '__main__':
    acc = ReinAcc()
    acc.launch_train()