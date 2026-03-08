# Full Sync Deploy（本地完整同步到服务器）

目标：每次发布都把“本地代码 + 本地数据库 + 部署配置”完整同步到服务器，避免本地/线上不一致。

## 一条命令

```bash
./scripts/deploy_full_sync.sh \
  --user neo \
  --host 100.122.169.32 \
  --remote-dir /home/neo/WMS-system \
  --version 1.0.0
```

如果你不用 SSH key，可加密码参数：

```bash
./scripts/deploy_full_sync.sh \
  --user neo \
  --host 100.122.169.32 \
  --password '你的SSH密码' \
  --yes
```

也可用环境变量：

```bash
export WMS_SSH_PASSWORD='你的SSH密码'
./scripts/deploy_full_sync.sh --user neo --host 100.122.169.32 --yes
```

## 脚本会做什么

1. 本地打安装包（installer bundle）
2. 本地导出 Odoo 数据库（按 `odoo.conf` 读取连接信息）
3. 上传安装包和数据库 dump 到服务器
4. 覆盖服务器代码目录（保留服务器 `deploy/.env`）
5. 将本地 dump 恢复到服务器 PostgreSQL
6. 执行服务器 `INSTALL.sh`（模块升级、中文化、健康检查）
7. 输出服务状态与 HTTP 验收结果

## 注意事项

- 这是“整库覆盖”，会替换服务器现有业务数据。
- 推荐上线前先做服务器备份快照。
- 推荐使用 SSH key；密码模式依赖 `expect`。
- 本地 `odoo.conf` 的 `db_name/db_user/db_password` 必须正确。

## 失败回滚建议

- 先恢复服务器部署前数据库备份。
- 再回滚到上一版安装包代码。

