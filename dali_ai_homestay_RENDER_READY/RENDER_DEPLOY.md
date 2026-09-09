# Render 固定公网部署

这个目录已经是 Render-ready 版本，项目文件位于仓库根目录。

## 最省事部署
1. 把本目录中的所有文件上传到 GitHub 仓库根目录（不要只上传 ZIP）。
2. 在 Render 新建 Web Service 或 Blueprint。
3. 连接该 GitHub 仓库。
4. 如果使用 Web Service 手动配置：
   - Runtime: Python 3
   - Build Command: `python -m pip install -r requirements.txt`
   - Start Command: `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/guest`
   - Region: Singapore（如可选）
   - Plan: Free（Demo）
5. 部署成功后：
   - `/guest` 住客端
   - `/admin` 老板后台
   - `/qr` 二维码页

## 注意
- Free Web Service 适合演示，不建议直接作为正式商用生产环境。
- 当前 SQLite 数据可能在实例重建/重新部署后重置。
- 正式 V1 应迁移 PostgreSQL，并增加登录、权限、备份和隐私配置。
