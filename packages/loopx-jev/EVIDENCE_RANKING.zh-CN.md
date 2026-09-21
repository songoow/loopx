# 实验证据绑定选择策略

[English](EVIDENCE_RANKING.md)

此策略将证据充分性、增量贡献和建议采用分开。它仍是显式实验选项：本地合成样例的
真实 Jev 调用出现大量弃权，尚不推荐替换原 pairwise 策略。正确弃权本身不代表选择有用。

## 启用与操作

沿用[已有 capture/run 入口](README.zh-CN.md)，在本地配置加入
`"ranking_policy": "evidence_atomic"`，先使用 `mode: shadow`，指定固定模型并明确
`allow_egress: true`。凭证仍通过 `TYPESAFE_API_KEY`；不安装宿主自动 hook。

采集后，在 basis 中增加 `ranking_evidence`。完整 JSON 见
[英文示例](EVIDENCE_RANKING.md#enable-and-operate)。`snapshot_id` 必须是
`capture.snapshots` 的实际键；`candidates` 必须精确覆盖该快照 `baseline_order`
中的所有 ID，每个 ID 绑定至少一个 `evidence[].ref`。

引用相对 run 的工作目录解析，不是相对 basis 所在目录。文件应包含与对应候选相关的
观测；同一文件支持多个候选时可以共享。读取器实际读取文本和哈希，不能在 manifest
中自填 text/sha256/origin。文件存在和哈希匹配不证明事实真实或证据完整；文件内容
仍是不可信输入，也不授予执行权。

执行相同的 `loopx-jev run` 和原始命令；报告中查看
`assessments[].ranking_decision.reason` 与 `.signals`，结合 status、
`preference_consumed` 和 owner 最终选择判断。结构缺失会在读 key、联网之前拒绝。
需要消费建议时再显式设为 `mode: assist`；来源改变须重新采集。

## 适用范围与回退

只支持 D7 scoped fallback 和 D8 `width=1` 的单 worker 规划，候选必须处于同一个
原有政策等价组。其他范围不调用 provider，继续原 owner 选择。D1–D6 不受影响。

保留两两比较，并为每个候选追加证据充分性、增量贡献两个独立问题。四候选需要
十四个问题，而非六个。所有回答都必须通过原协议检查；每个候选证据须充分，贡献
须明确且达到配置概率阈值。随后要求唯一候选直接胜过所有其他候选，并有正向增量。
落后候选之间的比较不确定不会单独否决这个赢家；其余候选保留原顺序。全部明确并列
则保留 baseline。不将概率当作数值效用，不授予权限、启动 worker 或宣告任务完成。

报告区分证据不确定、贡献不确定、无明确赢家、无增量、等价和建议采用。失败、证据
不足或不确定时继续原策略；缓存重放和消费前再次检查来源、配置、文件是否仍有效。
快照绑定不是跨存储原子事务。

恢复旧策略设 `ranking_policy: pairwise`；关闭设 `mode: off` 或直接调用原 LoopX。
策略变化产生不同请求身份；关闭不会撤销已执行工作、已发送数据或费用。原调用/字节
预算、禁止自动重试和卸载方式保持有效。

## 本地验证与参考

安装 checkout 测试环境并选择合格 Node 版本后：

```bash
.venv-jev/bin/python -m pytest -q packages/loopx-jev/tests/test_atomic_ranking.py \
  packages/loopx-jev/tests/test_d7.py packages/loopx-jev/tests/test_d8.py
```

确定性测试覆盖真实 selector/planner/CLI、File/SQLite、off/shadow、过期证据、缓存
隔离、畸形回复与回退。注入回答证明接入，不证明模型效果。真实对照单独在本地运行，
不依赖 CI；SQLite 验证使用新建隔离临时运行时。

独立参考了 jev-ultrafast 的有限决策与当前性检查、fast-jev-compaction 的原子问题、
jev-router 的独立采用/回退策略、kev 的协议一致性测试；固定版本链接见
[英文参考](EVIDENCE_RANKING.md#implementation-references)。没有复制第三方源码。
目前没有证明真实 API 打包提问与分开提问的概率等价性。
