
# 云端部署：最省事的两种方式

这个版本已经加好：

- `Dockerfile`
- `render.yaml`
- `railway.json`
- `/qr` 真二维码页面
- `/api/qr` 二维码图片接口
- 云平台 `$PORT` 支持

## 方案 A：Render

1. 把整个项目上传到一个 Git 仓库。
2. 在 Render 新建 Web Service / Blueprint。
3. 选择这个仓库。
4. Render 会读取 `render.yaml` 或 `Dockerfile`。
5. 可选环境变量：
   - `DEEPSEEK_API_KEY`
   - `AMAP_WEB_KEY`
6. 部署完成后会得到一个 HTTPS 地址。

例如：

`https://dali-ai-homestay.onrender.com`

然后：

- 住客端：`/guest`
- 老板后台：`/admin`
- 真二维码：`/qr`

### 注意

免费/临时实例可能在重新部署后丢失 SQLite 数据。
**销售演示没问题，真实付费客户不要长期这样用。**
V1 应迁移 PostgreSQL。

---

## 方案 B：Railway

1. 把项目上传到 Git 仓库。
2. Railway → New Project → Deploy from GitHub Repo。
3. 选择仓库。
4. Railway 会读取 `Dockerfile`。
5. 在 Variables 中配置：
   - `DEEPSEEK_API_KEY`
   - `AMAP_WEB_KEY`
6. Generate Domain。

部署完成后一样打开：

- `/guest`
- `/admin`
- `/qr`

---

# Mac 本地用 Docker 先验证

如果你的 Mac 已安装 Docker Desktop：

```bash
docker build -t dali-ai-homestay .
docker run --rm -p 8000:8000 dali-ai-homestay
```

浏览器：

- http://localhost:8000/guest
- http://localhost:8000/admin
- http://localhost:8000/qr

---

# 正式商用前必须升级

当前云版是“销售/试点版”，不是最终商用架构。

真实收钱前建议完成：

1. PostgreSQL
2. 多租户账号和权限
3. HTTPS（托管平台通常自动提供）
4. 数据删除/留存设置
5. 日志和错误监控
6. 前台人工接管工作台
7. POI更新时间和审核
8. 商家合作关系披露
9. 隐私政策与AI说明
10. 备份
