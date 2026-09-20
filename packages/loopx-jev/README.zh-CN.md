# Jev 可选排序试点：个人分支实现

本分支实现两个明确接缝，不把上游 RFC 的讨论接纳写成主干采用批准。
[English](README.md) · [验证边界](VALIDATION.md)

## 已实现的范围

D7 接入实际的 scoped-gate Todo fallback：原 TypeScript owner 判断当前候选，
只在同优先级、同策略组内消费完整偏好。它不是全部 Todo 或原生 Agent 的统一选择器。

D8 在原 Explore profile/router/bundle 生成后消费偏好，再运行原 scheduler、资源、
依赖和写作用域冲突判断。它不是在最终 JSON 上装饰性排序；同时不改写现有 confidence、
evidence units 或 router 回报。原 dry-run 指标仍然只是估计，不是 Jev 收益测量。

`off` 是默认：不读 key、不加载传输、不联网、不创建 Jev 文件、不构建大快照。
`shadow` 先运行原命令，再对之前保存的候选作判断，不把建议发给工作 Agent；整个
显式命令仍等待报告，因此不宣称零开销或 L1 observer 资格。
`assist` 在原入口之前生成偏好，实际消费时重新核对当前 owner 快照、目标/来源版本、
配置和材料；不匹配则沿当前原策略继续。并列保持原次序；弃权、缺答案、循环和错误
不会变成新权限。途中关闭阻止后续消费，但不撤销已经执行的工作、已发送数据或费用。

## 安装与离线演示

在这个分支的仓库根目录，使用 Python 3.11+、Node 22.18+ 和隔离环境：

```bash
uv venv .venv-jev
uv pip install --python .venv-jev/bin/python -e '.[test]' -e packages/loopx-jev
.venv-jev/bin/loopx-jev demo --output-dir .local/jev/demo-001
```

每次使用新目录。演示调用真实 TS selector、Explore planner 和独立子进程产物读回；
默认模型回复明确标为 `fixture_injected`。完整 quota/Explore CLI、File/SQLite、
拒绝缺失产物以及独立验收后的 canonical Todo 完成由测试另外验证。
这不代表真实 Codex/Claude 已运行，更不代表模型质量或完整 Turn 结算已验证。

## 实际使用

先在忽略的 `.local/jev/` 中准备显式配置和目标依据。完整参数见英文说明。
使用相同 cwd 和完全相同的原始 LoopX 参数执行以下两步：

```bash
.venv-jev/bin/loopx-jev init-run .local/jev/run-001 --max-requests 20
.venv-jev/bin/loopx-jev capture --output .local/jev/capture-001.json -- \
  --format json --registry /your/private/registry.json \
  --runtime-root /your/private/runtime quota should-run \
  --goal-id your-goal --agent-id your-agent
.venv-jev/bin/loopx-jev run --config .local/jev/config.json \
  --capture .local/jev/capture-001.json --basis .local/jev/basis.json \
  --run-dir .local/jev/run-001 --report .local/jev/report-001.json -- \
  --format json --registry /your/private/registry.json \
  --runtime-root /your/private/runtime quota should-run \
  --goal-id your-goal --agent-id your-agent
```

D8 将两次的原始命令同时替换为现有 `explore worker-branch-plan` 和相同参数。
必须提供明确 registry/runtime/goal。工具不创建或提升活动 Goal，不启用 Explore，
不替用户授予 spawn 权限。capture 执行原命令，原来配置的 turn-start 行为仍可能发生；
它不是全局无副作用模式。采集前后来源变化时须重新采集。

复制 `examples/config.off.json`，选择 `off`、`shadow` 或 `assist`。
启用需要明确固定模型和 `allow_egress=true`；持有 key 不是上传授权。
凭证只使用环境变量 `TYPESAFE_API_KEY`，不写到配置、Git 或命令行参数中。
请求和候选数量、并发数、字节、整个子进程期限都有上限，自动重试为零。
示例阈值 0.6 是待评估参数，不是安全证明。

`basis.json` 含真实目标 ID、objective、acceptance，以及可选 non_goals/horizon/
already_known 和最多八个本地证据引用。工具实际读取文件并绑定版本，但 operator
研究说明不替代原系统的验收权威。来源绑定包括 registry、canonical provider revision
或旧状态文件，并不是跨存储原子事务。D8 只排除展示字段 generated_at，保留真正的
frontier、任务、profile、router 和资源变化。

## 真实 Jev 调用

已在聊天中出现的 key 应先轮换。不要再次粘贴到提交、PR 或脚本里。
在本机交互式读取到环境变量后，可执行：

```bash
.venv-jev/bin/loopx-jev demo --live --model jev-1.13.0 \
  --output-dir .local/jev/live-001
```

请先确认账号支持这个固定模型。此命令最多两次调用，只发送合成演示材料。
端点固定为 TypeSafe HTTPS；不跟随重定向，不用环境代理，不自动换模型，不记录错误响应正文。
未获有效回复时 live 演示返回非零；弃权与服务失败分开显示。查看 comparison.json 的
assessments，不把一次 HTTP 成功当作效果证据。本次开发环境 DNS 不可用，尚无真实 Jev 质量结果。

## 并发、恢复与关闭

多个请求共享私有 run manifest 的原子预约预算。同一请求重复时不重发；结果详情被
删除后，预约仍然存在。不确定是否发出的请求不自动重试。删除整个 run 后必须显式
初始化一个新的预算，这不构成跨删除或跨 run 的 exactly-once 保证。

设置 mode=off，或直接使用原 loopx 命令。已启动的合法工作不会因为关闭而回滚。
卸载 `loopx-jev-pilot` 后原路径继续可用；不要误删活动 Goal、receipt 或 lease。
本实现没有自动安装 Codex/Claude hook，没有额外 manager、守护进程或 native Goal driver。
原生宿主可显式使用这些命令，并依原有权限继续工作；其实际采用率和长时执行仍需单独验证。

报告中的 preference_consumed 只说明实际选择接缝用了偏好，不是 worker 启动、
独立接受或 Goal 完成回执。完整实验要另外记录真实执行、领域验收、费用和无增量案例。
