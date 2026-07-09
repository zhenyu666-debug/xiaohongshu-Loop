# xhs-scheduler SKILL.md

## 当前状态
APScheduler 调度器已完成：AsyncIOScheduler、任务激活/暂停/删除、reload_all_tasks()。task.tenant_id 列缺失需修复。

## 关键文件索引
1. `xiaohongshu-saas/app/scheduler/__init__.py` - APScheduler 调度器
2. `xiaohongshu-saas/app/scheduler/runner.py` - run_task_once() 任务执行
3. `xiaohongshu-saas/app/api/tasks.py` - 任务 CRUD API
4. `xiaohongshu-saas/alembic/versions/0001_baseline.py` - STAMP-ONLY baseline
5. `xiaohongshu-saas/app/models/orm.py` - Task 模型 (tenant_id)

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 APScheduler 持久化 next_run_at
- 2026-07-09: TODO: 修 task.tenant_id 列缺失 (alembic migration + startup ALTER)

## Next 待办
- [P0] 新增 alembic revision 0002_tenant_id.py 或 startup ALTER TABLE
- [P1] 添加任务执行日志详细记录
- [P2] 支持 CronTrigger 任务持久化 next_run_time
