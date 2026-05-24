# NGA BBS CLI

一个轻量级的 NGA 论坛命令行客户端，无需浏览器即可浏览 NGA 论坛的版块列表、帖子列表和回复内容。

## 安装

```bash
pip install requests
```

## 快速开始

```bash
# 浏览所有版块分类
python -m nga_client categories

# 查看某个版块的话题列表
python -m nga_client threads 650
python -m nga_client threads 275 -p 2   # 第二页

# 阅读某个帖子的回复
python -m nga_client read 46826141

# 搜索版块
python -m nga_client search 晴风村

# 登录（可选，用于需要认证的版块）
python -m nga_client login --cookie "ngaPassportUid=xxx; ngaPassportCid=yyy"
```

## 命令参考

| 命令 | 别名 | 说明 |
|------|------|------|
| `categories` | `cat` | 列出所有版块分类和子版块（含 fid/stid） |
| `threads <fid>` | `t` | 获取指定版块的话题列表 |
| `read <tid>` | `r` | 阅读指定帖子的回复 |
| `search <keyword>` | `s` | 按关键词搜索版块 |
| `login` | — | 保存登录 Cookie 以访问受限版块 |

### 全局选项

| 选项 | 说明 |
|------|------|
| `--domain` | 指定 NGA 域名，可选 `bbs.ngacn.cc` `bbs.nga.cn` `nga.178.com` 等 |
| `--cookie` | 直接传入 Cookie 字符串 |
| `--insecure` | 跳过 SSL 验证（证书错误时使用） |

### threads 选项

| 选项 | 说明 |
|------|------|
| `-p, --page` | 页码（默认 1） |
| `--stid` | 子版块 ID（某些版块使用 stid 而非 fid） |

### read 选项

| 选项 | 说明 |
|------|------|
| `-p, --page` | 页码（默认 1，每页 20 楼） |

## 作为 Python 库使用

```python
from nga_client import NGAClient

client = NGAClient()

# 获取版块列表
cats = client.get_categories()

# 获取话题列表
topics = client.get_forum_topics(650, page=1)

# 读取帖子内容
replies = client.read_topic(46826141)

# 搜索版块
results = client.search_forum("晴风村")
```

### NGAClient 构造参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `domain` | str | 域名，默认 `https://bbs.nga.cn` |
| `cookie_str` | str | Cookie 字符串（可选） |
| `insecure` | bool | 跳过 SSL 验证 |

### 方法

| 方法 | 说明 |
|------|------|
| `get_categories()` | 获取版块分类树 |
| `get_forum_topics(fid, page=1, stid=None)` | 获取版块话题列表 |
| `read_topic(tid, page=1)` | 读取帖子回复 |
| `search_forum(keyword)` | 搜索版块 |
| `save_cookies()` | 将当前 Cookie 持久化到 `~/.nga_cookies.json` |

## 特性

- **自动 SSL 降级** — 内置 5 个备用域名，首个域名 SSL 出错时自动切换
- **Cookie 持久化** — 登录一次即可，后续自动加载 `~/.nga_cookies.json`
- **请求限速** — 相邻请求至少间隔 1 秒，礼貌访问
- **Windows 兼容** — 自动处理 GBK 编码问题
- **回复内容清洗** — 自动去除 BBCode、HTML 标签、引用块，保留中文可读性
- **无外部依赖** — 仅需 `requests` 库

## 数据来源

所有数据通过 NGA 论坛公开 API 获取，无需抓取 HTML 页面。

- 版块/话题：`/app_api.php`, `/thread.php`
- 帖子内容：`/read.php`
- 搜索：`/forum.php`

## Cookie 获取方法

1. 在浏览器中登录 NGA（https://bbs.nga.cn）
2. 打开开发者工具（F12）→ Application → Cookies
3. 复制 `ngaPassportUid` 和 `ngaPassportCid` 的值
4. 运行 `python -m nga_client login --cookie "ngaPassportUid=xxx; ngaPassportCid=yyy"`

## 许可

MIT
