# xtc-third-store-backend

第三方手表应用商店后端（纯静态仓库版）。

目标：
- 仓库里只放应用元数据和已编译好的 `.rpk` 安装包。
- 应用列表 `data/index.json` 自动生成。
- 统一走 GitHub Pages（可绑定自定义域名），减少镜像缓存延迟。

## 仓库结构（建议）

```text
xtc-third-store-backend/
  apps/                          # 每个应用一份元数据
    games/
      sample-math.json
    tools/
      sample-timer.json
  packages/                      # rpk 存放区（按分类/应用）
    games/sample-math/sample-math-1.0.0.rpk
    tools/sample-timer/sample-timer-1.0.0.rpk
  data/
    index.json                   # 自动生成，前端直接拉这个
  scripts/
    build_index.py               # 构建索引脚本
  .github/workflows/
    rebuild-index.yml            # push 后自动更新索引
```

## 元数据格式（apps/*.json）

最小字段：

```json
{
  "appId": "sample-math",
  "name": "口算练习",
  "packageName": "com.demo.math",
  "category": "games",
  "versionName": "1.0.0",
  "versionCode": 1
}
```

`rpkPath` 可选（推荐不写，避免手误）：
- 若不写，会自动从 `packages/<category>/<appId>/` 下寻找 `.rpk`
- 该目录仅允许存在 1 个 `.rpk`，否则会报错并阻止生成错误索引
- 脚本仍兼容旧结构 `packages/<category>/<appId>/<versionName>/`（建议逐步迁移）

可选字段：
- `icon`, `screenshots`, `description`, `developer`, `tags`, `minPlatformVersion`, `minFirmware`

## 自动更新列表

提交（push）以下内容时会自动更新 `data/index.json`：
- `apps/**/*.json`
- `packages/**/*.rpk`

## 本地手动生成

```bash
python scripts/build_index.py --repo "demo/xtc-third-store-backend"
```

如需强制使用自定义域名：

```bash
python scripts/build_index.py --repo "demo/xtc-third-store-backend" --site-base "https://store.example.com"
```

不传 `--site-base` 时，默认使用：`https://<owner>.github.io/<repo>`

## 前端建议拉取地址

以 `packages/games/sample-math/sample-math-1.0.0.rpk` 为例：

- 主地址（GitHub Pages / 自定义域名）
  - `https://<your-domain>/packages/games/sample-math/sample-math-1.0.0.rpk`
- `download.mirror` 与 `download.proxy` 字段保留，但默认与 `download.primary` 相同（保持 JSON 结构不变）

> 在 GitHub 仓库 Settings -> Pages 中开启发布；若使用自定义域名，请配置 DNS 并设置仓库变量 `STORE_BASE_URL`（例如 `https://store.example.com`）。

## 你后续上传应用时的最简流程

1. 把 `.rpk` 放到：`packages/<分类>/<appId>/xxx.rpk`
2. 新建或更新：`apps/<分类>/<appId>.json`
3. `git add . && git commit && git push`
4. 等 Action 自动更新 `data/index.json`

就这 4 步，不需要额外后台服务。
