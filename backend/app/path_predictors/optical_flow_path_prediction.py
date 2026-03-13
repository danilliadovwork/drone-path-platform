import cv2
import numpy as np
import numpy.typing as npt
from typing import List, Tuple
import math
from shapely.geometry import LineString
import json
from tqdm import tqdm


class OpticalFlowPathEstimator:
    """
    Estimates the flight path of a drone from a video file using Optical Flow.
    """

    def __init__(self, video_path: str, start_lat: float, start_lon: float, scale_factor: float = 0.1):
        self.video_path = video_path
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.scale_factor = scale_factor
        self.trajectory_points: List[Tuple[float, float]] = [(start_lon, start_lat)]

    def process_video(self) -> str:
        cap = cv2.VideoCapture(self.video_path)

        if not cap.isOpened():
            raise ValueError("Could not open video file")

        # --- Get total frames for the progress bar ---
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        ret: bool
        old_frame: npt.NDArray[np.uint8]
        ret, old_frame = cap.read()
        if not ret:
            return json.dumps(LineString(self.trajectory_points).__geo_interface__)

        old_gray: npt.NDArray[np.uint8] = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)

        feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
        lk_params = dict(winSize=(15, 15), maxLevel=2,
                         criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))

        p0: npt.NDArray[np.float32] = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)

        current_lat = self.start_lat
        current_lon = self.start_lon
        METERS_PER_DEGREE_LAT = 111320.0

        # --- Wrap the processing loop with tqdm ---
        with tqdm(total=total_frames, desc="Optical Flow Processing", unit="frame") as pbar:
            frames_since_update = 1  # Account for the first frame already read

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # --- Batch Progress Bar Updates ---
                frames_since_update += 1
                if frames_since_update >= 120:
                    pbar.update(frames_since_update)
                    frames_since_update = 0

                frame_gray: npt.NDArray[np.uint8] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                p1: npt.NDArray[np.float32]
                st: npt.NDArray[np.uint8]
                err: npt.NDArray[np.float32]
                p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

                if p1 is not None:
                    good_new = p1[st == 1]
                    good_old = p0[st == 1]

                    dxs: List[float] = []
                    dys: List[float] = []

                    for i, (new, old) in enumerate(zip(good_new, good_old)):
                        a, b = new.ravel()
                        c, d = old.ravel()
                        dxs.append(float(a - c))
                        dys.append(float(b - d))

                    if dxs and dys:
                        median_dx = float(np.median(dxs))
                        median_dy = float(np.median(dys))

                        drone_dx_pixels = -median_dx
                        drone_dy_pixels = -median_dy

                        drone_dx_meters = drone_dx_pixels * self.scale_factor
                        drone_dy_meters = drone_dy_pixels * self.scale_factor

                        d_lat = (drone_dy_meters / METERS_PER_DEGREE_LAT) * -1
                        d_lon = drone_dx_meters / (METERS_PER_DEGREE_LAT * math.cos(math.radians(current_lat)))

                        current_lat += d_lat
                        current_lon += d_lon

                        self.trajectory_points.append((current_lon, current_lat))

                    old_gray = frame_gray.copy()
                    p0 = good_new.reshape(-1, 1, 2)
                else:
                    p0 = cv2.goodFeaturesToTrack(old_gray, mask=None, **feature_params)
                    if p0 is None:
                        break

                # --- Update the progress bar ---
                pbar.update(1)

        cap.release()

        line = LineString(self.trajectory_points)
        return json.dumps(line.__geo_interface__)