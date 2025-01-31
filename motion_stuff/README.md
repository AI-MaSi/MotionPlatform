# Motion Platform Geometry Tester

3D visualization tool for validating measured geometries of a 2-actuator parallel motion platform. Tests and verifies the physical measurements of platform components (base width/height, top plate dimensions, hinge points) by simulating platform movement based on actuator lengths.

The repository also includes `kinematics2.py` which contains the same geometric calculations as the simulator but without the visualization components, useful for direct calculation of platform kinematics.

## Usage

1. Run the simulator:
```bash
python motion_sim_measure.py
```

2. The simulator automatically creates `actuator_lengths.txt` in the same folder, starting with default values of 75,75. Update this file to control the simulation:
```
stroke1,stroke2
```
where strokes are in mm (0-150mm range). Simply save the file after editing to update the visualization.

3. The 3D visualization updates automatically when `actuator_lengths.txt` changes. Displays:
- Platform position
- Current angles (pitch/roll)
- Actuator lengths and rotations
- Green/red indicators for valid/invalid actuator positions

## Controls
- Left-click and drag to rotate view
- Actuator lengths update automatically when `actuator_lengths.txt` changes