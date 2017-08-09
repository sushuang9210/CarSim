import matplotlib.pyplot as plt
import numpy as np
from random import randint, random
from utilities.toolfunc import ToolFunc
import logging
import utilities.log_color

__author__ = 'qzq'


class InterSim(object):
    Tau = 1. / 30
    Speed_limit = 12        # m/s
    Scenary = randint(0, 2)
    Inter_Ori = 0.
    #Stop_Line = - 5. - random()
    Stop_Line = 150
    Pass_Point = 168
    Inter_Low = - 5.288
    Inter_Up = 5.288
    Inter_Left = - 4.013
    Inter_Right = 4.013
    Vehicle_NO = 3
    Lane_Left = 0.
    Lane_Right = 4.
    Cft_Accel = 3.     # m/s**2
    Visual = False

    tools = ToolFunc()

    def __init__(self):
        self.sim = None
        self.av_pos = dict()
        self.av_pos['y'] = - random() * 50. - 100.
        self.Start_Pos = self.av_pos['y']
        self.av_pos['x'] = 2.
        self.av_pos['vx'] = 0.
        self.av_pos['vy'] = random() * self.Speed_limit + 5
        self.av_pos['heading'] = 0
        self.av_pos['aceel'] = 0
        self.av_pos['steer'] = 0
        self.av_size = [4, 2]
        self.hv_poses = []
        for i in range(self.Vehicle_NO):
            hv_pos = dict()
            hv_pos['y'] = self.av_pos['y'] + random() * 50. + 20.
            hv_pos['x'] = 2.
            hv_pos['vx'] = 0.
            hv_pos['vy'] = self.Speed_limit - random()
            self.hv_poses.append(hv_pos)
        self.target_dis = None
        self.target_v = None
        self.state = None
        self.state_dim = None

        self.state_av = []
        self.state_fv = []
        self.state_road = []

    def draw_scenary(self, av, hvs):
        if self.Visual:
            plt.figure(1)
            plt.plot(0, self.Inter_Ori, 'g.', markersize=10)
            plt.plot(list(range(4)), list([self.Stop_Line] * 4), 'g')
            plt.plot(list(xrange(-20, 20)), list([self.Inter_Low] * 40), 'r')
            plt.plot(list(xrange(-20, 20)), list([self.Inter_Up] * 40), 'r')
            plt.plot(list([self.Inter_Left] * 400), list(xrange(-200, 200)), 'r')
            plt.plot(list([self.Inter_Right] * 400), list(xrange(-200, 200)), 'r')
            plt.plot(self.Inter_Right / 2., self.Pass_Point, 'g.', markersize=10)
            plt.plot(av['x'], av['y'], 'r.', markersize=15)
            plt.text(av['x'], av['y'], str(av['vy']))
            for hv in hvs:
                plt.plot(hv['x'], hv['y'], 'c.', markersize=15)
                plt.text(hv['x'], hv['y'], str(hv['vy']))
            plt.show()
            plt.pause(0.1)
            plt.clf()

    # def get_state(self, a=0):
    #     self.update_vehicle(a)
    #     front_dis = [hv_pos['y'] - self.av_pos['y'] for hv_pos in self.hv_poses]
    #     sl_dis = self.Stop_Line - self.av_pos['y']
    #     dis_pool = [sl_dis] + front_dis
    #     self.target_dis = min(dis_pool)
    #     min_i = np.argmin(dis_pool)
    #     self.target_v = 0. if min_i == 0 else self.hv_poses[min_i-1]['vy']
    #     self.state = np.array([self.av_pos['vy'], self.target_v, self.target_dis], ndmin=2)
    #     self.state_dim = self.state.shape[1]
    #     print 'Accel: ', a, ', V_av = ', self.av_pos['vy'], ', Distance Pool: ', dis_pool

    def get_state(self):
        self.state_av = [self.av_pos['vy'], self.av_pos['heading'], self.av_pos['aceel'], self.av_pos['steer']]
        fv_dis_list = [hv_pos['y'] - self.av_pos['y'] for hv_pos in self.hv_poses]
        fv_index = np.argmin(fv_dis_list)
        fv_pos = self.hv_poses[fv_index]
        self.state_fv = [fv_pos['vy'], fv_pos['y'] - self.av_pos['y']]
        sl_dis = self.Stop_Line - self.av_pos['y']
        ll = self.av_pos['x'] - self.av_size[1] / 2 - self.Lane_Left
        lr = self.Lane_Right - (self.av_pos['x'] + self.av_size[1] / 2)
        self.state_road = [sl_dis, ll, lr]
        self.state = np.array(self.state_av + self.state_fv + self.state_road, ndmin=2)
        self.state_dim = self.state.shape[1]
        return self.state

    def update_vehicle(self, a=0, st=0):
        for hv_pos in self.hv_poses:
            hv_a = - 0.5 * (hv_pos['vy'] ** 2) / (self.Stop_Line - hv_pos['y']) if hv_pos['y'] < self.Stop_Line - 1 \
                else self.Cft_Accel
            hv_pos['vy'] += hv_a * self.Tau
            hv_pos['vy'] = min(max(0.1, hv_pos['vy']), self.Speed_limit)
            hv_pos['y'] += hv_pos['vy'] * self.Tau + 0.5 * hv_a * (self.Tau ** 2)
        old_av_vel = self.av_pos['vy']
        self.av_pos['vy'] += a * self.Tau
        self.av_pos['vy'] = max(0.1, self.av_pos['vy'])
        self.av_pos['y'] += old_av_vel * self.Tau + 0.5 * a * (self.Tau ** 2)
        self.av_pos['heading'] += st
        self.av_pos['aceel'] = a
        self.av_pos['steer'] = st
        if self.Visual:
            self.draw_scenary(self.av_pos, self.hv_poses)
        return self.get_state()

    def get_reward(self, a=0, st=0):
        r_smooth = self.reward_smooth(a, st)
        r_clerance, collision = self.reward_clear()
        r_stop = self.reward_stop()
        r_speedlimit = self.reward_speedlimit()
        r_v = 0.1 * self.av_pos['vy'] - 0.2 if self.av_pos['vy'] <= self.Speed_limit \
            else (- 0.6 * self.av_pos['vy'] + 8.4) - 0.2
        r_v = max(- 0.2, r_v)
        r_time = - 3.0
        r_finish = self.reward_finish()
        r = r_smooth + r_clerance + r_stop + r_speedlimit + r_v + r_time + r_finish
        return r, collision

    def reward_smooth(self, a, st):
        x1 = a - self.av_pos['aceel']
        f1 = - 2. * abs(self.tools.sigmoid(x1, 5) - 0.5) + 0.9
        x2 = st - self.av_pos['steer']
        f2 = - 2. * abs(self.tools.sigmoid(x2, 2) - 0.5) + 0.9
        return f1 + f2

    def reward_clear(self):
        f_clear = self.state_fv[1]
        ff = abs(self.tools.sigmoid(f_clear, 0.4) - 1.0) + 0.1
        l_clear = self.state_road[1]
        fl = abs(self.tools.sigmoid(l_clear, 6) - 1.) + 0.1
        r_clear = self.state_road[2]
        fr = abs(self.tools.sigmoid(r_clear, 6) - 1.) + 0.1
        collision = (f_clear <= 0.1) or (r_clear <= 0.1) or (l_clear <= 0.1)
        return ff + fl + fr,  collision

    def reward_stop(self):
        th_1 = 2. * self.Cft_Accel
        th_2 = 2.
        mid_point = (th_1 + th_2) / 2
        x = self.av_pos['vy'] ** 2 / self.state_road[0] - mid_point
        fx = self.tools.sigmoid(x, - 1) - 0.1
        return fx

    def reward_speedlimit(self):
        th_1 = self.Speed_limit
        th_2 = th_1 + 2.
        mid_point = (th_1 + th_2) / 2
        x = self.av_pos['vy'] - mid_point
        fx = self.tools.sigmoid(x, - 3) - 0.9
        return fx

    def reward_finish(self):
        if self.state_road[0] <= 2.0 and (self.av_pos['vy'] <= 0.15):
            return 500.
        else:
            return 0.


if __name__ == '__main__':
    sim = InterSim()
    plt.ion()
    while sim.av_pos['y'] <= sim.Pass_Point:
        sim.get_state()
        sim.get_reward()
        sim.update_vehicle()
