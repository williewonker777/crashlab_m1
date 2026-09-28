#!/usr/bin/env python3
"""Read two live RGB-D pairs and visualize the supplied crashlab_vslam frontend.

No motion commands, TF broadcasts, parameter changes, or SLAM nodes are started.
Run from the configured ALICE M1 ROS environment. The input source is unchanged.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
import message_filters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=Path("/home/wonker/crashlab_vslam"))
    ap.add_argument("--output", type=Path, default=Path("assets/img/vslam-results"))
    args = ap.parse_args()
    sys.path.insert(0, str(args.source))
    from crashlab_vslam.camera import PinholeCamera
    from crashlab_vslam.frontend import RGBDFrontend
    from crashlab_vslam.node import SENSOR_QOS, VslamNode
    from crashlab_vslam import geometry as g

    rclpy.init()
    node = Node("lecture3_readonly_result_capture")
    infos, pairs = [], []
    info_sub = node.create_subscription(CameraInfo, "/aeirobot/vslam_left_camera_info", infos.append, SENSOR_QOS)
    rgb_sub = message_filters.Subscriber(node, Image, "/aeirobot/vslam_left_image", qos_profile=SENSOR_QOS)
    depth_sub = message_filters.Subscriber(node, Image, "/aeirobot/vslam_depth", qos_profile=SENSOR_QOS)
    sync = message_filters.ApproximateTimeSynchronizer([rgb_sub, depth_sub], 10, .02)
    stamp = lambda m: m.header.stamp.sec + m.header.stamp.nanosec * 1e-9

    def receive(rgb, depth):
        if infos and (not pairs or stamp(rgb) - stamp(pairs[-1][0]) >= .45):
            pairs.append((rgb, depth, infos[-1]))

    sync.registerCallback(receive)
    deadline = time.monotonic() + 30
    while len(pairs) < 2 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=.1)
    node.destroy_node()
    rclpy.shutdown()
    if len(pairs) < 2:
        raise SystemExit("No two synchronized RGB-D pairs within 30 seconds; no figures written.")

    cam = PinholeCamera.from_camera_info(pairs[0][2])
    decoder = SimpleNamespace(cam=cam)
    frames, rgb_arrays = [], []
    frontend = RGBDFrontend(cam)
    for rgb, depth, info in pairs:
        if rgb.encoding != "rgb8" or rgb.step != rgb.width * 3:
            raise SystemExit("This capture expects the observed packed rgb8 input.")
        if depth.encoding != "32FC1" or depth.step != depth.width * 4 or depth.is_bigendian:
            raise SystemExit("This capture expects the observed little-endian packed 32FC1 depth.")
        gray = VslamNode.decode_gray(decoder, rgb)
        z = VslamNode.decode_depth(decoder, depth)
        frames.append(frontend.make_frame(stamp(rgb), gray, z))
        rgb_arrays.append(np.asarray(rgb.data, dtype=np.uint8).reshape(rgb.height, rgb.width, 3))
    cv2.setRNGSeed(7)
    motion = frontend.estimate_motion(*frames)
    ia, ib = frontend.match(*frames)
    if not motion.ok:
        raise SystemExit(f"Captured pair failed frontend validation: {motion.reason}")
    transformed = g.transform_points(g.inverse(motion.T_ref_cur), frames[0].xyz[ia])
    errors = np.linalg.norm(cam.project(transformed) - frames[1].uv[ib], axis=1)
    good = np.flatnonzero(errors <= frontend.ransac_px)
    selected = good[np.linspace(0, len(good) - 1, min(32, len(good))).astype(int)]

    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 16, "axes.titlesize": 20, "font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    ax[0].imshow(rgb_arrays[0]); ax[0].set_title("RGB input · 1280 × 720"); ax[0].axis("off")
    z = frames[0].depth
    zm = np.ma.masked_where(~np.isfinite(z) | (z <= 0), z)
    cmap = plt.get_cmap("viridis").copy(); cmap.set_bad("#e6e8ed")
    im = ax[1].imshow(zm, vmin=0, vmax=8, cmap=cmap)
    ax[1].set_title("Depth · display range 0–8 m"); ax[1].axis("off")
    fig.colorbar(im, ax=ax[1], shrink=.7, label="Z [m]")
    fig.savefig(args.output / "live-input.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    for i in range(2):
        ax[i].imshow(frames[i].gray, cmap="gray", vmin=0, vmax=255)
        ax[i].set_title(f"{'Reference' if i == 0 else 'Current'} · t = {frames[i].stamp:.2f} s")
        ax[i].axis("off")
    for k in selected:
        a, b = frames[0].uv[ia[k]], frames[1].uv[ib[k]]
        for axis, p in zip(ax, [a, b]):
            axis.plot(p[0], p[1], "o", ms=4, color="#40e1e5", mec="#17215e", mew=.4)
        line = ConnectionPatch(a, b, "data", "data", axesA=ax[0], axesB=ax[1],
                               color="#40e1e5", alpha=.45, lw=.8)
        fig.add_artist(line)
    fig.savefig(args.output / "live-matches.png", dpi=140)
    plt.close(fig)

    source_files = ["camera.py", "frontend.py", "node.py", "vo.py", "slam.py", "posegraph.py", "slam_node.py", "evaluate.py", "replay.py"]
    report = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "mode": "Read-only live topic capture; unchanged crashlab_vslam frontend; two frames only",
        "source_sha256": {name: hashlib.sha256((args.source / "crashlab_vslam" / name).read_bytes()).hexdigest() for name in source_files},
        "width": cam.width, "height": cam.height,
        "camera": {name: getattr(cam, name) for name in ["fx", "fy", "cx", "cy"]},
        "frame_id": pairs[0][0].header.frame_id,
        "encodings": [pairs[0][0].encoding, pairs[0][1].encoding],
        "stamps": [f.stamp for f in frames],
        "pair_dt_ms": [round(abs(stamp(a) - stamp(b)) * 1000, 6) for a, b, _ in pairs],
        "valid_depth_ratio": float((np.isfinite(z) & (z > 0)).mean()),
        "features": [f.n_features for f in frames], "valid_features": [f.n_valid for f in frames],
        "depth_cut_m": [f.depth_cut for f in frames],
        "matches": motion.n_matches, "inliers": motion.n_inliers,
        "inlier_ratio": motion.inlier_ratio,
        "reprojection_median_px": float(np.median(errors)),
        "displayed_correspondences": len(selected),
        "display_rule": "At most 32 correspondences with reprojection error <= 3 px after refinement",
        "motion_ok": bool(motion.ok),
    }
    (args.output / "live-capture.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
