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
    Background worker that decouples disk I/O and CPU preprocessing from GPU inference.

    This class runs a dedicated daemon thread to read video frames, apply frame skipping,
    and convert them into PyTorch tensors. By buffering these in a thread-safe Queue,
    the GPU never has to wait for the slower CPU/Disk operations to complete.
    """

    def __init__(self, cap: cv2.VideoCapture, target_size: Tuple[int, int], frame_skip: int, preprocess_fn,
                 queue_size: int = 128):
        self.cap = cap
        self.target_size = target_size
        self.frame_skip = frame_skip
        self.preprocess_fn = preprocess_fn

        # The queue holds tuples of: (preprocessed_tensor, frames_read_since_last_yield)
        # We cap the queue size to prevent RAM exhaustion if the GPU is slower than the CPU.
        self.Q = queue.Queue(maxsize=queue_size)
        self.stopped = False

        # Start the background daemon thread to begin filling the queue immediately
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        """Internal loop for the background thread."""
        # We start at 1 because the main class already read the first frame manually
        frame_counter = 1
        frames_accumulated = 0

        while not self.stopped:
            ret, frame = self.cap.read()

            if not ret:
                # Use None as a sentinel value to signal the main thread that the file is finished
                self.Q.put((None, frames_accumulated + 1))
                self.stop()
                break

            frame_counter += 1
            frames_accumulated += 1

            # --- Universal Frame Skip Logic ---
            # Only process every Nth frame to save computation time
            if frame_counter % self.frame_skip != 0:
                continue

            # --- CPU Preprocessing ---
            # Performs resizing and color space conversion on the CPU thread
            tensor = self.preprocess_fn(frame, self.target_size)

            # Put in queue. If queue is full, this call blocks, naturally throttling
            # the CPU reader to match the GPU's processing speed.
            self.Q.put((tensor, frames_accumulated))
            frames_accumulated = 0

        self.cap.release()

    def read(self):
        """External method to pull processed data from the background queue."""
        return self.Q.get()

    def stop(self):
        """Sets the stop flag to gracefully shut down the background thread."""
        self.stopped = True


class DeepLearningPathEstimator:
    """
    Analyzes drone video movement using Optical Flow neural networks (RAFT)
    to estimate a geographic flight path.
    """

    def __init__(self, video_path: str, start_lat: float, start_lon: float, scale_factor: float = 0.1,
                 frame_skip: int = 5):
        self.video_path = video_path
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.scale_factor = scale_factor  # Meters per pixel of camera movement
        self.frame_skip = frame_skip
        self.trajectory_points: List[Tuple[float, float]] = [(start_lon, start_lat)]
        self.is_cuda_available = False

        # --- Hardware Selection Logic ---
        # Prioritize Nvidia (CUDA), then Apple Silicon (MPS), then CPU fallback.
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

        # Set model to evaluation mode for inference efficiency
        self.model.eval()

    def _preprocess_frame(self, frame: np.ndarray, target_size: Tuple[int, int]) -> torch.Tensor:
        """Converts raw OpenCV images to normalized tensors suitable for the ML model."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(rgb_frame, (target_size[1], target_size[0]))
        # Convert HWC to CHW format
        tensor = torch.from_numpy(resized_frame).permute(2, 0, 1)
        return tensor

    def _create_exclusion_mask(self, h: int, w: int, device: torch.device) -> torch.Tensor:
        """
        Creates a boolean mask to ignore specific regions (like the bottom 15%
        where the drone's own shadow or landing gear might appear).
        """
        mask = torch.ones((h, w), dtype=torch.bool, device=device)
        bottom_crop = int(h * 0.15)
        mask[-bottom_crop:, :] = False
        return mask

    def process_video(self, batch_size: int = 10) -> str:
        """
        Main processing loop. Uses a batching strategy on the GPU for maximum throughput.
        """
        cap = cv2.VideoCapture(self.video_path)

        if not cap.isOpened():
            raise ValueError("Could not open video file")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # --- Baseline Setup ---
        ret, old_frame = cap.read()
        if not ret:
            return json.dumps(LineString(self.trajectory_points).__geo_interface__)

        orig_h, orig_w = old_frame.shape[:2]
        # Use higher resolution on GPU; smaller resolution on CPU for speed
        target_size = (480, 640) if self.is_cuda_available else (240, 320)

        # We need these to scale the small predicted flow back to the original video size
        scale_x = orig_w / target_size[1]
        scale_y = orig_h / target_size[0]

        old_tensor = self._preprocess_frame(old_frame, target_size)

        current_lat = self.start_lat
        current_lon = self.start_lon
        METERS_PER_DEGREE_LAT = 111320.0

        valid_mask = None

        # --- Start the background I/O Thread ---
        video_reader = ThreadedVideoReader(
            cap=cap,
            target_size=target_size,
            frame_skip=self.frame_skip,
            preprocess_fn=self._preprocess_frame,
            queue_size=128
        )

        with tqdm(total=total_frames, desc="Deep Learning Processing", unit="frame") as pbar:
            frames_since_update = 1
            eof_reached = False

            while not eof_reached:
                new_tensors = []
                frames_read_this_batch = 0

                # --- 1. Gather a batch instantly from the Queue ---
                # We pull multiple frames to process them simultaneously on the GPU
                while len(new_tensors) < batch_size:
                    tensor, read_count = video_reader.read()

                    if tensor is None:  # End of file sentinel
                        eof_reached = True
                        frames_read_this_batch += read_count
                        break

                    frames_read_this_batch += read_count
                    new_tensors.append(tensor)

                if not new_tensors:
                    # Final progress bar update on exit
                    if frames_read_this_batch > 0:
                        frames_since_update += frames_read_this_batch
                    if frames_since_update > 0:
                        pbar.update(frames_since_update)
                    break

                # --- 2. Prepare the batches for the model ---
                # batch1: [frame_t-1, frame_t, frame_t+1...]
                # batch2: [frame_t,   frame_t+1, frame_t+2...]
                batch1_list = [old_tensor] + new_tensors[:-1]
                batch2_list = new_tensors

                batch1_stack = torch.stack(batch1_list)
                batch2_stack = torch.stack(batch2_list)

                # RAFT requires specific normalization transforms
                batch1, batch2 = self.transforms(batch1_stack, batch2_stack)
                batch1 = batch1.to(self.device, non_blocking=True)
                batch2 = batch2.to(self.device, non_blocking=True)

                # --- 3. Run Neural Network Inference ---
                with torch.inference_mode():
                    if self.is_cuda_available:
                        # Use FP16 (Half Precision) on Nvidia GPUs to double speed
                        with torch.autocast(device_type="cuda", dtype=torch.float16):
                            list_of_flows = self.model(batch1, batch2)
                    else:
                        list_of_flows = self.model(batch1, batch2)

                    predicted_flows = list_of_flows[-1]

                # --- 4. Vectorized GPU Math ---
                # Calculate the median motion (displacement) of the entire image
                if valid_mask is None:
                    valid_mask = self._create_exclusion_mask(
                        predicted_flows.shape[2],
                        predicted_flows.shape[3],
                        device=self.device
                    )

                # Extract dx (horizontal) and dy (vertical) from the flow tensor
                valid_dx_batch = predicted_flows[:, 0, valid_mask]
                valid_dy_batch = predicted_flows[:, 1, valid_mask]

                # Median is more robust against moving objects (cars/people) than the mean
                median_dx_tensor = torch.median(valid_dx_batch, dim=1).values
                median_dy_tensor = torch.median(valid_dy_batch, dim=1).values

                # Bring data back from GPU to CPU for geographic calculations
                median_dx_numpy = median_dx_tensor.cpu().numpy()
                median_dy_numpy = median_dy_tensor.cpu().numpy()

                # --- 5. CPU Geographic Math ---
                for i in range(len(new_tensors)):
                    median_dx_resized = float(median_dx_numpy[i])
                    median_dy_resized = float(median_dy_numpy[i])

                    # Scale motion back to original video dimensions
                    median_dx = median_dx_resized * scale_x
                    median_dy = median_dy_resized * scale_y

                    # The drone moves in the opposite direction of the perceived camera flow
                    drone_dx_pixels = -median_dx
                    drone_dy_pixels = -median_dy

                    # Convert pixel displacement to physical meters
                    drone_dx_meters = drone_dx_pixels * self.scale_factor
                    drone_dy_meters = drone_dy_pixels * self.scale_factor

                    # Calculate change in Latitude and Longitude based on the Earth's curvature
                    d_lat = (drone_dy_meters / METERS_PER_DEGREE_LAT) * -1
                    d_lon = drone_dx_meters / (METERS_PER_DEGREE_LAT * math.cos(math.radians(current_lat)))

                    current_lat += d_lat
                    current_lon += d_lon

                    self.trajectory_points.append((current_lon, current_lat))

                # Last frame of this batch becomes the baseline for the next batch
                old_tensor = new_tensors[-1]

                # --- 6. Progress Bar Updates ---
                # Only update the UI bar every 120 frames to reduce UI overhead
                frames_since_update += frames_read_this_batch
                if frames_since_update >= 120:
                    pbar.update(frames_since_update)
                    frames_since_update = 0

        # Clean up background thread
        video_reader.stop()

        # Export result as a GeoJSON LineString
        line = LineString(self.trajectory_points)
        return json.dumps(line.__geo_interface__)