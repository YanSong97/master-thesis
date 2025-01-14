import torch
import numpy as np
import gym
import math
import matplotlib.pyplot as plt
import torch.nn as nn


import seaborn as sns

import time

# -*- coding: utf-8 -*-
"""
Classic cart-pole system modified from Gym

We add a uniform or a Gaussian noise to either actuator and the sensor or both.
"""

import logging
import math
import random
import gym
from gym import spaces
from gym.utils import seeding
import numpy as np

logger = logging.getLogger(__name__)


class CartPoleModEnv(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second': 50
    }

    def __init__(self, case):
        self.__version__ = "0.2.0"
        print("CartPoleModEnv - Version {}, Noise case: {}".format(self.__version__, case))
        self.gravity = 9.8
        self.masscart = 1.0
        self.masspole = 0.1
        self.total_mass = (self.masspole + self.masscart)
        self.length = 0.5  # actually half the pole's length
        self.polemass_length = (self.masspole * self.length)
        self.seed()

        self.origin_case = case
        if case < 6:  # only model  noise
            self.force_mag = 30.0 * (1 + self.addnoise(case))
            self.case = 1
        elif case > 9:  # both model and data noise
            self.force_mag = 30.0 * (1 + self.addnoise(case))
            self.case = 10
        else:  # only data noise
            self.force_mag = 30.0
            self.case = case

        self.tau = 0.02  # seconds between state updates

        self.min_action = -1.
        self.max_action = 1.0

        # Angle at which to fail the episode
        self.theta_threshold_radians = 12 * 2 * math.pi / 360
        self.x_threshold = 2.4

        # Angle limit set to 2 * theta_threshold_radians so failing observation is still within bounds
        high = np.array([
            self.x_threshold * 2,
            np.finfo(np.float32).max,
            self.theta_threshold_radians * 2,
            np.finfo(np.float32).max])

        # self.action_space = spaces.Discrete(2) # AA Set discrete states back to 2
        self.action_space = spaces.Box(
            low=self.min_action,
            high=self.max_action,
            shape=(1,)
        )

        self.observation_space = spaces.Box(-high, high)

        self.viewer = None
        self.state = None

        self.steps_beyond_done = None

    def addnoise(self, x):
        return {
            1: 0,
            2: self.np_random.uniform(low=-0.05, high=0.05, size=(1,)),
            # 5% actuator noise ,  small model uniform noise
            3: self.np_random.uniform(low=-0.10, high=0.10, size=(1,)),
            # 10% actuator noise ,  large model uniform noise
            4: self.np_random.normal(loc=0, scale=np.sqrt(0.10), size=(1,)),  # small model gaussian noise
            5: self.np_random.normal(loc=0, scale=np.sqrt(0.50), size=(1,)),  # large model gaussian noise
            6: self.np_random.uniform(low=-0.05, high=0.05, size=(1,)),  # 5% sensor noise ,    small data uniform noise
            7: self.np_random.uniform(low=-0.10, high=0.10, size=(1,)),
            # 10% sensor noise ,    large data uniform noise
            8: self.np_random.normal(loc=0, scale=np.sqrt(0.10), size=(1,)),
            # 0.1              small data gaussian noise
            9: self.np_random.normal(loc=0, scale=np.sqrt(0.20), size=(1,)),
            # 0.2              large data gaussian noise
            10: self.np_random.normal(loc=0, scale=np.sqrt(0.10), size=(1,)),  # small both gaussian noise
            11: self.np_random.normal(loc=0, scale=np.sqrt(0.50), size=(1,)),  # large both gaussian noise
        }.get(x, 1)

    def seed(self, seed=None):  # Set appropriate seed value
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def stepPhysics(self, force):
        x, x_dot, theta, theta_dot = self.state
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        temp = (force + self.polemass_length * theta_dot * theta_dot * sintheta) / self.total_mass
        thetaacc = (self.gravity * sintheta - costheta * temp) / \
                   (self.length * (4.0 / 3.0 - self.masspole * costheta * costheta / self.total_mass))
        xacc = temp - self.polemass_length * thetaacc * costheta / self.total_mass
        # noise = self.addnoise(self.case)
        x = (x + self.tau * x_dot)
        x_dot = (x_dot + self.tau * xacc)
        theta = (theta + self.tau * theta_dot)  # *(1 + noise)
        theta_dot = (theta_dot + self.tau * thetaacc)
        return (x, x_dot, theta, theta_dot)

    def step(self, action):
        assert self.action_space.contains(action), "%r (%s) invalid" % (action, type(action))
        force = self.force_mag * float(action)
        self.state = self.stepPhysics(force)
        x, x_dot, theta, theta_dot = self.state

        # adding measurement noisy to theta
        noise = self.addnoise(self.case)
        theta = theta * (1 + noise)
        noise = self.addnoise(self.case)
        x = x * (1 + noise)
        noise = self.addnoise(self.case)
        x_dot = x_dot * (1 + noise)
        noise = self.addnoise(self.case)
        theta_dot = theta_dot * (1 + noise)

        output_state = (x, x_dot, theta, theta_dot)
        output_state = np.array(output_state)

        done = x < -self.x_threshold \
               or x > self.x_threshold \
               or theta < -self.theta_threshold_radians \
               or theta > self.theta_threshold_radians
        done = bool(done)

        if not done:
            reward = 1.0
        elif self.steps_beyond_done is None:
            # Pole just fell!
            self.steps_beyond_done = 0
            reward = 1.0
        else:
            if self.steps_beyond_done == 0:
                logger.warn(
                    "You are calling 'step()' even though this environment has already returned done = True. You should always call 'reset()' once you receive 'done = True' -- any further steps are undefined behavior.")
            self.steps_beyond_done += 1
            reward = 0.0

        # return np.array(self.state), reward, done, {}
        return output_state, reward, done, {}

    def reset(self):
        self.state = self.np_random.uniform(low=-0.05, high=0.05, size=(4,))
        self.steps_beyond_done = None

        if self.origin_case < 6:  # only model  noise
            self.force_mag = 30.0 * (1 + self.addnoise(self.origin_case))
        elif self.origin_case > 9:  # both model and data noise
            self.force_mag = 30.0 * (1 + self.addnoise(self.origin_case))
        else:  # only data noise
            self.force_mag = 30.0

        return np.array(self.state)

    def render(self, mode='human', close=False):
        if close:
            if self.viewer is not None:
                self.viewer.close()
                self.viewer = None
            return

        screen_width = 600
        screen_height = 400

        world_width = self.x_threshold * 2
        scale = screen_width / world_width
        carty = 100  # TOP OF CART
        polewidth = 10.0
        polelen = scale * 1.0
        cartwidth = 50.0
        cartheight = 30.0

        if self.viewer is None:
            from gym.envs.classic_control import rendering
            self.viewer = rendering.Viewer(screen_width, screen_height)
            l, r, t, b = -cartwidth / 2, cartwidth / 2, cartheight / 2, -cartheight / 2
            axleoffset = cartheight / 4.0
            cart = rendering.FilledPolygon([(l, b), (l, t), (r, t), (r, b)])
            self.carttrans = rendering.Transform()
            cart.add_attr(self.carttrans)
            self.viewer.add_geom(cart)
            l, r, t, b = -polewidth / 2, polewidth / 2, polelen - polewidth / 2, -polewidth / 2
            pole = rendering.FilledPolygon([(l, b), (l, t), (r, t), (r, b)])
            pole.set_color(.8, .6, .4)
            self.poletrans = rendering.Transform(translation=(0, axleoffset))
            pole.add_attr(self.poletrans)
            pole.add_attr(self.carttrans)
            self.viewer.add_geom(pole)
            self.axle = rendering.make_circle(polewidth / 2)
            self.axle.add_attr(self.poletrans)
            self.axle.add_attr(self.carttrans)
            self.axle.set_color(.5, .5, .8)
            self.viewer.add_geom(self.axle)
            self.track = rendering.Line((0, carty), (screen_width, carty))
            self.track.set_color(0, 0, 0)
            self.viewer.add_geom(self.track)

        if self.state is None: return None

        x = self.state
        cartx = x[0] * scale + screen_width / 2.0  # MIDDLE OF CART
        self.carttrans.set_translation(cartx, carty)
        self.poletrans.set_rotation(-x[2])
        return self.viewer.render(return_rgb_array=mode == 'rgb_array')

