"""30 FPS webcam + 60 Hz NI-DAQ collection. DI3 toggles record/pause; Ctrl+C saves.

Run: python record_dataset.py --view --pose front
Install: python -m pip install -r requirements-collection.txt
"""

import argparse
import csv
import json
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from modules.NiDAQ_controller import AI_CHANNELS, DI_CHANNELS, NiDAQJoysticks, OutputFormat

RATE = 60
CAMERA_FPS = 30


def stats(values):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return None
    return dict(zip(("median", "p95", "max"), map(float, np.percentile(a, [50, 95, 100]))))


def make_labels(folder, latency_ms=0):
    """Interpolate axes at estimated exposure time; never extrapolate missing data."""
    with (folder / "axes.csv").open(newline="") as f:
        axes = list(csv.DictReader(f))
    with (folder / "frames.csv").open(newline="") as f:
        frames = list(csv.DictReader(f))
    times = np.array([int(r["sample_est_ns"]) for r in axes], dtype=np.int64)
    fields = [f"axis{i}" for i in range(len(AI_CHANNELS))]
    values = np.array([[float(r[k]) for k in fields] for r in axes])
    with (folder / "labels.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "segment", "exposure_est_ns", "valid", "sample_left", "sample_right", *fields])
        for frame in frames:
            t = int(frame["delivery_ns"]) - round(latency_ms * 1e6)
            right = int(np.searchsorted(times, t, side="right"))
            left = right - 1
            valid = 0 <= left < right < len(times)
            if valid:
                valid = times[right] - times[left] <= 1.5 * 1e9 / RATE
            row = [frame["frame"], frame["segment"], t, int(valid)]
            if valid:
                alpha = (t - times[left]) / (times[right] - times[left])
                row += [axes[left]["sample"], axes[right]["sample"], *(values[left] * (1-alpha) + values[right] * alpha)]
            else:
                row += ["", "", *([""] * len(fields))]
            writer.writerow(row)


def record(args):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = Path(args.output) / f"{stamp}_{args.pose}"
    folder.mkdir(parents=True, exist_ok=False)
    stop = threading.Event()
    lock = threading.Lock()
    state = {"recording": args.auto_start, "segment": int(args.auto_start)}
    errors = queue.Queue()
    images = queue.Queue(maxsize=120)
    camera_times, capture_ms, encode_ms, queue_ms, daq_ms, daq_backlog = [], [], [], [], [], []
    cap, joystick, video = None, None, None
    threads = []
    metadata = dict(pose=args.pose, utc_start=stamp, daq_target_hz=RATE, camera_target_fps=CAMERA_FPS,
                    ai_channels=AI_CHANNELS, di_channels=DI_CHANNELS,
                    camera_latency_ms=args.camera_latency_ms,
                    synchronization="uncalibrated" if args.camera_latency_ms is None else "user_supplied_offset",
                    timestamp_note="perf_counter_ns; webcam delivery, not exposure. DAQ sample grid is estimated from task.start bracket, not a hardware timestamp.",
                    daq_phase_note="First sample assumed one period after task start midpoint; phase may differ by one sample period plus device delays.")
    started = time.perf_counter()
    interrupted = False
    try:
        backend = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "auto": cv2.CAP_ANY}[args.backend]
        cap = cv2.VideoCapture(args.camera, backend)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {args.camera}; try --backend msmf or --camera 1")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Best effort; many backends ignore this.
        print("Warming camera...", flush=True)
        for _ in range(30):
            ok, image = cap.read()
            if not ok:
                raise RuntimeError("Camera failed during warmup")
        height, width = image.shape[:2]
        metadata.update(camera=args.camera, backend=cap.getBackendName(), width=width, height=height,
                        camera_reported_fps=cap.get(cv2.CAP_PROP_FPS), opencv=cv2.__version__)
        joystick = NiDAQJoysticks(output_format=OutputFormat.FLOAT, deadzone=0, padding=0, sample_rate=RATE)
        metadata.update(daq_rate_hz=joystick.actual_sample_rate,
                        daq_start_before_ns=joystick.start_before_ns, daq_start_after_ns=joystick.start_after_ns)
        origin = (joystick.start_before_ns + joystick.start_after_ns) // 2
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2))

        def daq_worker():
            try:
                with (folder / "axes.csv").open("w", newline="", buffering=65536) as f:
                    writer = csv.writer(f)
                    writer.writerow(["sample", "sample_est_ns", "read_begin_ns", "read_end_ns", "backlog", *[f"volts{i}" for i in range(len(AI_CHANNELS))], *[f"axis{i}" for i in range(len(AI_CHANNELS))], *[f"di{i}" for i in range(len(DI_CHANNELS))]])
                    # Require release before accepting a press; debounce both edges.
                    previous = None
                    candidate = None
                    changed_at = time.perf_counter()
                    while not stop.is_set():
                        begin = time.perf_counter_ns()
                        data = joystick.read(preserve_samples=True)
                        end = time.perf_counter_ns()
                        backlog = joystick.task_ai.in_stream.avail_samp_per_chan
                        daq_ms.append((end - begin) / 1e6)
                        daq_backlog.append(backlog)
                        index = joystick.samples_read - 1
                        t = origin + round((index + 1) * 1e9 / joystick.actual_sample_rate)
                        writer.writerow([index, t, begin, end, backlog, *joystick.last_raw_ai, *data.ai, *data.di])
                        pressed = bool(data.di[3]) != args.button_active_low
                        now = time.perf_counter()
                        if pressed != candidate:
                            candidate, changed_at = pressed, now
                        if now - changed_at >= 0.05 and candidate != previous:
                            if previous is False and candidate:
                                with lock:
                                    state["recording"] = not state["recording"]
                                    if state["recording"]:
                                        state["segment"] += 1
                                    print("RECORDING" if state["recording"] else "PAUSED", flush=True)
                            previous = candidate
                        if backlog > RATE:
                            raise RuntimeError("DAQ reader is over one second behind; session timing invalid")
            except Exception as exc:
                errors.put(f"NI-DAQ: {exc}")
                stop.set()

        def camera_worker():
            try:
                while not stop.is_set():
                    begin = time.perf_counter_ns()
                    ok, image = cap.read()
                    delivery = time.perf_counter_ns()
                    if not ok:
                        raise RuntimeError("Camera stopped delivering frames")
                    camera_times.append(delivery)
                    capture_ms.append((delivery - begin) / 1e6)
                    with lock:
                        active, segment = state["recording"], state["segment"]
                    try:
                        images.put_nowait((image, begin, delivery, active, segment))
                    except queue.Full:
                        raise RuntimeError("Video writer cannot keep up; stopped rather than silently dropping frames")
            except Exception as exc:
                errors.put(f"Camera: {exc}")
                stop.set()

        threads = [threading.Thread(target=daq_worker, daemon=True), threading.Thread(target=camera_worker, daemon=True)]
        for thread in threads:
            thread.start()
        print(f"Dataset: {folder}\nDI3: start/pause. Ctrl+C: save and exit. Starts {'recording' if args.auto_start else 'paused'}.", flush=True)
        started = time.perf_counter()
        frame_index = 0
        with (folder / "frames.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "segment", "grab_begin_ns", "delivery_ns", "write_end_ns"])
            try:
                while not stop.is_set() or not images.empty():
                    if args.seconds and time.perf_counter() - started >= args.seconds:
                        stop.set()
                    try:
                        image, begin, delivery, active, segment = images.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    queue_ms.append((time.perf_counter_ns() - delivery) / 1e6)
                    if active:
                        if video is None:
                            video = cv2.VideoWriter(str(folder / "video.avi"), cv2.VideoWriter_fourcc(*"MJPG"), CAMERA_FPS, (width, height))
                            if not video.isOpened():
                                raise RuntimeError("Cannot create MJPEG AVI writer")
                        before_write = time.perf_counter_ns()
                        video.write(image)
                        end = time.perf_counter_ns()
                        encode_ms.append((end - before_write) / 1e6)
                        writer.writerow([frame_index, segment, begin, delivery, end])
                        frame_index += 1
                    if args.view:
                        preview = image.copy()
                        cv2.putText(preview, "RECORDING" if active else "PAUSED - DI3 to record", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255) if active else (0, 255, 0), 2)
                        cv2.imshow("Dataset camera | DI3 start/pause | Ctrl+C saves", preview)
                        cv2.waitKey(1)
            except KeyboardInterrupt:
                interrupted = True
                stop.set()
    except KeyboardInterrupt:
        interrupted = True
    except Exception as exc:
        errors.put(str(exc))
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=3)
        for thread in threads:
            if thread.is_alive():
                errors.put("Hardware worker did not stop within 3 seconds")
        if video is not None:
            video.release()
        if not any(t.is_alive() for t in threads):
            if cap is not None:
                cap.release()
            if joystick is not None:
                joystick.close()
        if args.view:
            cv2.destroyAllWindows()
        problems = []
        while not errors.empty():
            problems.append(errors.get())
        dt = np.diff(camera_times) / 1e6
        measured_fps = (len(camera_times)-1) * 1e9 / (camera_times[-1]-camera_times[0]) if len(camera_times) > 1 else 0
        report = dict(camera_measured_fps=measured_fps, camera_interval_ms=stats(dt),
                      camera_intervals_over_50ms=int(np.sum(dt > 50)),
                      camera_read_blocking_ms=stats(capture_ms), video_encode_ms=stats(encode_ms),
                      delivery_to_writer_ms=stats(queue_ms), daq_read_blocking_ms=stats(daq_ms),
                      daq_max_backlog=max(daq_backlog, default=0), camera_frames_delivered=len(camera_times),
                      errors=problems, interrupted=interrupted,
                      cadence_pass=bool(28.5 <= measured_fps <= 31.5 and len(dt) >= 60 and not np.any(dt > 75) and not problems),
                      alignment_verified=False,
                      note="Blocking read times are not sensor latency. A movement calibration is required to verify exposure/axis alignment.")
        (folder / "timing.json").write_text(json.dumps(report, indent=2))
        if (folder / "axes.csv").exists() and (folder / "frames.csv").exists() and not any(t.is_alive() for t in threads):
            make_labels(folder, args.camera_latency_ms or 0)
        print(f"Saved {folder}\nCamera: {measured_fps:.2f} FPS; cadence check: {report['cadence_pass']}; alignment: unverified", flush=True)
        if problems:
            raise RuntimeError("; ".join(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--view", action="store_true", help="Show live camera while paused and recording")
    parser.add_argument("--pose", default="camera", help="Short camera-pose name for this dataset")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--backend", choices=["dshow", "msmf", "auto"], default="dshow")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", default="datasets")
    parser.add_argument("--button-active-low", action="store_true", help="Use if DI3 reads 0 when pressed")
    parser.add_argument("--seconds", type=float, help="Optional timed session, including pauses")
    parser.add_argument("--auto-start", action="store_true", help="Start recording immediately (useful for benchmarks)")
    parser.add_argument("--camera-latency-ms", type=float, help="Measured delivery-minus-exposure offset; positive shifts labels earlier")
    parser.add_argument("--relabel", type=Path, help="Regenerate labels for an existing session with --camera-latency-ms")
    args = parser.parse_args()
    if args.relabel:
        if args.camera_latency_ms is None:
            parser.error("--relabel requires --camera-latency-ms")
        make_labels(args.relabel, args.camera_latency_ms)
        metadata_path = args.relabel / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata.update(camera_latency_ms=args.camera_latency_ms, synchronization="user_supplied_offset")
        metadata_path.write_text(json.dumps(metadata, indent=2))
        return
    if any(c in args.pose for c in '/\\:<>"|?*') or args.pose in (".", ".."):
        parser.error("--pose must be a simple folder name")
    if args.seconds is not None and (not np.isfinite(args.seconds) or args.seconds <= 0):
        parser.error("--seconds must be positive")
    if args.camera_latency_ms is not None and not np.isfinite(args.camera_latency_ms):
        parser.error("--camera-latency-ms must be finite")
    record(args)


if __name__ == "__main__":
    main()
