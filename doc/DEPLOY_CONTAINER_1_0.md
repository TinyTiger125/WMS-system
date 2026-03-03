# 1.0 容器部署说明（目标服务器）

## 1. 目录与文件
- 编排文件: `deploy/compose.yaml`
- 镜像构建: `deploy/Dockerfile`
- 启动脚本: `deploy/start-odoo.sh`
- 初始化脚本: `deploy/init-db.sh`
- 健康检查: `deploy/healthcheck.sh`
- 环境变量模板: `deploy/.env.example`

## 2. 部署步骤
1. 复制环境变量模板。
```bash
cp deploy/.env.example deploy/.env
```
2. 修改 `deploy/.env` 中的数据库密码和 `ODOO_ADMIN_PASSWD`。
3. 构建镜像。
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env build
```
4. 启动数据库。
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env up -d db
```
5. 初始化数据库（仅首次安装或重建库时执行）。
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env --profile init run --rm init
```
6. 启动 Odoo 应用。
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env up -d odoo
```
7. 检查健康状态。
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env ps
curl -I http://127.0.0.1:${ODOO_HTTP_PORT:-8069}/web/login
```

## 3. 日常维护
- 查看应用日志:
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env logs -f odoo
```
- 升级自定义模块（不停库建议先在预发验证）:
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env run --rm --entrypoint /opt/deploy/init-db.sh init
```

## 4. 风险控制建议
- 先在预发环境跑 `scripts/release_1_0_check.sh` 再上线。
- 上线时冻结新功能，仅允许 bugfix。
- 保留回滚用镜像 tag，例如 `custom-wms:1.0.0`、`custom-wms:1.0.1`。
