#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

CATEGORY_NAME_MAP = {
    "games": "游戏",
    "tools": "工具",
    "study": "学习",
    "life": "生活",
    "other": "其他",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip('/')


def default_site_base(repo: str) -> str:
    owner, _, repo_name = repo.partition('/')
    if not owner or not repo_name:
        raise ValueError(f"invalid repo format: {repo}, expected owner/repo")
    return f"https://{owner}.github.io/{repo_name}"


def to_url(repo: str, branch: str, rel_path: str, site_base: str) -> dict:
    rel_path = rel_path.replace('\\', '/')
    primary = f"{site_base}/{rel_path}"
    return {
        "primary": primary,
        # 保留字段结构，避免前端改动；GitHub Pages + 自定义域名下可与 primary 相同
        "mirror": primary,
    }


def to_proxy_url(url: str) -> str:
    # 保留字段结构，统一走 GitHub Pages 域名
    return url


def resolve_media_url(repo: str, branch: str, site_base: str, media_value):
    if not media_value:
        return media_value
    if isinstance(media_value, str):
        if media_value.startswith("http://") or media_value.startswith("https://"):
            return media_value
        return to_url(repo, branch, media_value, site_base)["primary"]
    if isinstance(media_value, list):
        out = []
        for item in media_value:
            if isinstance(item, str) and not (item.startswith("http://") or item.startswith("https://")):
                out.append(to_url(repo, branch, item, site_base)["primary"])
            else:
                out.append(item)
        return out
    return media_value


def infer_rpk_path(root: Path, category: str, app_id: str, version_name: str) -> str:
    # 新结构（唯一推荐）：packages/<category>/*.rpk
    category_dir = root / "packages" / category
    category_rpk_files = sorted(category_dir.glob("*.rpk")) if category_dir.exists() else []
    if category_rpk_files:
        preferred_names = {
            f"{app_id}.rpk",
            f"{app_id}-{version_name}.rpk",
            f"{app_id}_{version_name}.rpk",
        }
        exact = [p for p in category_rpk_files if p.name in preferred_names]
        if len(exact) == 1:
            return str(exact[0].relative_to(root)).replace('\\', '/')
        if len(exact) > 1:
            raise ValueError(
                f"multiple matched .rpk files found in {category_dir} for appId={app_id}, version={version_name}. "
                f"Please set rpkPath explicitly."
            )

        # 次选：文件名包含 appId 且包含版本号
        fuzzy = [
            p for p in category_rpk_files
            if app_id.lower() in p.name.lower() and str(version_name).lower() in p.name.lower()
        ]
        if len(fuzzy) == 1:
            return str(fuzzy[0].relative_to(root)).replace('\\', '/')
        if len(fuzzy) > 1:
            raise ValueError(
                f"multiple fuzzy matched .rpk files found in {category_dir} for appId={app_id}, version={version_name}. "
                f"Please set rpkPath explicitly."
            )

        # 兜底：仅按 appId 匹配
        app_only = [p for p in category_rpk_files if app_id.lower() in p.name.lower()]
        if len(app_only) == 1:
            return str(app_only[0].relative_to(root)).replace('\\', '/')
        if len(app_only) > 1:
            raise ValueError(
                f"multiple appId matched .rpk files found in {category_dir} for appId={app_id}. "
                f"Please include version in filename or set rpkPath explicitly."
            )

    raise ValueError(
        f"missing rpkPath and no matched .rpk found under packages/{category}/. "
        f"Please set rpkPath explicitly or place rpk as packages/{category}/{app_id}-{version_name}.rpk"
    )


def load_apps(apps_dir: Path, root: Path):
    apps = []
    for p in sorted(apps_dir.rglob('*.json')):
        data = json.loads(p.read_text(encoding='utf-8'))
        data["_metaPath"] = str(p.relative_to(root)).replace('\\', '/')

        if "category" not in data:
            # 默认采用 apps/<category>/<appId>.json 的目录名作为分类
            try:
                data["category"] = p.relative_to(apps_dir).parts[0]
            except Exception:
                data["category"] = "other"

        required = ["appId", "name", "packageName", "versionName", "versionCode"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"{p}: missing fields {missing}")

        category = data.get("category", "other")
        if not data.get("rpkPath"):
            data["rpkPath"] = infer_rpk_path(root, category, data["appId"], str(data["versionName"]))

        rpk_path = root / data["rpkPath"]
        if not rpk_path.exists():
            raise ValueError(f"{p}: rpkPath not exists -> {data['rpkPath']}")
        if rpk_path.suffix.lower() != ".rpk":
            raise ValueError(f"{p}: rpkPath must end with .rpk -> {data['rpkPath']}")

        if data.get("rpkFileName") and data["rpkFileName"] != rpk_path.name:
            raise ValueError(
                f"{p}: rpkFileName({data['rpkFileName']}) not match real file name({rpk_path.name})"
            )

        data["_rpkFileName"] = rpk_path.name
        data["_packageSizeBytes"] = rpk_path.stat().st_size

        apps.append(data)
    return apps


def build_index(repo: str, branch: str, site_base: str, apps: list):
    normalized = []
    for a in apps:
        category = a.get("category", "other")
        download_urls = to_url(repo, branch, a["rpkPath"], site_base)
        item = {
            "appId": a["appId"],
            "name": a["name"],
            "packageName": a["packageName"],
            "category": category,
            "versionName": a["versionName"],
            "versionCode": int(a["versionCode"]),
            "description": a.get("description", ""),
            "developer": a.get("developer", ""),
            "tags": a.get("tags", []),
            "minPlatformVersion": a.get("minPlatformVersion"),
            "minFirmware": a.get("minFirmware"),
            "icon": resolve_media_url(repo, branch, site_base, a.get("icon")),
            "screenshots": resolve_media_url(repo, branch, site_base, a.get("screenshots", [])),
            "rpkFileName": a.get("rpkFileName", a.get("_rpkFileName")),
            "packageSizeBytes": a.get("packageSizeBytes", a.get("_packageSizeBytes")),
            "download": {
                **download_urls,
                "proxy": to_proxy_url(download_urls["primary"]),
            },
            "meta": to_url(repo, branch, a["_metaPath"], site_base),
            "updatedAt": a.get("updatedAt", utc_now_iso()),
        }
        normalized.append(item)

    normalized.sort(key=lambda x: (x["category"], x["name"].lower(), -x["versionCode"]))

    buckets = {}
    for app in normalized:
        buckets.setdefault(app["category"], []).append(app)

    categories = []
    for cid in sorted(buckets.keys()):
        categories.append({
            "id": cid,
            "name": CATEGORY_NAME_MAP.get(cid, cid),
            "count": len(buckets[cid]),
            "apps": buckets[cid],
        })

    return {
        "version": "1.0",
        "generatedAt": utc_now_iso(),
        "repo": {
            "id": repo,
            "branch": branch,
        },
        "categories": categories,
        "apps": normalized,
    }


def main():
    parser = argparse.ArgumentParser(description="Build app index for third-party watch store")
    parser.add_argument("--repo", required=True, help="GitHub repo, e.g. owner/repo")
    parser.add_argument("--branch", default="main", help="Git branch")
    parser.add_argument("--site-base", default="", help="Site base URL for GitHub Pages/custom domain")
    parser.add_argument("--apps-dir", default="apps", help="Apps metadata directory")
    parser.add_argument("--out", default="data/index.json", help="Output index file")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    apps_dir = root / args.apps_dir
    out_file = root / args.out

    if not apps_dir.exists():
        raise SystemExit(f"apps dir not found: {apps_dir}")

    site_base = normalize_base_url(args.site_base) or default_site_base(args.repo)

    apps = load_apps(apps_dir, root)
    index = build_index(args.repo, args.branch, site_base, apps)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(f"[ok] wrote {out_file} ({len(index['apps'])} apps)")


if __name__ == "__main__":
    main()
