"""流程 CRUD 路由。"""

from __future__ import annotations

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...flow.yaml_loader import validate_flow
from ...flow.steps import list_steps
from ...storage.repository import Repository
from ..deps import get_repo

router = APIRouter(prefix="/api/flows", tags=["flows"])


class FlowIn(BaseModel):
    name: str
    yaml_content: str = Field(alias="yaml")
    description: str = ""
    tags: list[str] = []
    variables: dict = {}

    model_config = {"populate_by_name": True}


@router.get("")
async def list_flows(repo: Repository = Depends(get_repo)):
    flows = repo.list_flows()
    return {
        "items": [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "tags": f.tags,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in flows
        ]
    }


@router.post("")
async def create_flow(body: FlowIn, repo: Repository = Depends(get_repo)):
    errs = validate_flow(_to_dict(body.yaml_content))
    if errs:
        raise HTTPException(status_code=400, detail="; ".join(errs))
    rec = repo.save_flow(
        name=body.name,
        yaml_content=body.yaml_content,
        description=body.description,
        tags=body.tags,
        variables=body.variables,
    )
    return {"id": rec.id, "name": rec.name}


@router.get("/{flow_id}")
async def get_flow(flow_id: int, repo: Repository = Depends(get_repo)):
    rec = repo.get_flow(flow_id)
    if not rec:
        raise HTTPException(status_code=404, detail="流程不存在")
    return {
        "id": rec.id,
        "name": rec.name,
        "description": rec.description,
        "yaml": rec.yaml_content,
        "tags": rec.tags,
        "variables": rec.variables,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


@router.put("/{flow_id}")
async def update_flow(flow_id: int, body: FlowIn, repo: Repository = Depends(get_repo)):
    rec = repo.get_flow(flow_id)
    if not rec:
        raise HTTPException(status_code=404, detail="流程不存在")
    errs = validate_flow(_to_dict(body.yaml_content))
    if errs:
        raise HTTPException(status_code=400, detail="; ".join(errs))
    rec = repo.save_flow(
        name=body.name,
        yaml_content=body.yaml_content,
        description=body.description,
        tags=body.tags,
        variables=body.variables,
    )
    return {"id": rec.id, "name": rec.name}


@router.delete("/{flow_id}")
async def delete_flow(flow_id: int, repo: Repository = Depends(get_repo)):
    ok = repo.delete_flow(flow_id)
    if not ok:
        raise HTTPException(status_code=404, detail="流程不存在")
    return {"ok": True}


@router.post("/validate")
async def validate(body: dict):
    """校验 YAML 文本。"""
    errs = validate_flow(_to_dict(body.get("yaml", "")))
    return {"valid": not errs, "errors": errs}


@router.get("/steps/list")
async def list_step_types():
    """列出可用的步骤类型。"""
    return {"steps": list_steps()}


def _to_dict(yaml_text: str) -> dict:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败: {e}")
    return data or {}
