import random
import math

import pygame
import pymunk
import pymunk.pygame_util

# Local imports
import constants

from srobot import SRobot
from swarm import SwarmController

class Simulation:
    OBSERVATION_SPACE_N = 6
    ACTION_SPACE_N = 3

    def __init__(self, screen_size=constants.SCREEN_SIZE):
        """Initialize the simulation.

        Args:
            screen_size ((int, int), optional): The size of the surface. Defaults 
            to constants.SCREEN_SIZE.
        """
        # Initialize the game
        pygame.init()

        # Save the dimension of the surface
        self.screen_size = screen_size

        # Set the screen dimensions
        self.screen = pygame.display.set_mode(self.screen_size)

        # Set the title of the simulation
        pygame.display.set_caption("Foraging in Swarm Robotics")
        self.clock = pygame.time.Clock()

        # Considering the screen variable above, the space would occupy
        # this whole screen and would have a dimension equal to the one
        # specified above
        self.space = pymunk.Space()
        self.space.gravity = (0.0, 0.0)
    
        # Declare the optional attributes of the space
        self.draw_options = pymunk.pygame_util.DrawOptions(self.screen)

        # Add the homebase 
        self.goal_pos = self.get_homebase_pos()

        # Create every object in the simulation
        self.reset()
    
    def reset(self):
        """On reset, the robots and the target are placed in the starting positions."""
        
        # Remove all bodies from the space
        for shape in self.space.shapes:
            self.space.remove(shape)

        # Add the boundary again
        self.__add_boundary()

        # Add the target again
        self.target = self.add_target()

        # Add the robots again
        self.swarm = SwarmController(start_pos=self.goal_pos, 
                                     start_angle=(-math.pi / 2),
                                     sim_space=self.space,
                                     goal_pos=self.goal_pos)

        return [self.target.body.position[0], self.target.body.position[1],
                self.goal_pos[0], self.goal_pos[1],
                self.swarm.angle, self.swarm.f_sca]

    def step(self, action):
        """Advance the simulation one step given an action.
        
        Args:
            action (int): Can be one of the three options: 0 = tras, 1 = rot, 
            3 = sca.
        """

        # TODO: uncomment this
        # assert (action in [0, 1, 2]), \
        #         "[Simulation.step] Given action is not recognized"

        last_pos = self.swarm.position  # Save the last position of the swarm 
        last_target = self.target.body.position  # Save the last position of the target

        # Perform the given action
        self.swarm.perform_action(action)

        # Compute the reward
        reward = self.__get_reward(last_pos, self.swarm.position, last_target)

        # Check if the swarm managed to bring the target food object into the nest
        done = True if (self.target.point_query(self.goal_pos).distance < 0) else False 

        new_state = [self.target.body.position[0], self.target.body.position[1],
                     self.goal_pos[0], self.goal_pos[1],
                     self.swarm.angle, self.swarm.f_sca]

        return new_state, reward, done

    def __get_dist(self, pos1, pos2):
        """Based on 2 points in the simulation, get the distance between them."""

        return math.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)

    def __get_reward(self, last_pos, pos, last_target):
        """
        Args:
            last_pos ((int, int)): The previous position of the swarm.
            pos ((int, int)): The current position of the swarm.

        Returns:
            int: Value of the reward
        """

        # If box is in goal
        if self.target.point_query(self.goal_pos).distance < 0:
            return 100
        
        dist_to_goal = self.__get_dist(self.swarm.position, self.target.body.position)

        if dist_to_goal > constants.SWARM_BOX_NEAR:
            # Check wether the swarm got closer to the target
            dist_last = self.__get_dist(last_pos, self.target.body.position)
            dist = self.__get_dist(pos, self.target.body.position)

            if (dist_last - dist) > 0.0001:
                return 1
        
        else:
            # Check wether the food object got closer to the goal
            dist_last = self.__get_dist(last_target, self.goal_pos)
            dist = self.__get_dist(self.target.body.position, self.goal_pos)

            if (dist_last - dist) > 0.0001:
                return 1
            return 5
        
        # If none of the conditions above are met, then the reward is -1
        return -1

    def add_robots(self, start_pos, n_robots=constants.ROBOTS_NUMBER):
        """Add a number of robots to the simulation.

        Args:
            start_pos ((int, int)): The robots will be created around this 
            starting position.

            n_robots (int, optional): The number of robots to be created. 
            Defaults to constants.ROBOTS_NUMBER.

        Returns:
            A list containing the robots instances.
        """
    
        robots = []
        for _ in range(n_robots):
            robots.append(SRobot(self.space, start_pos))
        
        return robots

    def add_target(self, mass=1, length=20, position=None):
        """Create and add to the space of the simulation the target object that
        is to be carried by the robots to the home base. The shape of the target
        object will be a square.

        The mass is measured in kg.
        The length of the rectangular body is measured in cm.
        
        The target object will be added at the top right corner of the surface
        if the position is not specified."""

        body = pymunk.Body()

        # Add the target object in the upper right corner 
        # if the position is not given
        if position is None:
            h, w = self.screen_size
            x = random.randint(w - w/5, w - (w/5 - w/25))  # 400, 420
            y = random.randint(w/5 - w/25, w/5 + w/25)  # 80, 120
        else:
            x, y = position

        # Set the initial position of the target
        body.position = x, y

        # Add a square shape for the target
        shape = pymunk.Poly.create_box(body, (length, length), 0.0)
        shape.color = constants.COLOR["hunter-green"]
        shape.mass = mass  # mass in kg
        shape.friction = 1  

        # Add the target object to the space
        self.space.add(body, shape)

        return shape
    
    def get_homebase_pos(self, position=None):
        """Returns the coordonates of the homebase (x, y)."""

        # Add the hombase in the lower left corner 
        # if the position is not given
        if position is None:
            h, w = self.screen_size
            x = random.randint(w/10, w/5 - w/25)  # 50, 80
            y = random.randint(w - w/5, w - (w/5 - w/25))  # 400, 420
        else:
            x, y = position

        return x, y

    def __add_boundary(self, color=constants.COLOR["black"]):
        """Initialize and add to the simulation a boundary around the visible
        environment.
        
        Args:
            color ((int, int, int, int)): The color of the boundary box.
        """

        static_body = self.space.static_body
        max_w, max_h = self.screen_size

        left_segm = pymunk.Segment(static_body, a=(0, 0), b=(0, max_h), radius=1.0)
        self.space.add(left_segm)
        left_segm.friction = 1
        left_segm.color = color

        right_segm = pymunk.Segment(static_body, a=(max_w-2, 0), b=(max_w-2, max_h-2), radius=1.0)
        self.space.add(right_segm)
        right_segm.friction = 1
        right_segm.color = color

        up_semg = pymunk.Segment(static_body, a=(0, 0), b=(max_w, 0), radius=1.0)
        self.space.add(up_semg)
        up_semg.friction = 1
        up_semg.color = color

        down_segm = pymunk.Segment(static_body, a=(0, max_h-2), b=(max_w-2, max_h-2), radius=1.0)
        self.space.add(down_segm)
        down_segm.friction = 1
        down_segm.color = color
