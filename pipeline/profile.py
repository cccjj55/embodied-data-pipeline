"""Profile a directory of demonstration episodes and write a dataset card.

Answers, in numbers: how many episodes, how long, at what rate, what does the
action space look like, and how often did the recorder drop frames.

    python pipeline/profile.py --data data
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def load_episode(path: Path) -> list[dict]:
    frames = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (p / 100.0)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    return float(ordered[lo] * (1 - (rank - lo)) + ordered[hi] * (rank - lo))


def describe_action(episodes: list[list[dict]]) -> list[dict]:
    if not episodes:
        return []
    dims = len(episodes[0][0]['action'])
    stats = []
    for dim in range(dims):
        values = [f['action'][dim] for ep in episodes for f in ep]
        mean = statistics.fmean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        stats.append({
            'dim': dim,
            'mean': round(mean, 4),
            'std': round(std, 4),
            'min': round(min(values), 4),
            'max': round(max(values), 4),
        })
    return stats


def analyse(data_dir: Path) -> dict:
    paths = sorted(data_dir.glob('episode_*.jsonl'))
    episodes = [load_episode(p) for p in paths]
    episodes = [ep for ep in episodes if ep]

    durations, dts, gaps = [], [], 0
    total_frames = 0
    for ep in episodes:
        ts = [f['t'] for f in ep]
        durations.append(ts[-1] - ts[0])
        total_frames += len(ep)
        step_dts = [b - a for a, b in zip(ts, ts[1:]) if b > a]
        dts.extend(step_dts)
        if step_dts:
            threshold = 2.5 * statistics.median(step_dts)
            gaps += sum(1 for d in step_dts if d > threshold)

    median_dt = statistics.median(dts) if dts else 0.0
    return {
        'episodes': len(episodes),
        'frames': total_frames,
        'total_duration_s': round(sum(durations), 2),
        'duration_mean_s': round(statistics.fmean(durations), 2) if durations else 0.0,
        'hz_median': round(1.0 / median_dt, 1) if median_dt else 0.0,
        'dt_p50_ms': round(percentile(dts, 50) * 1e3, 1),
        'dt_p99_ms': round(percentile(dts, 99) * 1e3, 1),
        'gaps': gaps,
        'action_stats': describe_action(episodes),
    }


def to_markdown(info: dict) -> str:
    lines = [
        '# Dataset profile / 数据画像',
        '',
        '| 指标 | 值 |',
        '| --- | --- |',
        f"| episode 数 | {info['episodes']} |",
        f"| 总帧数 | {info['frames']:,} |",
        f"| 总时长 | {info['total_duration_s']:.1f} s |",
        f"| 单条平均时长 | {info['duration_mean_s']:.1f} s |",
        f"| 采样频率（中位数） | {info['hz_median']:.1f} Hz |",
        f"| dt P50 / P99 | {info['dt_p50_ms']:.1f} / {info['dt_p99_ms']:.1f} ms |",
        f"| 丢帧事件（dt > 2.5×P50） | {info['gaps']} |",
        '',
        '## 动作分布 / action statistics',
        '',
        '| dim | mean | std | min | max |',
        '| --- | --- | --- | --- | --- |',
    ]
    for s in info['action_stats']:
        lines.append(
            f"| {s['dim']} | {s['mean']:.4f} | {s['std']:.4f} | {s['min']:.4f} | {s['max']:.4f} |"
        )
    lines.append('')
    lines.append('> 判读：std 接近 0 的维度说明该维几乎不动（可能是死通道）；'
                 'min/max 明显超出物理范围说明有错误标签。')
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--out', default='reports/profile.md')
    args = ap.parse_args()

    info = analyse(Path(args.data))
    text = to_markdown(info)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + '\n', encoding='utf-8')

    print(f"episodes={info['episodes']} frames={info['frames']} "
          f"duration={info['total_duration_s']:.1f}s hz={info['hz_median']:.1f} "
          f"gaps={info['gaps']}")
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
