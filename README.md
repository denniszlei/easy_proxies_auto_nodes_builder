# auto-proxy-list

定时抓取公开 proxy list，并生成 [easy_proxies](https://github.com/jasonwong1991/easy_proxies.git) 可直接使用的 `nodes.txt` 成品文件。

## 下载成品

- 仓库内文件：[`dist/node.txt`](dist/node.txt)
- Raw 直链：`https://raw.githubusercontent.com/denniszlei/easy_proxies_auto_nodes_builder/main/dist/node.txt`
- 浏览器查看：`https://github.com/denniszlei/easy_proxies_auto_nodes_builder/blob/main/dist/node.txt`

## 数据来源

- `https://imtaqin.id/api/vpn/sub/all`
- `https://imtaqin.id/api/proxies`

## 生成规则

- 合并订阅节点与公开的 HTTP / SOCKS5 代理
- 仅保留 `easy_proxies` 实际兼容的协议格式
- 输出为纯文本 `nodes.txt`，每行一个 URI
- 脚本仅使用 Python 标准库，无额外依赖
- GitHub Actions 每 6 小时自动刷新一次

## 与 Easy Proxies 配合使用

在 [easy_proxies](https://github.com/jasonwong1991/easy_proxies.git) 的配置里可使用 `nodes_file` 指向下载后的本地文件，也可以在后续把最终 raw 链接直接填进 `subscriptions`。

参考项目：[`jasonwong1991/easy_proxies`](https://github.com/jasonwong1991/easy_proxies.git)
