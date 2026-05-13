import os

os.environ["PYTHONWARNINGS"] = "ignore::RuntimeWarning:runpy"

import gym
import minerl
import pyglet

pyglet.options["dpi_scaling"] = "stretch"

from minerl.human_play_interface.human_play_interface import HumanPlayInterface


CONTROLS = """
Controls:
  W/A/S/D      move
  Space        jump
  Left Ctrl    sprint
  Left Shift   sneak
  Mouse        look
  Left click   attack
  Right click  use
  E            inventory
  Q            drop
  1-9          hotbar
  Esc          end episode
"""


def main():
    env = gym.make('MineRLBasaltFindCave-v0')
    env = HumanPlayInterface(env)

    print(CONTROLS)
    obs = env.reset()
    done = False

    try:
        while not done:
            obs, reward, done, _ = env.step()
    finally:
        env.close()

if __name__ == "__main__":
    main()
