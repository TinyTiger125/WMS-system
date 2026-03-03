# 1.0 UAT 验收清单（主干无阻断）

## 0. 预检查
- 服务可访问: `/web/login` 返回 200。
- 三角色账号可登录:
  - `boss_demo`
  - `warehouse_demo`
  - `service_demo`

## 1. 角色权限
- 执行脚本:
```bash
./scripts/qa_role_access_scan.sh
```
- 预期结果:
  - 输出 `Role Access Scan PASSED`
  - 无 `menu ... has no read access` 错误
  - 无 `list-read failed` 错误

## 2. 主流程（老板 + 库管）
1. 商品登记（老板）
2. 采购下单（老板）
3. 采购入库（库管）
4. 销售下单（老板或销售）
5. 销售出库（库管）

验收标准:
- 每一步可进入页面且不报权限错。
- “下一步”按钮可跳转且不报前端错误。
- 取消按钮仅老板可见。

## 3. 报表与异常
- 经营日报可打开。
- 低库存预警可打开。
- 库存占资 TOP10 可打开。

## 4. 发布门禁
- P0: 0 个（阻断业务、数据错乱、登录/权限崩溃）
- P1: 0 个（主流程明显绕路或高频报错）
- 脚本 `scripts/release_1_0_check.sh` 通过。
