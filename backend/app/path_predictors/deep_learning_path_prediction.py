import json
import logging
import math
import os
import queue
import threading
from typing import List, Tuple

import cv2
import numpy as np
import torch
from shapely.geometry import LineString
from torchvision.models.optical_flow import (
    raft_large, Raft_Large_Weights,
    raft_small, Raft_Small_Weights
)
from tqdm import tqdm


class ThreadedVideoReader:
    """
    Runs in a background thread. Reads frames from disk, decodes them,
    applies the frame skip logic, preprocesses them into PyTorch tensors,
    and holds them in a Queue for the GPU to consume instantly.
    """

    def __init__(self, cap: cv2.VideoCapture, target_size: Tuple[int, int], frame_skip: int, preprocess_fn,
                 queue_size: int = 128):
        self.cap = cap
        self.target_size = target_size
        self.frame_skip = frame_skip
        self.preprocess_fn = preprocess_fn

        # The queue holds tuples of: (preprocessed_tensor, frames_read_since_last_yield)
        # This allows the main thread to keep the progress bar perfectly accurate.
        self.Q = queue.Queue(maxsize=queue_size)
        self.stopped = False

        # Start the background daemon thread
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        # We start at 1 because the main class already read the first frame manually
        frame_counter = 1
        frames_accumulated = 0

        while not self.stopped:
            ret, frame = self.cap.read()

            if not ret:
                self.Q.put((None, frames_accumulated + 1))  # Signal EOF
                self.stop()
                break

            frame_counter += 1
            frames_accumulated += 1

            # Universal Frame Skip
            if frame_counter % self.frame_skip != 0:
                continue

            # CPU Preprocessing (Resizing, Color conversion, Tensor creation)
            tensor = self.preprocess_fn(frame, self.target_size)

            # Put in queue. If queue is full (GPU is falling behind), this naturally blocks
            # and prevents RAM exhaustion.
            self.Q.put((tensor, frames_accumulated))
            frames_accumulated = 0

        self.cap.release()

    def read(self):
        return self.Q.get()

    def stop(self):
        self.stopped = True


class DeepLearningPathEstimator:

    def __init__(self, video_path: str, start_lat: float, start_lon: float, scale_factor: float = 0.1,
                 frame_skip: int = 5):
        self.video_path = video_path
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.scale_factor = scale_factor
        self.frame_skip = frame_skip
        self.trajectory_points: List[Tuple[float, float]] = [(start_lon, start_lat)]
        self.is_cuda_available = False

        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            logging.info("Hardware detected: Nvidia GPU (CUDA). Loading RAFT Large.")
            self.is_cuda_available = True
            weights = Raft_Large_Weights.DEFAULT
            self.transforms = weights.transforms()
            self.model = raft_large(weights=weights, progress=False).to(self.device)
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
            logging.info("Hardware detected: Apple Silicon (MPS). Loading RAFT Large.")
            weights = Raft_Large_Weights.DEFAULT
            self.transforms = weights.transforms()
            self.model = raft_large(weights=weights, progress=False).to(self.device)
        else:
            self.device = torch.device("cpu")
            torch.set_num_threads(os.cpu_count())
            logging.info("Hardware detected: CPU. Loading RAFT Small for performance.")
            weights = Raft_Small_Weights.DEFAULT
            self.transforms = weights.transforms()
            self.model = raft_small(weights=weights, progress=False).to(self.device)

        self.model.eval()

    def _preprocess_frame(self, frame: np.ndarray, target_size: Tuple[int, int]) -> torch.Tensor:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(rgb_frame, (target_size[1], target_size[0]))
        tensor = torch.from_numpy(resized_frame).permute(2, 0, 1)
        return tensor

    def _create_exclusion_mask(self, h: int, w: int, device: torch.device) -> torch.Tensor:
        mask = torch.ones((h, w), dtype=torch.bool, device=device)
        bottom_crop = int(h * 0.15)
        mask[-bottom_crop:, :] = False
        return mask

    def process_video(self, batch_size: int = 10) -> str:
        cap = cv2.VideoCapture(self.video_path)

        if not cap.isOpened():
            raise ValueError("Could not open video file")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Read the very first frame synchronously to establish baseline
        ret, old_frame = cap.read()
        if not ret:
            return json.dumps(LineString(self.trajectory_points).__geo_interface__)

        orig_h, orig_w = old_frame.shape[:2]
        target_size = (480, 640) if self.is_cuda_available else (240, 320)
        scale_x = orig_w / target_size[1]
        scale_y = orig_h / target_size[0]

        old_tensor = self._preprocess_frame(old_frame, target_size)

        current_lat = self.start_lat
        current_lon = self.start_lon
        METERS_PER_DEGREE_LAT = 111320.0

        valid_mask = None

        # --- Start the background I/O Thread ---
        # The background thread takes ownership of the `cap` object from here
        video_reader = ThreadedVideoReader(
            cap=cap,
            target_size=target_size,
            frame_skip=self.frame_skip,
            preprocess_fn=self._preprocess_frame,
            queue_size=128  # Holds up to ~128 preprocessed frames in RAM
        )

        with tqdm(total=total_frames, desc="Deep Learning Processing", unit="frame") as pbar:
            frames_since_update = 1
            eof_reached = False

            while not eof_reached:
                new_tensors = []
                frames_read_this_batch = 0

                # --- 1. Gather a batch instantly from the Queue ---
                while len(new_tensors) < batch_size:
                    tensor, read_count = video_reader.read()

                    if tensor is None:
                        eof_reached = True
                        frames_read_this_batch += read_count
                        break

                    frames_read_this_batch += read_count
                    new_tensors.append(tensor)

                if not new_tensors:
                    if frames_read_this_batch > 0:
                        frames_since_update += frames_read_this_batch
                    if frames_since_update > 0:
                        pbar.update(frames_since_update)
                    break

                # --- 2. Prepare the batches for the model ---
                batch1_list = [old_tensor] + new_tensors[:-1]
                batch2_list = new_tensors

                batch1_stack = torch.stack(batch1_list)
                batch2_stack = torch.stack(batch2_list)

                batch1, batch2 = self.transforms(batch1_stack, batch2_stack)
                batch1 = batch1.to(self.device, non_blocking=True)
                batch2 = batch2.to(self.device, non_blocking=True)

                # --- 3. Run Inference ---
                with torch.inference_mode():
                    if self.is_cuda_available:
                        with torch.autocast(device_type="cuda", dtype=torch.float16):
                            list_of_flows = self.model(batch1, batch2)
                    else:
                        list_of_flows = self.model(batch1, batch2)

                    predicted_flows = list_of_flows[-1]

                # --- 4. VECTORIZED GPU MATH ---
                if valid_mask is None:
                    valid_mask = self._create_exclusion_mask(
                        predicted_flows.shape[2],
                        predicted_flows.shape[3],
                        device=self.device
                    )

                valid_dx_batch = predicted_flows[:, 0, valid_mask]
                valid_dy_batch = predicted_flows[:, 1, valid_mask]

                median_dx_tensor = torch.median(valid_dx_batch, dim=1).values
                median_dy_tensor = torch.median(valid_dy_batch, dim=1).values

                median_dx_numpy = median_dx_tensor.cpu().numpy()
                median_dy_numpy = median_dy_tensor.cpu().numpy()

                # --- 5. CPU Geographic Math ---
                for i in range(len(new_tensors)):
                    median_dx_resized = float(median_dx_numpy[i])
                    median_dy_resized = float(median_dy_numpy[i])

                    median_dx = median_dx_resized * scale_x
                    median_dy = median_dy_resized * scale_y

                    drone_dx_pixels = -median_dx
                    drone_dy_pixels = -median_dy

                    drone_dx_meters = drone_dx_pixels * self.scale_factor
                    drone_dy_meters = drone_dy_pixels * self.scale_factor

                    d_lat = (drone_dy_meters / METERS_PER_DEGREE_LAT) * -1
                    d_lon = drone_dx_meters / (METERS_PER_DEGREE_LAT * math.cos(math.radians(current_lat)))

                    current_lat += d_lat
                    current_lon += d_lon

                    self.trajectory_points.append((current_lon, current_lat))

                old_tensor = new_tensors[-1]

                # --- 6. Progress Bar Updates ---
                frames_since_update += frames_read_this_batch
                if frames_since_update >= 120:
                    pbar.update(frames_since_update)
                    frames_since_update = 0

        # Ensure background thread is fully stopped
        video_reader.stop()

        line = LineString(self.trajectory_points)
        return json.dumps(line.__geo_interface__)
