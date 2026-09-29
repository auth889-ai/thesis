"""POST /api/lifeos/compile: text in, a validated commitment out (model path when Bedrock is reachable, rules otherwise)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.lifeos.compiler import service

router = APIRouter(prefix="/api/lifeos", tags=["lifeos"])


class CompileRequest(BaseModel):
    person_id: str
    text: str = Field(..., min_length=3, examples=["Interview at TechNova in Banani on Friday 10 AM, bring CV and ID"])
    save: bool = Field(False, description="store the commitment when one was compiled")
    use_model: bool = Field(True, description="try the language model first; the rules always stand behind it")


def _llm():
    try:
        from app.agent.router import _llm as agent_llm
        return agent_llm()
    except Exception:                                                # noqa: BLE001 - no model: the rules path answers
        return None


@router.post("/compile")
def compile_text(req: CompileRequest):
    return service.compile(req.text, req.person_id, llm=_llm() if req.use_model else None, save=req.save)
