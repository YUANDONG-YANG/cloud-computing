# Stage 1 — 本地后端交付包

这是 `../division.md` 中 Person 1 的工作目录。基于现有 `../backend/` 和后端测试整理，
新增本地 CSV 加载、文字搜索、相关系数及 NumPy k-means；原有部署目录未改动。
本目录可独立运行，包含完整的 `data/All_Diets.csv`（来自 Project1）。

- 教师汇总材料：[summary.html](summary.html)，无需联网，支持浏览器打印为 PDF。
- 进程内接口实测结果：[docs/api-results.json](docs/api-results.json)。
- 真实 HTTP 实测结果：[docs/http-results.json](docs/http-results.json)。
- 测试与验证记录：[docs/verification.txt](docs/verification.txt)。
- 运行截图：[docs/screenshots/](docs/screenshots/)，共 7 张。

## 文件与职责

| 文件 | 用途 |
|---|---|
| function_app.py | Azure Functions v2 HTTP 入口，4 个 GET 路由 |
| nutrition.py | 文本清理、缺失值填充及统计聚合 |
| clustering.py | NumPy 手写 k-means，固定随机种子 |
| data/All_Diets.csv | 完整本地数据，7,806 条食谱 |
| tests/ | 数据清洗、接口、边界条件、聚类、本地缓存测试 |
| host.json / local.settings.json.example | Functions 主机配置和无密钥的本地配置模板 |
| verify_http.py | 对运行中的 Functions 主机发 10 条真实 HTTP 请求并断言结果 |
| requirements*.txt / pytest.ini / .flake8 | 依赖、测试与代码风格配置 |

## 本地运行

在 `Project2/stage1` 中执行；使用 Python 3.11，与团队原有项目运行环境一致。
下面的流程已在 Python 3.11.18 与 Azure Functions Core Tools 4.16.0 下实测通过。
若尚未安装 Core Tools：`npm i -g azure-functions-core-tools@4`。

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -r requirements-dev.txt
cp local.settings.json.example local.settings.json
python -m pytest -q
python -m flake8 . --exclude=.venv,.venv311
func start --port 7071
# 主机起来后，另开一个终端：
python verify_http.py
```

本阶段只读本地 CSV，不需要 Azure 账号、Blob 密钥或 Azurite。
可用环境变量 `DATASET_PATH` 指定另一份 CSV；相对路径基于运行目录，建议用绝对路径。
默认读取本目录的 `data/All_Diets.csv`。缓存按文件路径、修改时间和大小更新。
前端本地 CORS 允许 `http://localhost:5500` 和 `http://127.0.0.1:5500`。

## API 约定

基地址 `http://localhost:7071/api`。全部为 GET，返回 `application/json`。
数据接口的 `metadata` 包含执行时间（秒）、数据来源及缓存命中状态。
失败返回 `{"error": "..."}`；内部异常不会出现在 HTTP 响应里。

| 接口 | 参数 | 返回内容 |
|---|---|---|
| /health | 无 | 服务状态；不读取 CSV |
| /insights | 无 | average_macros、correlation、summary.diet_counts、top_recipes、common_cuisines、total_protein_by_diet、metadata |
| /recipes | diet_type, search, page, limit | recipes、count、total、page、limit、total_pages、diet_type_filter、search、metadata |
| /clusters | k（默认 3，范围 1–10） | points、centroids、cluster_counts、features、k、seed、iterations、inertia、standardized、metadata |

- `diet_type` 不区分大小写；省略或 `all` 表示所有类型，未知类型返回 404。
- `search` 在食谱名、饮食类型和菜系中作不区分大小写的字面匹配，可与饮食筛选组合；无匹配返回空列表。
- `page` 从 1 开始，默认 1；`limit` 默认 50，最大 500；无效参数返回 400。超出末页会返回末页。
- `correlation` 是蛋白质、碳水、脂肪的 Pearson 相关系数矩阵，常数列的未定义值返回 null。
- `clusters` 使用全部食谱，返回全部点供散点图使用。cluster 从 0 编号；质心和点均以克为单位。
- k-means 先进行 z-score 标准化，固定 seed=42，最多迭代 100 次；空簇保留原质心。
  inertia 为标准化空间中的平方距离和；聚类仅为探索性分组，不是饮食建议。
- `k` 大于不同营养向量数量时返回 400。

## 数据清理

去除列名和文本两端空格；饮食类型与菜系统一小写，缺失填为 unknown；
缺失食谱名填 Unnamed recipe。营养数值转为数字，负数、无穷值、非法文本及缺失值
用所在列有效数值的均值填补。缺少必需列、空数据或整列无有效数值时拒绝处理。

## 实测 JSON 示例

以下来自完整 CSV 的进程内 handler 调用，不是网络请求。insights 省略附加统计列表，
clusters 的 points 仅展示前两条；完整返回结果见 docs/api-results.json。

### GET /api/health

```json
{
  "status": "healthy",
  "service": "nutritional-insights-api",
  "version": "2.0.0",
  "dataset_cached": false
}
```

### GET /api/insights

```json
{
  "average_macros": [
    {
      "Diet_type": "dash",
      "Protein(g)": 69.28,
      "Carbs(g)": 160.54,
      "Fat(g)": 101.15
    },
    {
      "Diet_type": "keto",
      "Protein(g)": 101.27,
      "Carbs(g)": 57.97,
      "Fat(g)": 153.12
    },
    {
      "Diet_type": "mediterranean",
      "Protein(g)": 101.11,
      "Carbs(g)": 152.91,
      "Fat(g)": 101.42
    },
    {
      "Diet_type": "paleo",
      "Protein(g)": 88.67,
      "Carbs(g)": 129.55,
      "Fat(g)": 135.67
    },
    {
      "Diet_type": "vegan",
      "Protein(g)": 56.16,
      "Carbs(g)": 254.0,
      "Fat(g)": 103.3
    }
  ],
  "correlation": {
    "Protein(g)": {
      "Protein(g)": 1.0,
      "Carbs(g)": 0.155682,
      "Fat(g)": 0.478012
    },
    "Carbs(g)": {
      "Protein(g)": 0.155682,
      "Carbs(g)": 1.0,
      "Fat(g)": 0.269059
    },
    "Fat(g)": {
      "Protein(g)": 0.478012,
      "Carbs(g)": 0.269059,
      "Fat(g)": 1.0
    }
  },
  "summary": {
    "total_recipes": 7806,
    "diet_types": [
      "dash",
      "keto",
      "mediterranean",
      "paleo",
      "vegan"
    ],
    "diet_counts": {
      "mediterranean": 1753,
      "dash": 1745,
      "vegan": 1522,
      "keto": 1512,
      "paleo": 1274
    },
    "highest_mean_protein_diet": "keto",
    "highest_mean_protein_g": 101.27,
    "highest_total_protein_diet": "mediterranean",
    "highest_total_protein_g": 177249.89
  },
  "metadata": {
    "execution_time_seconds": 0.027,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": false
  }
}
```

### GET /api/recipes

```json
{
  "recipes": [
    {
      "Diet_type": "keto",
      "Recipe_name": "Keto Chicken Pot Pie Casserole Recipe",
      "Cuisine_type": "american",
      "Protein(g)": 183.07,
      "Carbs(g)": 66.95,
      "Fat(g)": 330.43
    },
    {
      "Diet_type": "keto",
      "Recipe_name": "Keto Everything Bagel Chicken",
      "Cuisine_type": "american",
      "Protein(g)": 214.84,
      "Carbs(g)": 17.29,
      "Fat(g)": 140.76
    }
  ],
  "count": 2,
  "total": 225,
  "page": 1,
  "limit": 2,
  "total_pages": 113,
  "diet_type_filter": "keto",
  "search": "chicken",
  "metadata": {
    "execution_time_seconds": 0.002,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

### GET /api/clusters

```json
{
  "k": 3,
  "features": [
    "Protein(g)",
    "Carbs(g)",
    "Fat(g)"
  ],
  "standardized": true,
  "seed": 42,
  "iterations": 58,
  "inertia": 12825.275678703805,
  "cluster_counts": {
    "0": 1205,
    "1": 5681,
    "2": 920
  },
  "centroids": [
    {
      "cluster": 0,
      "Protein(g)": 228.09124481327768,
      "Carbs(g)": 119.31101244813274,
      "Fat(g)": 265.9383568464727
    },
    {
      "cluster": 1,
      "Protein(g)": 49.97187114944563,
      "Carbs(g)": 100.62553775743703,
      "Fat(g)": 75.44519978876957
    },
    {
      "cluster": 2,
      "Protein(g)": 98.87491304347826,
      "Carbs(g)": 513.0980000000006,
      "Fat(g)": 181.31163043478267
    }
  ],
  "points": [
    {
      "Recipe_name": "Bone Broth From 'Nom Nom Paleo'",
      "Diet_type": "paleo",
      "Protein(g)": 5.22,
      "Carbs(g)": 1.29,
      "Fat(g)": 3.2,
      "cluster": 1
    },
    {
      "Recipe_name": "Paleo Effect Asian-Glazed Pork Sides, A Sweet & Crispy Appetizer",
      "Diet_type": "paleo",
      "Protein(g)": 181.55,
      "Carbs(g)": 28.62,
      "Fat(g)": 146.14,
      "cluster": 0
    }
  ],
  "metadata": {
    "execution_time_seconds": 0.026,
    "source": "Local CSV",
    "dataset": "All_Diets.csv",
    "dataset_from_cache": true
  }
}
```

## 验收与交接

`division.md` 第一部分的完成条件已全部满足，证据见 `docs/`：

| 完成条件 | 结果 | 证据 |
|---|---|---|
| 44 项 pytest 通过、flake8 无报错（Python 3.11） | 通过 | docs/screenshots/cli-pytest-flake8.png |
| `func start` 能起本地主机并注册 4 个路由 | 通过 | docs/screenshots/cli-func-start.png |
| 4 个接口在浏览器中实际返回 | 通过 | docs/screenshots/api-*-browser.png |
| 真实 HTTP 行为（分页、搜索、400/404、本地 CORS） | 10 条用例全通过 | docs/screenshots/cli-http-verification.png、docs/http-results.json |
| 完整 CSV 数据量一致 | insights 与 clusters 均为 7,806 | docs/verification.txt |

7 张截图全部由 macOS `screencapture` 对屏幕上的真实窗口截取：浏览器图为 Google Chrome 窗口
（地址栏可见，使用独立空白配置，不含个人浏览数据），终端图为 Terminal.app 窗口中的真实命令输出。
所有验证只在本地进行，未创建或改动任何 Azure 资源与 stage1 以外的配置。

交接：
1. 交给 Person 2：基地址 `http://localhost:7071/api`、上述 JSON 契约及本地 CORS 设置。
2. Person 3 后续将本地加载替换为 Blob Storage，并保持 API 契约一致。

团队现有 frontend/ 只对接原来的 3 个接口，新增搜索、相关系数图和聚类图仍需 Person 2 接入。
不要直接运行现有 deploy.sh 来发布本目录：原部署脚本仍面向 ../backend/。
整组提交要求包括 Azure 部署、PDF/Word 截图报告和所有成员参与的视频（约 10 分钟）；
原项目已有部署和截图记录，不能据本次本地环境缺少工具就认定这些工作尚未完成。
本 HTML 仅覆盖第一部分，不能替代最终整组提交。

## 已有截图核对

summary.html 已内嵌原项目的 5 张证据图：Function App 运行状态、health、insights、recipes 返回结果，以及 CORS/HTTP 200/计时记录。
这些是原版三接口部署的证据，不要求重复制作；新增的 clusters、搜索和相关系数需用当前 stage1 的验证记录补充。
原始课程 brief 并未硬性规定 k-means 或四个接口，这些来自小组 division.md 分工。
