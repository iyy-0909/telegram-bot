# 部署说明

## 生产环境代理处理

生产环境建议在 `.env` 中设置：

```env
APP_ENV=production
```

当 `APP_ENV=production` 时，系统会在运行时自动忽略账号中配置的本地代理，避免服务器错误连接本地开发代理。

会被自动忽略的本地代理地址包括：

- `127.0.0.1`
- `localhost`
- `0.0.0.0`
- `::1`

例如，本地开发数据库里账号代理是 `127.0.0.1:7897`，上传到线上服务器后，系统不会修改数据库字段，只会在运行时把这个代理当作未配置处理。

如果线上需要使用代理，请配置服务器真实可访问的远程代理地址，例如：

```txt
socks5://1.2.3.4:1080
http://1.2.3.4:7890
```

Bot API 请求同样遵守这个规则。生产环境不要配置本地 Bot API 代理：

```env
BOT_API_PROXY=http://127.0.0.1:7897
```

如果服务器不能直连 `api.telegram.org`，请配置真实远程代理：

```env
BOT_API_PROXY=socks5://user:pass@host:port
```

生产环境启动时，如果发现 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`http_proxy`、`https_proxy`、`all_proxy` 指向本地地址，也会自动从运行时环境中清理，避免 `requests` 误走本地开发代理。

生产环境忽略本地代理时，后端日志会出现类似记录：

```txt
生产环境已忽略本地代理 | account_id=1 | account_name=采集账号 | proxy=127.0.0.1:7897
```
