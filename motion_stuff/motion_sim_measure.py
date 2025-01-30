import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import os


class ParallelMechanism:
    def __init__(self):

        # TODO: find real values, these are only about right!
        # dimensions in mm

        # irl the actuator are connected higher that the joint
        # so we need to offset the pitch angle to match the real world
        self.PITCH_OFFSET = -25.5  # degrees

        # Base triangle measurements in mm
        base_width = 688  # width between servo mounts
        base_height = 885  # height

        # Top triangle measurements in mm
        top_width = 630  # width between servo mounts
        top_height = 522  # height

        # Hinge point height from floor in mm
        hinge_height = 255

        # Actuator limits in mm
        # measured by hand, not accurate!
        self.min_actuator_length = 560
        self.max_actuator_length = 706

        # Stroke length in mm
        self.stroke = 150

        # Offset for rotation if servo min is not at 0!
        # Tritex might have some offset in the rotation
        self.rot_offset = 0.0

        # Current angles
        self.current_pitch = 0.0
        self.current_roll = 0.0

        # Base triangle setup (all in mm)
        base_left = np.array([-base_width / 2, -base_height / 2, 0])
        base_right = np.array([base_width / 2, -base_height / 2, 0])
        base_top = np.array([0, base_height / 2, 0])
        self.base_points = np.array([base_top, base_left, base_right])

        # Fixed hinge point
        self.hinge_point = np.array([0, base_height / 2, hinge_height])

        # Top triangle setup
        rel_left = np.array([-top_width / 2, -top_height, 0])
        rel_right = np.array([top_width / 2, -top_height, 0])
        rel_top = np.array([0, 0, 0])

        # Initial pitch offset
        init_pitch = np.radians(self.PITCH_OFFSET)

        # Initial pitch rotation matrix
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

    def stroke_to_total_length(self, stroke_length):
        """Convert stroke length (0-150mm) to total actuator length"""
        stroke = np.clip(stroke_length, 0, self.stroke)
        return self.min_actuator_length + stroke

    def len_to_rot(self, length_mm, lead=None, stroke_mm=None, base_rot=None):
        """Convert length to rotations based on lead screw specs"""
        if lead is None:
            lead = self.lead  # 0.2 inches
        if stroke_mm is None:
            stroke_mm = self.stroke  # 150mm
        if base_rot is None:
            base_rot = self.rot_offset

        lead_mm = lead * 25.4  # convert lead from inches to mm
        return float(max(0, min(length_mm * lead_mm, stroke_mm * lead_mm)) + base_rot)

    def calculate_angles_from_lengths(self, lengths):
        """Calculate pitch and roll angles from actuator lengths using inverse kinematics"""
        pitch = 0
        roll = 0
        min_error = float('inf')

        # Search through possible angles to find best match
        for p in np.arange(-30, 30, 0.5):
            for r in np.arange(-30, 30, 0.5):
                rotated_top = self.rotate_top(p, r)
                calculated_lengths = self.calculate_actuator_lengths(rotated_top)
                error = np.sum((np.array(calculated_lengths) - np.array(lengths)) ** 2)

                if error < min_error:
                    min_error = error
                    pitch = p
                    roll = r

                    # If we find a very good match, break early
                    if error < 0.1:
                        break
            if min_error < 0.1:
                break

        return pitch, roll

    def rotate_top(self, pitch_deg, roll_deg):
        # Use raw pitch_deg since the PITCH_OFFSET is already applied in init
        pitch = np.radians(pitch_deg)
        roll = np.radians(roll_deg)

        pitch_matrix = np.array([
            [1, 0, 0],
            [0, np.cos(pitch), -np.sin(pitch)],
            [0, np.sin(pitch), np.cos(pitch)]
        ])

        roll_matrix = np.array([
            [np.cos(roll), 0, np.sin(roll)],
            [0, 1, 0],
            [-np.sin(roll), 0, np.cos(roll)]
        ])

        rotated_points = self.top_points - self.hinge_point
        rotated_points = np.dot(rotated_points, pitch_matrix.T)
        rotated_points = np.dot(rotated_points, roll_matrix.T)
        rotated_points = rotated_points + self.hinge_point

        return rotated_points

    def calculate_actuator_lengths(self, rotated_top_points):
        lengths = []
        for base_idx, top_idx in self.actuator_connections:
            base_point = self.base_points[base_idx]
            top_point = rotated_top_points[top_idx]
            length = np.linalg.norm(top_point - base_point)
            lengths.append(length)
        return lengths


# Create figure and initialize mechanism
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(top=0.8)

mechanism = ParallelMechanism()

# Initialize view angles and mouse control
elev = 30
azim = 225
initial_click = None

# Track file modification time
last_modified = 0


def on_mouse_press(event):
    global initial_click
    if event.button == 1:
        initial_click = (event.x, event.y)


def on_mouse_release(event):
    global initial_click
    initial_click = None


def on_mouse_move(event):
    global initial_click, elev, azim
    if initial_click is not None and event.button == 1:
        dx = event.x - initial_click[0]
        dy = event.y - initial_click[1]
        azim = (azim - dx * 0.3) % 360
        elev = np.clip(elev - dy * 0.3, -90, 90)
        initial_click = (event.x, event.y)


# Connect mouse event handlers
fig.canvas.mpl_connect('button_press_event', on_mouse_press)
fig.canvas.mpl_connect('button_release_event', on_mouse_release)
fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)


def update(frame):
    global last_modified, elev, azim

    # Check if file has been modified
    try:
        current_modified = os.path.getmtime('actuator_lengths.txt')
        if current_modified <= last_modified:
            return
        last_modified = current_modified

        with open('actuator_lengths.txt', 'r') as f:
            data = f.read().strip().split(',')
            stroke_lengths = [float(data[0]), float(data[1])]

        # Convert stroke lengths to total lengths
        lengths = [mechanism.stroke_to_total_length(sl) for sl in stroke_lengths]
    except (FileNotFoundError, ValueError, IndexError):
        stroke_lengths = [0, 0]
        lengths = [mechanism.min_actuator_length, mechanism.min_actuator_length]

    # Calculate pitch and roll from lengths
    pitch, roll = mechanism.calculate_angles_from_lengths(lengths)
    mechanism.current_pitch = pitch
    mechanism.current_roll = roll

    ax.cla()
    rotated_top = mechanism.rotate_top(pitch, roll)

    # Calculate rotations based on lead screw specs
    rotations = [mechanism.len_to_rot(sl, lead=0.2, stroke_mm=mechanism.stroke) for sl in stroke_lengths]

    # Scale the plot based on platform size (in mm)
    max_dim = 1000  # slightly larger than our largest dimension
    ax.set_xlim([-max_dim / 2, max_dim / 2])
    ax.set_ylim([-max_dim / 2, max_dim / 2])
    ax.set_zlim([0, max_dim])

    # Draw base triangle
    ax.plot_trisurf(mechanism.base_points[:, 0],
                    mechanism.base_points[:, 1],
                    mechanism.base_points[:, 2],
                    color='r', alpha=0.6)

    # Draw top triangle
    ax.plot_trisurf(rotated_top[:, 0],
                    rotated_top[:, 1],
                    rotated_top[:, 2],
                    color='k', alpha=0.6)

    # Draw actuators with color indicators
    for i, ((base_idx, top_idx), length) in enumerate(zip(mechanism.actuator_connections, lengths)):
        base_point = mechanism.base_points[base_idx]
        top_point = rotated_top[top_idx]
        color = 'r' if (stroke_lengths[i] < 0 or stroke_lengths[i] > mechanism.stroke) else 'g'
        ax.plot([base_point[0], top_point[0]],
                [base_point[1], top_point[1]],
                [base_point[2], top_point[2]],
                f'{color}-', linewidth=3)

    # Draw hinge point
    ax.scatter([mechanism.hinge_point[0]],
               [mechanism.hinge_point[1]],
               [mechanism.hinge_point[2]],
               color='yellow', s=100)

    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')

    # Update title with status information
    status_text = (
        f'Pitch (Driver seat): {pitch:.1f}° ({pitch + mechanism.PITCH_OFFSET:.1f}° plane)\n'
        f'Roll: {roll:.1f}°\n'
        f'Stroke Lengths: {stroke_lengths[0]:.1f}mm, {stroke_lengths[1]:.1f}mm\n'
        f'Total Lengths: {lengths[0]:.1f}mm, {lengths[1]:.1f}mm\n'
        f'Rotations: {rotations[0]:.1f}, {rotations[1]:.1f}'
    )
    ax.set_title(status_text, pad=25)

    # Maintain view angles
    ax.view_init(elev=elev, azim=azim)


# Create initial actuator lengths file with midpoint stroke (75mm)
with open('actuator_lengths.txt', 'w') as f:
    f.write('75,75')  # Start at midpoint stroke

# Create animation with updates only on file change
anim = FuncAnimation(fig, update, frames=None, interval=100, blit=False, cache_frame_data=False)

# Adjust plot settings
ax.set_box_aspect([1, 1, 1])
plt.show()