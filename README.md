# embodied-data-pipeline

**示教数据从「一堆文件」到「能训练的数据集」。**
*From raw demonstration logs to a trainable dataset, with the quality numbers written down.*

具身数据的真正难点不是采集，是**你凭什么相信这批数据**。这个仓库把三件事做成流水线：

```
profile  →  clean  →  dataset card
（画像）    （重采样/剔除）  （可发布的数据卡）
```

---

## 结果一览 / At a glance

| 项 | 现在 |
| --- | --- |
| 管线 | `profile`（画像）→ 重采样到 30 Hz → MAD 动作差分剔除 → `dataset_card.md` |
| 实测 | 3 episodes / 600 帧 / 30.1 Hz，剔除率 2.12%（**合成数据**，用于验证管线本身） |
| CI | 每次 push 跑完整管线（生成 → 画像 → 质检），产物缺失就红 |
| 设计取舍 | 先重采样再清洗（否则阈值随录制帧率漂移）；阈值用 MAD 而非固定上限（尺度自适应） |
| 待补 | 真实示教 20 条、LeRobot 导出、BC baseline 成功率 |

---

## 快速开始

```bash
python pipeline/make_synthetic.py --n-episodes 5      # 生成合成数据（用于自测）
python pipeline/profile.py --data data               # 数据画像 → reports/profile.md
python pipeline/quality.py --data data --target-hz 30  # 重采样 + 剔除 → clean/
```

## 数据格式

一条轨迹一个 JSONL 文件，每行一帧：

```json
{"t": 1.2333, "obs": [0.12, -0.03, 0.44, 0.01, 0.0, 0.98], "action": [0.31, -0.02, 0.05]}
```

`t` 为秒（单调递增），`obs` / `action` 为定长向量。选择 JSONL 是因为**人可读、可 diff**；
真实项目里应换成 Parquet / LeRobot 格式（见"路线"）。

## 两个脚本各自解决什么

| 脚本 | 回答的问题 | 输出 |
| --- | --- | --- |
| `profile.py` | 这批数据多少条、多长、频率多少、动作分布如何、有没有丢帧 | `reports/profile.md` |
| `quality.py` | 重采样到多少 Hz、剔除哪些帧、剔除率多少、为什么 | `clean/*.jsonl` + `reports/quality.md` |

**关键设计**：剔除规则是**基于动作差分的中位数绝对偏差（MAD）**，不是拍脑袋的阈值上限。
理由：动作幅值随任务变化，固定阈值会在大动作任务上误删；MAD 是尺度自适应的。

## 指标口径

| 指标 | 定义 |
| --- | --- |
| `gaps` | `dt > 2.5 × median(dt)` 的次数（丢帧/卡顿） |
| `resample_rate` | 目标控制频率（默认 30 Hz，可按策略频率调整） |
| `removal_rate` | 剔除帧数 / 重采样后帧数 |
| `outlier_reason` | 动作差分超 `k×MAD`（默认 k=6） |

## 状态

- [x] 合成数据生成器（自测用）
- [x] 画像脚本（episode 数 / 时长 / 频率 / 动作分布 / 丢帧）
- [x] 质检脚本（重采样 + MAD 剔除 + 报告）
- [ ] LeRobot 格式导出
- [ ] 真实示教数据（20 条）与 BC baseline 的成功率对照
- [ ] 剔除率 vs 成功率的敏感性曲线

> 诚实标注：仓库内的 `data/` 是**合成数据**（`pipeline/make_synthetic.py` 生成），
> `reports/` 里的两份报告也是基于合成数据跑出来的，用来证明流水线能跑通；
> 真实示教数据、剔除率依据与 BC 成功率待补。真实数据到位后，报告由脚本重新生成，不手改。

## License

MIT
