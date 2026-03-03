# 一键安装包说明（服务器）

## 1. 打包
在开发机执行：
```bash
./scripts/build_installer_bundle.sh 1.0.0
```
生成文件：
- `dist/custom-wms-installer-1.0.0.tar.gz`

## 2. 服务器一键安装
1. 上传并解压：
```bash
tar -xzf custom-wms-installer-1.0.0.tar.gz
cd custom-wms-installer-1.0.0
```
2. 执行一键安装：
```bash
./INSTALL.sh
```

安装器会自动执行：
- 环境预检（内存、磁盘、端口、基础命令）
- Docker / Compose 检查与常见系统自动安装
- 生成 `deploy/.env`（随机密码）
- 启动 PostgreSQL 容器
- 初始化 Odoo 数据库与模块
- 启动 Odoo 服务
- 健康检查直到服务可访问

## 3. 运维命令
- 查看状态：
```bash
./installer/status.sh
```
- 卸载（删除容器与数据卷）：
```bash
./installer/uninstall.sh
```

## 4. 失败排查
- 查看应用日志：
```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env logs -f odoo
```
- 常见原因：
  - 服务器无法访问 Docker 安装源
  - 端口冲突（`ODOO_HTTP_PORT`）
  - 服务器禁止特权命令（sudo）
