"""Render wall boxes as a gz sim (Harmonic) SDF world."""
from __future__ import annotations

from collections.abc import Iterable

from .geometry import WallBox

_WORLD_HEADER = """<?xml version="1.0"?>
<sdf version="1.9">
  <world name="{name}">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>50 50</size></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>50 50</size></plane></geometry>
          <material><diffuse>0.8 0.8 0.8 1</diffuse></material>
        </visual>
      </link>
    </model>

    <model name="scanned_room">
      <static>true</static>
      <link name="walls">
"""

_WORLD_FOOTER = """      </link>
    </model>
  </world>
</sdf>
"""

_BOX = """        <collision name="wall_{i}_c">
          <pose>{x:.4f} {y:.4f} {z:.4f} 0 0 0</pose>
          <geometry><box><size>{sx:.4f} {sy:.4f} {h:.4f}</size></box></geometry>
        </collision>
        <visual name="wall_{i}_v">
          <pose>{x:.4f} {y:.4f} {z:.4f} 0 0 0</pose>
          <geometry><box><size>{sx:.4f} {sy:.4f} {h:.4f}</size></box></geometry>
          <material><diffuse>0.55 0.6 0.7 1</diffuse></material>
        </visual>
"""


def box_element(index: int, box: WallBox, height: float) -> str:
    return _BOX.format(i=index, x=box.x, y=box.y, z=height / 2.0,
                       sx=box.size_x, sy=box.size_y, h=height)


def render_world(boxes: Iterable[WallBox], wall_height: float, name: str = "scanned_room") -> str:
    body = "".join(box_element(i, b, wall_height) for i, b in enumerate(boxes))
    return _WORLD_HEADER.format(name=name) + body + _WORLD_FOOTER
