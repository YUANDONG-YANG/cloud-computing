# Project 1: Cloud-Native Nutritional Insights Application — 任务简报 (for Codex)

来源:`Project 1 Cloud-Native Nutritional Insights Application.html`(作业原文)。本文件是对其要求的整理,用于指导实现。
所有 Azure 相关内容都在**本地模拟**,不使用真实 Azure 资源。团队作业,满分 100。

## 数据集 All_Diets.csv
列:`Diet_type, Recipe_name, Cuisine_type, Protein(g), Carbs(g), Fat(g), Extraction_day, Extraction_time`
(来源 Kaggle "healthy-diet-recipes-a-comprehensive-dataset" 或课程资源。当前目录**尚未包含该 CSV**,需用户提供。)
已知脏数据:`Diet_type` / `Cuisine_type` 大小写不一致(如 "Paleo" vs "paleo"),需 strip + 统一大小写;数值列可能有缺失。

## 目标目录结构
```
data_analysis.py            # Task 1
lambda_function.py          # Task 3
Dockerfile                  # Task 2
docker-compose.yml          # Task 2 (Compose 模拟部署)
requirements.txt
tests/                      # Task 4 的测试
.github/workflows/deploy.yml  # Task 4
simulated_nosql/results.json  # Task 3 输出
output/                     # 图表输出
```

## Task 1 (20分) — data_analysis.py
Pandas 处理:
1. 各 Diet_type 平均 Protein/Carbs/Fat
2. 每种 Diet_type 蛋白质最高的前 5 个食谱
3. 平均(或总体)蛋白质最高的饮食类型
4. 每种 Diet_type 最常见的 Cuisine_type
5. 新列:`Protein_to_Carbs_ratio = Protein/Carbs`,`Carbs_to_Fat_ratio = Carbs/Fat`
6. 清洗缺失值

可视化(Matplotlib/Seaborn,保存为 PNG):
- 柱状图:各饮食类型平均营养素
- 热力图:营养素 × 饮食类型
- 散点图:前 5 蛋白食谱在各菜系的分布

题目伪代码的坑(不要照抄):
- `df.fillna(df.mean())` 遇到字符串列会报错 → 只对数值列填充
- 比值要处理除以 0 / inf / NaN
- 必须 `matplotlib.use('Agg')` 并 `savefig`(容器内无显示器)
- 输出目录先 `os.makedirs(..., exist_ok=True)`

## Task 2 (20分) — Docker
- Dockerfile 起点:`FROM python:3.9-slim` / `WORKDIR /app` / `COPY . /app` / `RUN pip install pandas matplotlib seaborn` / `CMD ["python","data_analysis.py"]`
- `docker build -t diet-analysis .` 与 `docker run -it diet-analysis`,用 volume 挂载导出图表
- 可选:推送 Docker Hub(`docker login/tag/push`)或本地 registry(Harbor)
- 用 Docker Compose 或 Minikube 模拟编排部署(推荐 Compose,更简单)

## Task 3 (20分) — lambda_function.py (Azurite 模拟 serverless)
- 启动 Azurite:`npm i -g azurite` 或 `docker run -p 10000:10000 -p 10001:10001 mcr.microsoft.com/azure-storage/azurite`
- Blob 端点 `http://127.0.0.1:10000/devstoreaccount1`;用 Storage Explorer 或脚本创建容器 `datasets` 并上传 `All_Diets.csv`
- 函数:用 `azure-storage-blob` 的 `BlobServiceClient.from_connection_string` 读 CSV → 算各饮食类型平均 Protein/Carbs/Fat → 写入 `simulated_nosql/results.json`(或本地 MongoDB)
- 连接串需使用 Azurite **官方完整默认 AccountKey**(题目示例被截断)
- 触发:手动调用,或 `watchdog` 模拟事件触发
- 若函数在 Docker 内运行,Azurite 地址用 Compose 服务名,不要用 127.0.0.1
- 需附文字说明:如何用 Azurite 模拟云存储与 serverless 流程

## Task 4 (20分) — CI/CD
- GitHub 仓库 + `.github/workflows/deploy.yml`:构建 Docker 镜像 → 运行测试/检查(pytest/flake8) → 推送 Docker Hub(用 GitHub Secrets 存凭据)→ 可选 SSH 部署
- GitHub runner 在云端,访问不到本地 Azurite:测试用 mock 或在 workflow 里以 service container 启动 Azurite
- 需要展示模拟部署证据(如容器运行输出)

## Task 5 (5分) — 增强研究 + 1 页报告
三选二,应用到 Task 1–4 之一:
a. 多阶段 Docker 构建/缩小镜像
b. 降低 serverless 冷启动、提升执行速度
c. 优化查询/索引/数据处理逻辑
建议选 **a + c**,最容易量化。报告需含:选了哪两项、研究内容、应用的改进、**前后对比数据**(镜像 MB、耗时等)、预期收益。

## 其他评分项
- 视频演示 10 分(全员出镜)、贡献报告 5 分(分工、commit/PR、会议、工时、沟通方式)— 需人工完成,代码侧保证各成员有独立 commit。

## 提交物
`data_analysis.py`、`lambda_function.py`、`Dockerfile`、`.github/workflows/deploy.yml`;PDF 报告(所有截图须**可见日期时间**,含 1 页增强报告);团队视频;贡献报告。打包 zip。

## 给 Codex 的建议执行顺序
1. 向用户确认/获取 `All_Diets.csv`
2. Task 1:写 `data_analysis.py`,本地跑通,生成图表与控制台结果
3. Task 2:Dockerfile + docker-compose.yml,验证容器内可运行
4. Task 3:`lambda_function.py` + Azurite(compose 里加 azurite 服务)+ 上传脚本
5. Task 4:测试 + deploy.yml
6. Task 5:记录优化前后数据,生成报告草稿
截图、视频、Docker Hub 登录等需用户手动操作的部分,列出清单交给用户。

## 本地环境现状 (2026-09-30 检测)
- Windows 10 宿主机:已有 Python 3.11、Node/npm、Git(`D:\Git\bin\git.exe`)
- **未检测到 Docker**;WSL 已启用但**没有安装任何发行版**
- 注册表显示装过 VirtualBox 7.2.16,但默认路径下找不到 `VBoxManage.exe`;用户表示本地有虚拟机(Ubuntu VM 按作业要求用于 Docker/Azurite/Azure Functions 相关任务)
- 分工建议:Task 1 可直接在宿主机 Python 跑;Task 2/3/4 需要 Docker 的部分在 Ubuntu VM 内执行。VM 的名称/登录方式待用户提供
