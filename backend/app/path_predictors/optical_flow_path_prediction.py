import json
import math
from typing import List, Tuple

import cv2
import numpy as np
import numpy.typing as npt
from shapely.geometry import LineString
from tqdm import tqdm


class OpticalFlowPathEstimator:
    """
    Estimates the flight path of a drone from a video file using Classical Optical Flow (Lucas-Kanade).

    Unlike Deep Learning models that process entire images, this estimator tracks specific
    'features' (corners/points) to determine how the camera moved relative to the ground.
    """

    def __init__(self, video_path: str, start_lat: float, start_lon: float, scale_factor: float = 0.1):
        self.video_path = video_path
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.scale_factor = scale_factor  # Meters per pixel of camera movement
        self.trajectory_points: List[Tuple[float, float]] = [(start_lon, start_lat)]

    def process_video(self) -> str:
        """
        Main loop to process video frames and translate pixel-motion into geographic coordinates.
        """
        cap = cv2.VideoCapture(self.video_path)

        if not cap.isOpened():
            raise ValueError("Could not open video file")

        # --- Metadata Setup ---
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Read the first frame to establish the initial set of tracking points
        ret: bool
        old_frame: npt.NDArray[np.uint8]
        ret, old_frame = cap.read()
        if not ret:
            return json.dumps(LineString(self.trajectory_points).__geo_interface__)

        # Optical Flow is typically calculated on grayscale images for speed and simplicity
        old_gray: npt.NDArray[np.uint8] = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)

        # --- Lucas-Kanade Parameters ---
        # Shi-Tomasi Corner Detection: Finds high-contrast points that are easy to track
        feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)

        # Lucas-Kanade Flow: Tracks the points across frames using a multi-level pyramid (winSize)
        lk_params = dict(winSize=(15, 15), maxLevel=2,
                         criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        # Find initial features to track
        p0: npt.NDArray[np.float32] = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)

        current_lat = self.start_lat
        current_lon = self.start_lon
        METERS_PER_DEGREE_LAT = 111320.0  # Standard approximation for latitude to meters

        # --- Main Processing Loop ---
        with tqdm(total=total_frames, desc="Optical Flow Processing", unit="frame") as pbar:
            frames_since_update = 1  # Account for the first frame already read

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # --- Batch Progress Bar Updates ---
                # Updating the UI/Terminal every single frame is slow; we batch updates every 120 frames
                frames_since_update += 1
                if frames_since_update >= 120:
                    pbar.update(frames_since_update)
                    frames_since_update = 0

                frame_gray: npt.NDArray[np.uint8] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # --- Calculate Optical Flow ---
                # Predict where the points in 'p0' moved to in 'frame_gray'
                p1: npt.NDArray[np.float32]
                st: npt.NDArray[np.uint8]  # Status: 1 if point was found, 0 if lost
                err: npt.NDArray[np.float32]
                p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

                if p1 is not None:
                    # Select only the points that were successfully tracked
                    good_new = p1[st == 1]
                    good_old = p0[st == 1]

                    dxs: List[float] = []
                    dys: List[float] = []

                    # Calculate the pixel displacement (delta) for every tracked point
                    for i, (new, old) in enumerate(zip(good_new, good_old)):
                        a, b = new.ravel()  # Current position (x, y)
                        c, d = old.ravel()  # Previous position (x, y)
                        dxs.append(float(a - c))
                        dys.append(float(b - d))

                    if dxs and dys:
                        # --- Movement Estimation ---
                        # We use the MEDIAN displacement to ignore 'outliers' (e.g., a moving car
                        # that doesn't represent the ground movement).
                        median_dx = float(np.median(dxs))
                        median_dy = float(np.median(dys))

                        # If the camera sees the ground moving 'Left', the drone is moving 'Right'.
                        drone_dx_pixels = -median_dx
                        drone_dy_pixels = -median_dy

                        # Convert pixel delta to meters
                        drone_dx_meters = drone_dx_pixels * self.scale_factor
                        drone_dy_meters = drone_dy_pixels * self.scale_factor

                        # --- Geographic Math ---
                        # Calculate change in Latitude
                        d_lat = (drone_dy_meters / METERS_PER_DEGREE_LAT) * -1

                        # Calculate change in Longitude (must account for latitude, as lines
                        # of longitude get closer together near the poles).
                        d_lon = drone_dx_meters / (METERS_PER_DEGREE_LAT * math.cos(math.radians(current_lat)))

                        current_lat += d_lat
                        current_lon += d_lon

                        self.trajectory_points.append((current_lon, current_lat))

                    # Update baseline for next frame
                    old_gray = frame_gray.copy()
                    p0 = good_new.reshape(-1, 1, 2)

                    # If we've lost too many points, find new ones
                    if len(p0) < 20:
                        p0 = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)
                else:
                    # If no points tracked at all, try to re-initialize features
                    p0 = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)
                    if p0 is None:
                        break

        cap.release()

        # Wrap points into a GeoJSON LineString for frontend mapping
        line = LineString(self.trajectory_points)
        return json.dumps(line.__geo_interface__)