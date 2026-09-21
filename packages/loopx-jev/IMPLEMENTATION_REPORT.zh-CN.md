# Jev 分支实验实现与交接报告

[English](IMPLEMENTATION_REPORT.md)

**状态：独立实验归档，不申请合入 main，不建议升级为默认能力。**
本报告随完整实现保存，供复查和后续独立研究。RFC #4749 的讨论材料接纳不等于
运行时代码采用；此分支不修改该决定，也不要求上游持续维护实验。

## 版本与接收方式

- 原上游实现基线：`04ba65ac1a37c94d964adeedf3ff1f125c5ffe12`。
- 个人集成基线：`7fef13c73ab68e25878584e0ed61017a4bafa990`。
- 本报告对应已测实现：`3b4c1e27f1b2ed2227ee7cb105b57b7f1c69ad52`。
- 归档来源：[songoow/loopx:codex/jev-experiment-archive](https://github.com/songoow/loopx/tree/codex/jev-experiment-archive)。
- 实现讨论：[个人分支 PR #1](https://github.com/songoow/loopx/pull/1)，目标为个人实验集成分支，不是上游 main。
- 上游背景：[RFC #4749](https://github.com/loopx-project/loopx/pull/4749)。

当前发布账号没有上游写权限；来源分支不等于已建立上游分支。维护者如愿接收，可将
该完整历史另存为上游 `codex/jev-experiment-archive`，无需合并或变基到 main。
先核对来源 head 和目标分支不存在，再创建新 ref；不要强推或覆盖已有分支：

```bash
git fetch https://github.com/songoow/loopx.git refs/heads/codex/jev-experiment-archive
git show --no-patch --format=fuller FETCH_HEAD
git push https://github.com/loopx-project/loopx.git FETCH_HEAD:refs/heads/codex/jev-experiment-archive
```

接收后核对两个远端分支 SHA 相同。这里是保存实验历史，不是 main 兼容性认证或产品
合并流程。未来若重新考虑产品化，应另开范围明确的提案和真实任务评估。

## 已实现的部分

| 范围 | 实际交付 | 边界 |
|---|---|---|
| D1–D6 | `loopx-jev assess` 有限辅助判断、版本化输入和宿主读证据 | 不自动接管原生 Agent 或各 owner |
| D7 | scoped-gate fallback 中消费合法同组偏好 | 不是所有 Todo 的统一选择器 |
| D8 | Explore 候选规划后、原准入前消费偏好 | 不启动 worker；新证据策略限 width=1 |
| 开关与失败 | off/shadow/assist、期限、预算、无自动重试、过期/缓存撤销 | 关闭不撤销已经执行工作或已发生费用 |
| 实验证据策略 | `evidence_atomic` 分离充分性、贡献与采用判断 | pairwise 仍是默认，实验未显示改进 |

安装、原命令 capture/run、关闭与卸载见 [中文使用说明](README.zh-CN.md)；新策略
输入和回退见 [证据策略说明](EVIDENCE_RANKING.zh-CN.md)。不新增执行、权限、验收、
结算权，不改变原 gate、quota、资源与政策等价边界。

## 结果：选择变化不等于交付收益

最新比较冻结 24 个回归样例及 8 个新增样例，共 10 个语义家族的方向/排列变体。
不是 32 个独立真实工程任务；证据文件内容为合成事实。下表仅计每方向 8 个存在
唯一更优候选的样例，按原 owner 最终选择评分，包含弃权后的原策略回退。

| 方案 | D7 命中 | D8 命中 |
|---|---:|---:|
| 原 owner | 1/8 | 4/8 |
| pairwise + Jev | 4/8 | 7/8 |
| evidence_atomic + Jev | 1/8 | 4/8 |
| 同材料受限 Codex + atomic reducer | 8/8 | 8/8 |

旧 Jev 共 32 次调用；新 Jev 28 次调用、4 次联网前结构拒绝。新 Jev 26 次弃权、
2 次 `invalid_response_or_local_io`，没有可采用建议，因此命中来自原 baseline。
错误类别无法区分协议与本地 IO，不能断言是服务故障。Codex 28 次有限判断加相同
4 次结构拒绝；其标签 one-hot 适配不是模型概率。没有因负结果删例、降阈值或重试。

合并选择/等价/弃权/结构拒绝的预设行为匹配分别为 27/32、19/32、32/32；此数值
混合结构检查与模型判断，不能叫生产准确率。最新轮次未执行所选编码任务。

较早的真实 Codex 工作对照中，D1–D6 六对 off/assist 都完成 6/6，D7/D8 四对都
完成 4/4，独立验收和破坏副本检查通过。原 Agent 可以自行纠正较差排序。尚未观察到
额外完成案例或稳定加速，详见 [历史验证与范围](VALIDATION.zh-CN.md)。

## 耗时与质量验证

| 最新实际调用耗时 | 次数 | 中位数 ms | P95 ms |
|---|---:|---:|---:|
| pairwise Jev | 32 | 778.695 | 1169.586 |
| evidence_atomic Jev | 28 | 969.471 | 1104.821 |
| 受限 Codex | 28 | 9701.111 | 13032.679 |

Jev 包含读证据、评估封装、网络/子进程、落盘与 owner 消费；Codex 为进程启动到
退出，不含 owner 消费。两套 harness 不同，不能将比值称为纯推理加速。P95 使用
nearest-rank；纳秒计数不表示纳秒精度，单轮小样本不是 SLA。美元费用未知。
Jev 固定 `jev-1.13.0`；Codex 请求 `gpt-6-astra` / medium，实际小版本不可见。

Jev 读证据/评估/owner 消费阶段中位数：旧策略 1.791/751.260/23.844 ms，新策略
1.387/942.790/23.047 ms。各阶段独立取中位数，不能相加代替总中位数。

本地相关 Python 250 passed、TypeScript 32 passed；最终新增策略复测 27 passed。
包括真实 CLI、File/SQLite、关闭差分、响应协议、过期输入和缓存撤销。修改的产品
文件及新测试 Ruff 通过；新模块 strict mypy 通过。整个可选包 strict mypy 仍有
75 个错误，同配置基线为 80 个；不能称全包静态检查或全仓 CI 通过。

真实模型实验不依赖 CI；CI 仅运行无凭证的确定性回归。原始轨迹、私有文件、密钥和
本地运行材料不随归档发布。公开聚合结果是实验记录，不是第三方独立复现；仓库中的
演示及测试可复查接入行为，但不完整复现私有实验运行。

## 后续状态

此次以分支归档结束，不向 main 提实现合并请求，也不预设上游维护责任。证据策略
不升级默认。若后续继续，应另行冻结真实事实样例，定位证据充分性误判，再比较完整
Agent 流程的最终验收、成本和耗时。Claude、长期恢复、全局 Todo、PostgreSQL 资格、
多 worker 组合优化及真实 packed/separate 提问等价性均未验证。
