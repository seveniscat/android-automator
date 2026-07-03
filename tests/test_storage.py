"""存储层测试(使用临时 SQLite)。"""

from __future__ import annotations

import os
import tempfile

import pytest

# 在导入 storage 之前,把 DB 指向临时文件
_tmp = tempfile.mkdtemp(prefix="automator_test_")
os.environ["AUTOMATOR_DB_URL"] = f"sqlite:///{_tmp}/test.db"

# 重新加载 settings(因为已被其他模块导入过)
from automator import config as _config  # noqa: E402
from automator.config import Settings  # noqa: E402

new_settings = Settings()
new_settings.db_url = f"sqlite:///{_tmp}/test.db"
_config.settings = new_settings
# 也同步到 storage 模块
from automator.storage import db as _db  # noqa: E402
_db._engine = None
_db._SessionLocal = None

# 重置 repository 单例
from automator.storage import repository as _repo_mod  # noqa: E402
_repo_mod._repository = None


@pytest.fixture()
def repo():
    from automator.storage.repository import Repository
    return Repository()


def test_flow_crud(repo):
    rec = repo.save_flow(name="f1", yaml_content="name: f1\nsteps: []")
    assert rec.id > 0
    got = repo.get_flow(rec.id)
    assert got.name == "f1"

    recs = repo.list_flows()
    assert any(f.name == "f1" for f in recs)

    assert repo.delete_flow(rec.id) is True
    assert repo.get_flow(rec.id) is None


def test_task_and_run(repo):
    task = repo.create_task(
        flow_id=None,
        flow_name="t",
        flow_yaml="name: t\nsteps: []",
    )
    assert task.id > 0

    run = repo.create_run(task.id)
    assert run.status == "running"

    repo.finish_run(
        run.id,
        success=True,
        duration_ms=100,
        step_results=[
            {"step_name": "s1", "step_type": "wait", "success": True, "duration_ms": 50}
        ],
    )

    run2 = repo.get_run(run.id)
    assert run2.status == "success"
    assert run2.duration_ms == 100

    steps = repo.get_step_results(run.id)
    assert len(steps) == 1
    assert steps[0].step_name == "s1"
