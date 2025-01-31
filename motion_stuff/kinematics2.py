import numpy as np

# AI optimized code, just slightly faster than original

class MotionPlatformKinematics:
    def __init__(self, **kwargs):

        # Manually measured values, might need to be adjusted!
        base_width = kwargs.get('base_width', 688.0)                          # width between lower servo mounts
        base_height = kwargs.get('base_height', 885.0)                        # distance to lower hinge point (from triangle bottom)
        top_width = kwargs.get('top_width', 630.0)                            # width between upper servo mounts
        top_height = kwargs.get('top_height', 522.0)                          # distance to upper hinge point (from triangle bottom)
        hinge_height = kwargs.get('hinge_height', 255.0)                      # hinge point height from floor
        self.min_actuator_length = kwargs.get('min_actuator_length', 560.0)   # minimum actuator length
        self.max_actuator_length = kwargs.get('max_actuator_length', 706.0)   # maximum actuator length
        self.rot_offset = kwargs.get('rot_offset', 0.0)                       # offset for rotation if servo min is not at 0. Tritex might show some weird zero point value
        pitch_offset = kwargs.get('pitch_offset', -25.5)                      # initial pitch offset ("seat to triangle" offset)

        # from brochure, should be accurate
        self.stroke = kwargs.get('stroke', 150.0)     # actuator stroke length
        self.lead = kwargs.get('lead', 0.2)         # lead screw pitch (inches/rotation)


        # lead in mm
        self.lead_mm = self.lead * 25.4

        # Base triangle setup (all in mm)
        base_left = np.array([-base_width/2, -base_height/2, 0])
        base_right = np.array([base_width/2, -base_height/2, 0])
        base_top = np.array([0, base_height/2, 0])
        self.base_points = np.array([base_top, base_left, base_right])

        # Fixed hinge point
        self.hinge_point = np.array([0, base_height/2, hinge_height])

        # Top triangle setup relative to hinge
        rel_left = np.array([-top_width/2, -top_height, 0])
        rel_right = np.array([top_width/2, -top_height, 0])
        rel_top = np.array([0, 0, 0])

        # Initial pitch offset
        init_pitch = np.radians(pitch_offset)
        init_pitch_matrix = np.array([
            [1, 0, 0],
            [0, np.cos(init_pitch), -np.sin(init_pitch)],
            [0, np.sin(init_pitch), np.cos(init_pitch)]
        ])

        # Apply initial rotation and translate to hinge point
        rotated_points = np.dot(np.array([rel_top, rel_left, rel_right]), init_pitch_matrix.T)
        self.top_points = rotated_points + self.hinge_point
        self.hinge_point = self.top_points[0]

        # Actuator connections
        self.actuator_connections = [(1, 1), (2, 2)]

    def calculate(self, pitch, roll):
        """
        Calculate servo rotations for given pitch and roll angles
        """
        pitch_rad = np.radians(pitch)
        roll_rad = np.radians(roll)

        # Create rotation matrices
        pitch_matrix = np.array([
            [1, 0, 0],
            [0, np.cos(pitch_rad), -np.sin(pitch_rad)],
            [0, np.sin(pitch_rad), np.cos(pitch_rad)]
        ])

        roll_matrix = np.array([
            [np.cos(roll_rad), 0, np.sin(roll_rad)],
            [0, 1, 0],
            [-np.sin(roll_rad), 0, np.cos(roll_rad)]
        ])

        # Rotate points
        points_rel = self.top_points - self.hinge_point
        points_pitched = np.dot(points_rel, pitch_matrix.T)
        points_rolled = np.dot(points_pitched, roll_matrix.T)
        rotated_points = points_rolled + self.hinge_point

        # Calculate lengths
        lengths = []
        for base_idx, top_idx in self.actuator_connections:
            base_point = self.base_points[base_idx]
            top_point = rotated_points[top_idx]
            length = float(np.linalg.norm(top_point - base_point))
            lengths.append(length)

        # Calculate strokes
        stroke_lengths = [float(max(0.0, min(length - self.min_actuator_length, self.stroke)))
                         for length in lengths]

        # Calculate rotations
        rotations = [float(stroke * self.lead_mm + self.rot_offset)
                    for stroke in stroke_lengths]

        return {
            'total_length': {
                'servo1': lengths[0],
                'servo2': lengths[1]
            },
            'stroke_length': {
                'servo1': stroke_lengths[0],
                'servo2': stroke_lengths[1]
            },
            'rotations': {
                'servo1': rotations[0],
                'servo2': rotations[1]
            }
        }


# example usage:
# kin = MotionPlatformKinematics()
# result = kin.calculate(0, 0) # pitch, roll
# print(result)