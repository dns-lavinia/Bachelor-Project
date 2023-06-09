import math
import time 

from enum import Enum

# Local imports
import log 
import constants

from srobot import SRobot


class SwarmState(Enum):
    NONE = 0
    
    # States used for the rotation of the swarm
    ROTATION_MOVE = 1
    ROTATION_ROT = 2

    # States used for the translation of the swarm
    TRANSLATION_INI = 3
    TRANSLATION_STOP = 4


class SwarmController:
    # The space that has to be left empty in the swarm formation circle
    U_SHAPE_ALPHA = math.pi

    # The default size of the swarm.
    SWARM_SIZE = 3

    # The angle that the swarm has to change when given the action to rotate. 
    # The direction of the rotation has to be given by vrot.
    ROT_ANGLE = math.pi / 5

    SWARM_RADIUS = 23  # in cm

    # Create and save the logger for this class
    logger = log.create_logger(name="Swarm",
                               level=log.LOG_INFO)

    def __init__(self, start_pos, start_angle, sim_space, goal_pos, target, *, swarm_size=SWARM_SIZE):
        self.space = sim_space
        self.goal_pos = goal_pos
        self.target = target

        self.swarm_size = swarm_size
        self.position = start_pos
        self.angle = start_angle  # in radians
        self.f_sca = self.SWARM_RADIUS  # in cm

        # Compute the beta angle (in radians)
        self.b_angle = (2 * math.pi - self.U_SHAPE_ALPHA) / (swarm_size - 1)

        # Add the robots in the swarm and place them in a U shape
        self.robots = self.__add_robots()

        self.r_target_pos = None
        self.r_dir = None
        self.vtras, self.vrot = None, None

        # Upon initialization, the swarm isn't performing any action
        self.state = SwarmState.NONE
        self.state_start = time.time()
        self.state_count = 0
        self.last_state = SwarmState.NONE

        # At first, the task is to get the swarm to go to the object
        self.task = constants.TASK_TO_FOOD

    def run(self, action=None):
        """The main body that drives the swarm. Can give an optional argument 
        which denotes the action to take (move the swarm linearly, rotate the
        swarm or scale it). If the swarm is already processing an action it will
        continue to do so until it is completed.
        
        Args:
            action (int): Can be one of the three options: 0 = tras, 1 = rot, 
            3 = sca or None (in which case the argument can be skipped).
        """
        
        assert (action in [0, 1, 2] or action is None), \
                "[Simulation.step] Given action is not recognized"

        # Print a message in the case there is a given action and the swarm is 
        # already processing something else
        if self.state != SwarmState.NONE and action is not None:
            self.logger.info("The swarm is already running a different action")
            return
        
        self.logger.debug(f"State is [{self.state}]")
        self.logger.debug(f"State count is {self.state_count}")

        if self.state_count > 150 and self.state == SwarmState.NONE and action is not None:
            action = 1 - action

        # If the swarm is ready to accept commands  
        if self.state == SwarmState.NONE:
            # Get the velocities to be used for the robots in the swarm
            self.vtras, self.vrot = self.get_avg_vel()

            self.logger.debug(f'Vtras is {self.vtras} and vrot is {self.vrot}')

            # Move the swarm
            if action == 0:
                if self.last_state != SwarmState.TRANSLATION_INI:
                    self.__reset_state_count()
                    self.last_state = SwarmState.TRANSLATION_INI
                else:
                    self.state_count += 1

                self.state = SwarmState.TRANSLATION_INI
                self.__reset_state_start()

            # Rotate the swarm
            elif action == 1:
                if self.last_state != SwarmState.ROTATION_MOVE:
                    self.__reset_state_count()
                    self.last_state = SwarmState.ROTATION_MOVE
                else:
                    self.state_count += 1

                # Target positions for each robot in the swarm
                self.r_target_pos = []

                # Start the translation movement for all of the robots to their
                # new designated position in the swarm
                for i in range(self.swarm_size):
                    # Get the new position of the robot within the swarm
                    new_pos = self.__compute_new_pos_for_robot(self.vrot, robot_n=i)
                    
                    # Save the new position
                    self.r_target_pos.append(new_pos)

                    # Stop the motion of the robot
                    for i in range(self.swarm_size):
                        self.robots[i].stop_move()
                    
                self.state = SwarmState.ROTATION_MOVE
                self.__reset_state_start()
        
        elif self.state == SwarmState.TRANSLATION_INI:
            for i in range(self.swarm_size):
                self.robots[i].move(self.vtras)
            
            # Update the position of the swarm
            new_x = self.position[0] \
                    + self.vtras * (self.swarm_size/constants.FPS) * math.cos(self.angle)
            new_y = self.position[1] \
                    + self.vtras * (self.swarm_size/constants.FPS) * math.sin(self.angle)
            
            self.position = new_x, new_y

            # Movement finished
            self.state = SwarmState.TRANSLATION_STOP
            self.__reset_state_start()
        
        elif self.state == SwarmState.TRANSLATION_STOP:
            for i in range(self.swarm_size):
                self.robots[i].stop_move()

            # Movement finished
            self.state = SwarmState.NONE

        elif self.state == SwarmState.ROTATION_MOVE:
            finished_tras = 0

            # If the swarm got stuck for more than 5 seconds
            if (time.time() - self.state_start) > 5:
                self.__unstuck_swarm()

            # Move each robot to the new spot
            for i in range(self.swarm_size):
                dist = (self.robots[i].body.position - self.r_target_pos[i]).get_length_sqrd()

                if dist >= 0.5 ** 2:
                    self.robots[i].move_to(target_pos=self.r_target_pos[i])
                else:
                    self.robots[i].stop_move()
                    finished_tras += 1
                    
            # If all of the robots finished moving to their designated position
            # align them with the swarm angle
            if finished_tras == self.swarm_size:
                # Update the angle of the swarm
                self.set_angle(new_angle=(self.angle 
                                          + 5 * self.vrot * (1.0/constants.FPS)))
                
                # Save the optimal direction that each robot should rotate at
                self.r_dir = []
                for i in range(self.swarm_size):
                    norm_angle = self.angle % (2 * math.pi)
                    norm_robot_angle = self.robots[i].body.angle % (2 * math.pi)
                    diff = (norm_angle - norm_robot_angle) % (2 * math.pi)

                    self.r_dir.append(1 if diff < math.pi else -1)
        
                self.state = SwarmState.ROTATION_ROT
                self.__reset_state_start()

        elif self.state == SwarmState.ROTATION_ROT:
            for i in range(self.swarm_size):
                self.robots[i].body.angle = self.angle % (2 * math.pi)

            self.state = SwarmState.NONE

    def __unstuck_swarm(self):
        for i in range(self.swarm_size):
            self.robots[i].body.angle = self.angle
        
        # Reset the state
        self.state = SwarmState.NONE

    def __reset_state_count(self):
        self.state_count = 0

    def __reset_state_start(self):
        self.state_start = time.time()

    def set_task(self, task):
        assert (task == constants.TASK_TO_FOOD or task == constants.TASK_TO_NEST), \
            f"The task {task} is not recongized"
        
        self.task = task

    def set_angle(self, new_angle):
        self.angle = new_angle

    def get_sign(self, num):
        """
        Returns:
            int: sign(num)
        """

        if num > 0:
            return 1
        elif num < 0:
            return -1 
        
        return 0

    def get_avg_vel(self):
        """
        Returns:
            (float, float): Average vrot and vtras for all robots.
        """
        
        sum_vtras = 0
        sum_vrot = 0
        n = self.swarm_size
        target_pos = self.__get_target_pos()

        for i in range(n):
            vtras, vrot = self.robots[i].get_velocities(target_pos)

            sum_vtras += vtras
            sum_vrot += vrot

        return sum_vtras/n, sum_vrot/n
    
    def __get_target_pos(self):
        """Return the position of the current target, which based on the task 
        can be either the home base or the food object."""

        if self.task == constants.TASK_TO_FOOD:
            return self.target.body.position
        
        elif self.task == constants.TASK_TO_NEST:
            return self.goal_pos

    def __compute_new_pos_for_robot(self, vrot, robot_n):
        """Based on the direction of the rotational velocity, compute the new 
        coordinates for a robot within the swarm.

        The new position is computed knowing the position of the robot, as well
        as the angle that the swarm would rotate at (see `SwarmController.ROT_ANGLE`).

        Args:
            vrot (float): Rotational velocity. Can be either positive or negative.
            robot_n (int): The order of the robot in the swarm.

        Returns:
            (int, int): New position for the designated robot within the swarm
        """
        old_angle = self.angle + self.U_SHAPE_ALPHA / 2 + (robot_n * self.b_angle)
        swarm_center = self.position
        angle = 5 * vrot * (1.0/constants.FPS)

        if vrot > 0:
            # Move clockwise
            x_new = swarm_center[0] + self.f_sca * math.cos(old_angle + angle)
            y_new = swarm_center[1] + self.f_sca * math.sin(old_angle + angle)
        else:
            # Move anti-clockwise
            x_new = swarm_center[0] + self.f_sca * math.cos(old_angle - angle)
            y_new = swarm_center[1] + self.f_sca * math.sin(old_angle - angle)
        
        return x_new, y_new

    def __add_robots(self):
        """Arrange the robots in a U shape around the starting position of the
        swarm."""
        
        robots = []
        for i in range(self.swarm_size):
            # Get the position of the robot in the formation
            pos = self.__get_robot_pos(angle=(i * self.b_angle))

            robots.append(SRobot(space=self.space, 
                                 start_pos=pos,
                                 start_angle=self.angle))
        
        return robots
    
    def __get_robot_pos(self, angle):
        """Return the position of a robot for a given beta angle."""
        pos_x = self.position[0]  \
                + self.f_sca * math.cos(self.angle + self.U_SHAPE_ALPHA/2 + angle)
        
        pos_y = self.position[1] \
                + self.f_sca * math.sin(self.angle + self.U_SHAPE_ALPHA/2 + angle)

        return pos_x, pos_y 
