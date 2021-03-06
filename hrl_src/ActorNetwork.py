import numpy as np
import math
#from keras.initializations import normal, identity
from keras.initializers import RandomNormal, identity
from keras.models import Sequential, Model
from keras.layers import Dense, Flatten, Input, merge, Lambda, concatenate
from keras.optimizers import Adam
import tensorflow as tf
import keras.backend as K

HIDDEN1_UNITS = 1024
HIDDEN2_UNITS = 512
HIDDEN3_UNITS = 256
HIDDEN4_UNITS = 128


class ActorNetwork(object):
    def __init__(self, sess=None, state_size=None, action_size=None, batch_size=None, sigma=None, learn_rate=None):
        self.sess = sess
        self.batch_size = batch_size
        self.sigma = sigma
        self.learn_rate = learn_rate

        K.set_session(sess)

        # Now c0reate the model
        self.model, self.weights, self.state = self.create_actor_network(state_size, action_size)
        self.target_model, self.target_weights, self.target_state = self.create_actor_network(state_size, action_size)
        self.action_gradient = tf.placeholder(tf.float32,[None, action_size])
        self.params_grad = tf.gradients(self.model.output, self.weights, -self.action_gradient)
        grads = zip(self.params_grad, self.weights)
        self.optimize = tf.train.AdamOptimizer(learn_rate).apply_gradients(grads)
        self.sess.run(tf.global_variables_initializer())

    def train(self, states, action_grads):
        self.sess.run(self.optimize, feed_dict={
            self.state: states,
            self.action_gradient: action_grads
        })

    def target_train(self):
        actor_weights = self.model.get_weights()
        actor_target_weights = self.target_model.get_weights()
        for i in range(len(actor_weights)):
            actor_target_weights[i] = self.sigma * actor_weights[i] + (1 - self.sigma) * actor_target_weights[i]
        self.target_model.set_weights(actor_target_weights)

    def create_actor_network(self, state_size, action_size):
        print("Now we build the model")
        S  = Input(shape=[state_size])
        h0 = Dense(HIDDEN1_UNITS, activation='relu')(S)
        h1 = Dense(HIDDEN2_UNITS, activation='relu')(h0)
        h2 = Dense(HIDDEN3_UNITS, activation='relu')(h1)
        h3 = Dense(HIDDEN4_UNITS, activation='sigmoid')(h2)

        Action          = Dense(4, activation='softmax', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Acc1  = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Acc2  = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Time1 = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Time2 = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Time3 = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)
        Parameter_Time4 = Dense(1, activation='sigmoid', kernel_initializer=RandomNormal(mean=0.0, stddev=1e-4, seed=None))(h3)

        V = concatenate([Action, Parameter_Acc1, Parameter_Acc2, Parameter_Time1, Parameter_Time2,
                   Parameter_Time3, Parameter_Time4])
        # V = tf.concat(values=[Action, Parameter])
        model = Model(input=S,output=V)
        return model, model.trainable_weights, S
