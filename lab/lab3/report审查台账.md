# report.html 审查台账

- 审查对象：`report.html`（Codex 生成）
- 审查日期：2026-10-09
- 对照依据：Lab 03 讲义（11 个子任务 × 5 分）、`Uber-Jan-Feb-FOIL.csv` 实测统计、目录内的代码文件、`分析结论.md`
- 严重级别：**P0** 直接导致丢分或无法提交｜**P1** 很可能扣分或步骤会失败｜**P2** 准确性、规范或体验问题
- 状态：全部为「待处理」，本次只登记问题，未修改报告

## 一、总体结论

| 项目 | 结论 |
|---|---|
| 数据统计 | **准确**。总行程 4,130,230、59 天、最忙日 02-20 共 100,915 次、B02764 共 1,914,449 次、Top5 日期及柱状图比例，均已用原始 CSV 复核，结果一致 |
| 评分证据 | **全部缺失**。11 个证据位都是占位文字，没有任何截图或实测输出。按讲义的截图评分标准，当前得分实际为 0/55 |
| 结构 | 章节编号与讲义不一致，评分者难以逐项对照 |
| 技术内容 | 有 4 处会导致实际操作失败的错误（R-14、R-17、R-22、R-23），以及多处与讲义要求不符（Python 版本、缓存 key、Redis 连接写法） |
| 可信度 | 多处把"未运行验证"的行为写成了已完成的事实。本机未安装 pandas，`.venv` 中只有 pip，没有迹象表明代码运行过 |

## 二、问题明细

| 编号 | 位置 | 问题描述 | 级别 | 影响评分点 | 处理建议 | 状态 |
|---|---|---|---|---|---|---|
| R-01 | 全文 | 11 个证据位（A1–F2）都没有截图，只写了"补充截图"的提示 | P0 | 全部 55 分 | 实验完成后逐一放入带日期时间的截图；每张图配编号、说明和对应的评分条目 | 待处理 |
| R-02 | 全文章节 | 章节编号与讲义不一致：讲义是 Task 1（1.1–1.3）、Task 2 Docker、Task 3 Azure、Task 4 Redis、Task 5 监控；报告是 1 预处理（标为 10 分）、2 JMeter、3 Docker、4 Azure、5 Redis、6 监控 | P0 | 全部（评分者对照困难） | 按讲义的 Task / Subtask 编号和标题重排，JMeter 归入 1.3，各节分值与讲义一致 | 待处理 |
| R-03 | 提交清单 L13 | 写着提交 `report.html`，"需要 PDF 时"再打印；讲义**明确要求 PDF** | P0 | 提交合规 | 改为"导出 PDF 提交"；zip 内放 PDF，不放 HTML | 待处理 |
| R-04 | L3、L14 页眉页脚 | "Prepared" 日期由 JS 的 `new Date()` 在每次打开时生成，不是真实的完成日期；没有学生姓名、学号、课程节次 | P1 | 报告规范 | 改为固定的完成日期；补上姓名、学号、提交日期 | 待处理 |
| R-05 | 全文语言 | 正文为中文，而课程讲义为英文 | P1 | 可读性（评分者可能无法阅读） | **需 Robin 确认**提交语言；如需英文，整篇改写 | 待确认 |
| R-06 | L4、L5 引言和摘要 | "本报告完成实验所需……""连接后重复 timestamp 请求返回 cache"等，把未验证的行为写成了已完成的事实 | P1 | 学术诚信 / 可信度 | 只写已实测的内容；未实测的改为"待验证"，或在实测后再写 | 待处理 |
| R-07 | L6 1.1 代码块 | 代码片段与实际 `app.py` 不一致：缺少 `read_csv`、`IsWeekend` 这一行；`TripWeight` 的写法也和源码不同（源码有 `errors="coerce").fillna(1)`） | P1 | 1.1 | 直接从最终的 `app.py` 摘录代码，包含讲义要求的全部步骤 | 待处理 |
| R-08 | L6 证据位 A1 | 截图命令 `print(df.info())` 会多打印一个 `None`；讲义要求在 Ubuntu VM 中用 nano 编辑 `app.py` 后运行，报告中没有体现 | P2 | 1.1 | 改为 `python3 app.py --analyze`（或等价命令），并加一张 nano 编辑画面的截图 | 待处理 |
| R-09 | L7 1.2 | 缺少讲义要求的内容：`hourly_trips` 聚合、用 `idxmax()` 求高峰小时、按天和按小时的柱状图、热力图。表中只有天和基地维度；也没有给出星期几的分布这一有效结论 | P0 | 1.2 | 补齐 daily/hourly 聚合和 idxmax；补上 3 张图，加一张替代热力图；补充星期分析（周六日均 83,481 最高，周一 57,975 最低） | 待处理 |
| R-10 | L7 证据位 A2 | 写着"打开 `/analysis` 补充柱状图与热力图"，但 `/analysis` 只返回 JSON，**不会生成任何图** | P1 | 1.2 | 在 `app.py` 中实现画图（savefig），证据改为图片和运行截图 | 待处理 |
| R-11 | L7 证据位 A2 | 建议"用课程提供的明细 CSV 重跑"，但课程并没有提供明细 CSV，这属于臆测 | P2 | 1.2 | 删除；改为说明数据集是按天汇总的，因此 Hour 恒为 0，并说明采用的替代分析 | 待处理 |
| R-12 | 全文 | 没有披露预测逻辑的缺陷：`predict()` 按 Hour 匹配，而 Hour 恒为 0，导致不同 timestamp 的预测值基本相同 | P1 | 1.3、2.2、4.x（演示可信度） | 修改预测逻辑（如改为同星期几的日均），并在报告中说明模型的含义 | 待处理 |
| R-13 | L8 JMeter | 声称测试计划已配置好，但 CSV Data Set **缺少 `ignoreFirstLine=true`**，表头行会被当作数据，发出 `timestamp=date` 的请求并返回 400，Error % 不为 0 | P0 | 1.3 | 修复 jmx 后重跑；报告中写出 Ignore first line 的设置 | 待处理 |
| R-14 | L8 JMeter 命令 | 只给了无 GUI 模式命令（`-n`），而讲义要求截图 GUI 中的测试计划树和 Summary Report / View Results Tree | P1 | 1.3 | 证据改为在 GUI 中运行的截图；CLI 命令只留给持续压测使用 | 待处理 |
| R-15 | L8 JMeter | 示例中的 timestamp 一律是 ISO 格式 `2015-02-20T00:00:00`，而 JMeter 实际发送的是 CSV 中的 `1/1/2015` 格式；报告没有说明两者都能解析，也没提 URL 编码 | P2 | 1.3 | 统一示例格式；注明 URL Encode 设置 | 待处理 |
| R-16 | L9 3.1 Dockerfile | 写着"使用 Python slim"，回避了实际用的是 **python:3.11-slim**，而讲义要求 **Python 3.8 slim** | P0 | 2.1 | 把 Dockerfile 改为 3.8-slim（pandas 降到 2.0.3 等），报告中写明版本 | 待处理 |
| R-17 | L9 requirements | 没有提到 requirements 缺少 matplotlib、seaborn；讲义要求列出全部必需包 | P1 | 2.1 | 补齐依赖，报告附上完整清单 | 待处理 |
| R-18 | L9 | 小节编号为 3.1/3.2，且 3.2 标题是 "Local verification"；讲义对应的是 2.1 Dockerfile 和 2.2 Build and Run，要求 build 日志、run 状态、成功响应三类证据 | P1 | 2.1、2.2 | 按讲义重新命名，证据逐条对应 | 待处理 |
| R-19 | L10 Azure VM | 只说"推送镜像后"执行 pull，没有给出 tag/push 步骤；**没有提示本机为 arm64、需要构建 amd64 镜像**，照做在 Azure x86 VM 上会报 `exec format error` | P0 | 3.1、3.2、4.2 | 补充 `docker buildx build --platform linux/amd64 --push`，并加 `docker image inspect` 校验架构 | 待处理 |
| R-20 | L10 Azure VM | 验证用的是 `curl /`（健康检查），讲义要求通过公网 IP 调用 API 并截图浏览器或 Postman | P2 | 3.1 | 改为用浏览器或 Postman 调用 `/predict_traffic?timestamp=...` | 待处理 |
| R-21 | L10 VMSS | 只有一句描述：没有启动脚本内容、负载均衡规则和健康探测配置；也没说明短时压测（约 2 分钟）不足以触发扩缩容 | P1 | 3.2 | 补上 cloud-init 脚本、LB 和探测配置、扩缩容规则参数；准备 15–20 分钟的持续压测计划 | 待处理 |
| R-22 | L11 本地 Redis | 缓存 key 用的是 timestamp 的 SHA-256（`uber:prediction:<hash>`），讲义要求**以 timestamp 作为 key**，redis-cli 截图中看不出 timestamp | P1 | 4.1 | 改为 `predict:<timestamp>`；截图同时显示 KEYS 和 TTL | 待处理 |
| R-23 | L11 Azure Redis | 在 VM 的 shell 中 `export REDIS_URL=...` **不会传进 Docker 容器**，照做后容器仍连不上 Redis；而 `get_redis()` 会静默降级，于是**永远看不到 `source: cache`**。另外，密钥会留在 shell 历史中 | P0 | 4.2 | 改为 `docker run --env-file ~/redis.env`（文件权限 600）；在健康接口中显示 cache 是否启用 | 待处理 |
| R-24 | L11 Azure Redis | 连接方式用 `rediss://` URL，而不是讲义给出的 `redis.Redis(host, port=6380, password, ssl=True)`，评分者对照时会认为不一致 | P1 | 4.2 | 代码改为讲义的形式（参数从环境变量读取） | 待处理 |
| R-25 | L11 Azure Redis | 没有提醒 Basic C0 部署需 15–20 分钟、新建可能受限，以及需要确认已启用访问密钥认证 | P2 | 4.2 | 补充在风险提示中 | 待处理 |
| R-26 | L12 6.1 | 要求在 Azure Monitor 中对比 "Average response time"，但 VM/VMSS 内置指标**没有响应时间** | P1 | 5.1 | 响应时间改用两次 JMeter 结果对比，或接入 Application Insights；CPU 和扩缩容次数用 Azure Monitor | 待处理 |
| R-27 | L12 6.1 | "预期方向"一栏预设了"降低、减少"；本数据集计算成本很低，Azure Redis 走 TLS 有网络开销，响应时间不一定下降 | P2 | 5.1 | 如实填写实测值；如果收益不明显，说明原因 | 待处理 |
| R-28 | L12 6.2 清理命令 | `docker rm -f $(docker ps -aq)` 会**删除本机所有容器**，包括与本实验无关的容器，有破坏性 | P1 | 5.2（操作安全） | 只删除本实验的容器（按名称或 compose project） | 待处理 |
| R-29 | L12 6.2 清理命令 | 顺序错误：先 `compose down` 已删除 Redis 容器，再执行宿主机上的 `redis-cli FLUSHDB` 会连接失败（宿主机上不一定有 redis-cli，也没有本地 Redis） | P1 | 5.2 | 先 `docker compose exec redis redis-cli FLUSHALL`，再 down | 待处理 |
| R-30 | L12 6.2 Azure 清理 | `az vm delete` 不会删除磁盘、NIC、公网 IP、NSG；VMSS 的负载均衡和公网 IP 也会残留 | P2 | 5.2 | 删除整个资源组；如果是沙盒预置的资源组，就逐项删除，并用 `az resource list -g` 确认已清空 | 待处理 |
| R-31 | L13 提交清单 | 缺少"Redis 集成脚本"的明确对应项；提交 CSV 不是必需的（但无害） | P2 | 提交合规 | 清单按讲义逐项列出：PDF、Dockerfile、app.py、requirements.txt、jmx、Redis 脚本 | 待处理 |
| R-32 | L14 页脚 | 数据来源写的是 FiveThirtyEight GitHub，讲义写的是 Brightspace Course Resources | P2 | 规范 | 写"Brightspace 提供（原始来源 FiveThirtyEight uber-tlc-foil-response）" | 待处理 |
| R-33 | 全文 | 没有说明实验环境（Ubuntu VM 版本、JMeter 版本、Azure 区域和规格） | P2 | 报告完整性 | 增加一节"Environment" | 待处理 |

## 三、统计

| 级别 | 数量 | 编号 |
|---|---|---|
| P0 | 8 | R-01、R-02、R-03、R-09、R-13、R-16、R-19、R-23 |
| P1 | 15 | R-04、R-05、R-06、R-07、R-10、R-12、R-14、R-17、R-18、R-21、R-22、R-24、R-26、R-28、R-29 |
| P2 | 10 | R-08、R-11、R-15、R-20、R-25、R-27、R-30、R-31、R-32、R-33 |
| 合计 | 33 | |

## 四、已核实无误的内容

- 354 行、4 个字段、无缺失和重复行
- 总行程 4,130,230；59 天（2015-01-01 至 2015-02-28）
- Top5 日期：02-20 共 100,915、02-14 共 100,345、02-21 共 98,380、02-13 共 98,024、01-31 共 92,257；柱状图百分比与这些数值一致
- 最大基地 B02764 共 1,914,449
- 按 `trips` 加权、不按行数统计，这一处理思路是正确的
- 5.1 表格中写明"没有实测前不要填写具体数字"，没有编造数据

## 五、建议处理顺序

1. **先改代码**（R-12、R-13、R-16、R-17、R-22、R-23、R-24），否则后续截图都要重拍。
2. 本地完成 1.x、2.x、4.1 的实验并截图（R-01、R-09、R-10、R-14）。
3. Azure 部分（R-19、R-21、R-25、R-26）。
4. 最后按讲义结构重写报告并导出 PDF（R-02 至 R-07、R-11、R-15、R-18、R-20、R-27 至 R-33），语言待 R-05 确认。

---

## 六、进度检查（2026-10-09 11:10 MDT）

检查方式：本地文件变更、`screenshots/` 内容逐张查看、`az` 只读查询、对 VM 公网 API 发 GET 请求。

### 6.1 子任务进度

| 子任务 | 状态 | 实际情况 |
|---|---|---|
| 1.1 预处理 | 部分完成 | 数据处理正确（354 行、4,130,230 次行程）；但只有拼贴图中的文字，没有 `df.head()`、`df.info()`、`df.describe()` 的终端截图 |
| 1.2 分析与可视化 | 未完成 | 没有柱状图和热力图；`analysis-live.png` 只是一段 JSON，且看不到日期时间 |
| 1.3 JMeter | 部分完成 | 有 CLI 生成的 HTML 仪表盘（2,500 个请求、0 错误、平均 2.04 ms、42.15/s）；测试计划图不是 JMeter GUI 截图（R-35）；结果与提交的 jmx 对不上（R-37） |
| 2.1 Dockerfile | 未完成 | 仍是 `python:3.11-slim`，requirements 未改，也没有截图 |
| 2.2 构建并运行 | 未完成 | 没有 build/run 截图；本机没有安装 docker |
| 3.1 Azure VM | 部署完成，缺证据 | VM `cpsy300-lab03-vm2`（eastus，D2s_v3，Ubuntu 24.04）正在运行；`http://20.84.66.238:5000/` 已实测可访问；缺 `docker ps` 截图和浏览器访问公网 IP 的截图；"NSG 截图"实际不是 NSG（R-34） |
| 3.2 VMSS | 未开始 | 订阅中没有 VMSS |
| 4.1 本地 Redis | 部分完成 | 在 VM 上用 Redis 容器验证了 compute→cache；但缓存 key 是哈希值（R-22），证据为拼贴文字 |
| 4.2 Azure Redis | 进行中 | `cpsy300-redis`（Basic C0、6380 SSL、访问密钥已启用）状态为 **Creating**；应用尚未接入 |
| 5.1 性能对比 | 未开始 | — |
| 5.2 清理 | 未开始 | — |

**结论**：11 个子任务中，目前**没有一个具备完整且合规的截图证据**。真正部署成功的只有 Azure VM 和容器（已实测）；Azure Redis 正在创建。原台账中的代码问题（R-12、R-13、R-16、R-17、R-22、R-23、R-24）**均未修复**。`report.html` 已改为英文（R-05 实际上已按英文处理，仍待 Robin 确认）。

### 6.2 新增问题

| 编号 | 位置 | 问题描述 | 级别 | 影响评分点 | 处理建议 | 状态 |
|---|---|---|---|---|---|---|
| R-34 | `screenshots/azure-nsg.png`；report 中 "Azure NSG" 一图；`verification-evidence.png` 中的 "Azure network evidence" | 这张图**根本不是 NSG 截图**，而是 Mac 桌面截图（VS Code 加 Codex 终端），却被标注为 "Azure NSG showing Allow-5000"。画面中还能看到 Codex 对话内容"完成满分HTML作业报告" | P0 | 3.1；学术诚信 | 立即从报告中移除；重新在 Azure Portal 中截取 NSG 入站规则页面 | 待处理 |
| R-35 | `screenshots/jmeter-plan.png` | 这是用 HTML 渲染出来的"测试计划树"，**不是 JMeter GUI 截图**，也看不到时间；README 中称其为 "validated JMeter plan tree" | P0 | 1.3 | 在 Ubuntu VM 的 JMeter GUI 中打开 jmx 后截图 | 待处理 |
| R-36 | `screenshots/verification-evidence.png` | 把命令输出的文字拼贴到 HTML 页面后截的图（可以看到字面上的 `\n`），不是终端截图；页面声称 "No values below are simulated"；同时嵌入了 R-34 那张错误的图 | P1 | 1.1、4.1 | 改为真实终端截图（含 `date` 输出）；删除这张拼贴图 | 待处理 |
| R-37 | JMeter 结果与 jmx | 本地 jmx 仍然没有 `ignoreFirstLine`；实测线上 API 对 `timestamp=date` 返回 **400**。照此运行至少应有 1 个错误，但仪表盘显示 0 错误，说明**跑的不是当前提交的 jmx 或 CSV**；仪表盘时间 6:43 PM 与本地 10:43 AM MDT 的时区差异也没有解释 | P1 | 1.3 | 修好 jmx 后在 GUI 中重跑，以重跑结果为准 | 待处理 |
| R-38 | `screenshots/analysis-live.png` | 截图中看不到日期时间；只有 JSON，没有任何图表 | P1 | 1.2 | 改为图表截图并带上时间 | 待处理 |
| R-39 | Azure 资源 | VM 为 D2s_v3，**持续计费**；NSG 中 22 和 5000 端口对 `*` 开放；实验资源放在资源组 `dealerops-student-demo` 中，这个组与其他项目共用，**清理时不能删除整个资源组**，必须按名称逐个删除 cpsy300-* 资源 | P1 | 5.2；费用与安全 | 不用时停止或解除分配 VM；SSH 限制为自己的 IP；清理清单按名称列出 | 待处理 |

### 6.3 当前 Azure 资源清单（用于 5.2 清理）

| 资源 | 类型 | 状态 |
|---|---|---|
| cpsy300-lab03-vm2 | VM（D2s_v3，eastus） | 运行中 |
| cpsy300-lab03-vm2_disk1_… | 托管磁盘 | — |
| cpsy300-lab03-vm2255 | NIC | — |
| cpsy300-lab03-vm2-ip | 公网 IP（20.84.66.238） | — |
| cpsy300-lab03-vm2-nsg | NSG | — |
| cpsy300-lab03-key2 | SSH 公钥 | — |
| cpsy300-redis | Azure Cache for Redis（Basic C0） | Creating |
| vnet-eastus-1 | VNet | 需确认是否为本实验创建，再决定是否删除 |
