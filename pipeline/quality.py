"""Resample to a fixed control rate, drop label outliers, write a quality report.

Two decisions worth defending in an interview:

1. **Resample before cleaning.** The recorder's rate is not the policy's rate.
   Cleaning on the raw timestamps means the outlier threshold depends on how
   fast the recorder happened to run that day.
2. **Threshold from MAD, not a fixed limit.** Action magnitude differs per task,
   so a fixed cap either deletes good data (large motions) or keeps bad data
   (small motions). MAD of the first difference is scale free.

    python pipeline/quality.py --data data --target-hz 30 --out clean
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


def scaled_mad(values: list[float]) -> float:
    """Median absolute deviation scaled to be comparable with a std dev."""
    if len(values) < 2:
        return 0.0
    med = statistics.median(values)
    return 1.4826 * statistics.median(abs(v - med) for v in values)


def resample(frames: list[dict], target_hz: float) -> list[dict]:
    """Linear-interpolate obs/action onto a uniform grid."""
    keys = [k for k in frames[0] if k != 't']
    t0, t1 = frames[0]['t'], frames[-1]['t']
    n = max(2, int(round((t1 - t0) * target_hz)) + 1)
    grid = [t0 + i / target_hz for i in range(n)]

    out, j = [], 0
    for t in grid:
        while j < len(frames) - 2 and frames[j + 1]['t'] < t:
            j += 1
        a, b = frames[j], frames[j + 1]
        span = b['t'] - a['t']
        w = 0.0 if span <= 0 else min(1.0, max(0.0, (t - a['t']) / span))
        row = {'t': round(t, 6)}
        for key in keys:
            row[key] = [round(av + (bv - av) * w, 6) for av, bv in zip(a[key], b[key])]
        out.append(row)
    return out


def drop_outliers(frames: list[dict], k: float) -> tuple[list[dict], dict]:
    """Flag frames whose action first-difference exceeds k * scaled MAD."""
    if len(frames) < 3:
        return frames, {'removed': 0, 'dims': {}}

    dims = len(frames[0]['action'])
    diffs = [[abs(frames[i]['action'][d] - frames[i - 1]['action'][d]) for d in range(dims)]
             for i in range(1, len(frames))]
    thresholds = []
    for d in range(dims):
        column = [row[d] for row in diffs]
        mad = scaled_mad(column)
        thresholds.append(k * mad if mad > 0 else float('inf'))

    keep, removed_per_dim = [], {d: 0 for d in range(dims)}
    keep.append(frames[0])
    for i in range(1, len(frames)):
        row = diffs[i - 1]
        hit = [d for d in range(dims) if row[d] > thresholds[d]]
        if hit:
            for d in hit:
                removed_per_dim[d] += 1
        else:
            keep.append(frames[i])

    return keep, {
        'removed': len(frames) - len(keep),
        'dims': {f'dim{d}': n for d, n in removed_per_dim.items() if n},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    ap.add_argument('--out', default='clean')
    ap.add_argument('--report', default='reports/quality.md')
    ap.add_argument('--target-hz', type=float, default=30.0)
    ap.add_argument('--k', type=float, default=6.0, help='MAD multiplier')
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, total_in, total_out, total_removed = [], 0, 0, 0
    for path in sorted(Path(args.data).glob('episode_*.jsonl')):
        frames = load_episode(path)
        if len(frames) < 3:
            continue
        resampled = resample(frames, args.target_hz)
        kept, info = drop_outliers(resampled, args.k)
        with open(out_dir / path.name, 'w', encoding='utf-8', newline='\n') as fh:
            for frame in kept:
                fh.write(json.dumps(frame, ensure_ascii=False) + '\n')

        rate = info['removed'] / len(resampled) if resampled else 0.0
        total_in += len(resampled)
        total_out += len(kept)
        total_removed += info['removed']
        rows.append((path.name, len(frames), len(resampled), len(kept), rate, info['dims']))

    overall = total_removed / total_in if total_in else 0.0
    lines = [
        '# Quality report / 质检报告',
        '',
        f'- 目标频率：{args.target_hz:g} Hz',
        f'- 剔除规则：动作一阶差分 > {args.k:g} × 缩放 MAD',
        f'- 合计：重采样 {total_in:,} 帧 → 保留 {total_out:,} 帧，'
        f'剔除 {total_removed:,} 帧（{overall * 100:.2f}%）',
        '',
        '| episode | 原始帧 | 重采样后 | 保留 | 剔除率 | 触发维度 |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for name, raw, resampled_n, kept_n, rate, dims in rows:
        dims_text = ', '.join(f'{d}×{n}' for d, n in dims.items()) or '-'
        lines.append(f'| {name} | {raw} | {resampled_n} | {kept_n} | {rate * 100:.2f}% | {dims_text} |')
    lines += [
        '',
        '> 判读：剔除率突然升高通常有三种原因——标注错误、录制丢帧、或该段动作本身是快速切换。',
        '> 真实项目里应当抽样人工复核，而不是全信脚本。',
    ]

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'kept {total_out:,} / {total_in:,} frames (removed {overall * 100:.2f}%)')
    print(f'wrote {report} and {out_dir}/')


if __name__ == '__main__':
    main()
