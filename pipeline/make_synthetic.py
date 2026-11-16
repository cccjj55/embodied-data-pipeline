"""Generate synthetic demonstration episodes so the pipeline can be tested.

The trajectories are deliberately imperfect: irregular timestamps, a few gaps
(dropped frames) and a handful of action spikes (bad labels). That way the
profile/quality scripts have something real to detect.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

OBS_DIM = 6
ACT_DIM = 3


def make_episode(episode: int, n_frames: int, rng: random.Random) -> list[dict]:
    frames = []
    t = 0.0
    yaw = rng.uniform(-0.2, 0.2)
    for i in range(n_frames):
        # irregular sampling: ~30 Hz with jitter, plus occasional long gaps
        dt = rng.gauss(1 / 30.0, 0.004)
        if rng.random() < 0.004:
            dt += rng.uniform(0.1, 0.4)          # dropped frames
        dt = max(dt, 1e-3)
        t += dt

        yaw += rng.gauss(0.0, 0.01)
        action = [
            round(0.25 * math.sin(i / 40.0) + rng.gauss(0, 0.01), 4),
            round(0.10 * math.cos(i / 55.0) + rng.gauss(0, 0.01), 4),
            round(0.30 * yaw, 4),
        ]
        if rng.random() < 0.006:                  # bad label
            action[0] += rng.choice([-1.5, 1.5])

        obs = [
            round(math.sin(i / 40.0), 4), round(math.cos(i / 55.0), 4),
            round(yaw, 4), round(0.01 * i, 4), 0.0, 0.98,
        ]
        frames.append({'t': round(t, 4), 'obs': obs, 'action': action})
    return frames


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--n-episodes', type=int, default=5)
    ap.add_argument('--frames', type=int, default=300)
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()

    out = Path(args.data)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    for ep in range(args.n_episodes):
        frames = make_episode(ep, args.frames, rng)
        path = out / f'episode_{ep:03d}.jsonl'
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            for frame in frames:
                fh.write(json.dumps(frame, ensure_ascii=False) + '\n')
        print(f'wrote {path} ({len(frames)} frames, {frames[-1]["t"]:.1f}s)')


if __name__ == '__main__':
    main()
