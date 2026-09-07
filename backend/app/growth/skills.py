"""Discoverable data specifications. Revisions cannot add executable tools."""
import json
from pathlib import Path

from sqlalchemy import select

from .models import Evidence, SkillRevision
from .store import record

REQUIRED = {"purpose", "inputs", "tools", "process", "output", "success_signal", "failure_conditions", "cost_expectation"}
TOOLS = {"public_search", "evidence_read", "qualification", "model", "draft", "send_email",
         "reply_read", "funnel_read", "experiment_update", "belief_update", "product_feedback"}


def validate(spec):
    if not REQUIRED.issubset(spec) or not isinstance(spec["tools"], list):
        raise ValueError("Skill specification is missing required fields")
    if not set(spec["tools"]).issubset(TOOLS):
        raise ValueError("Skill cannot add execution capabilities")
    if len(json.dumps(spec)) > 10000:
        raise ValueError("Skill specification exceeds context budget")
    if not all(spec[k] for k in REQUIRED):
        raise ValueError("Skill fields cannot be empty")
    return {"schema": "passed", "tool_allowlist": "passed"}


def bootstrap_skills(db):
    for path in sorted((Path(__file__).parent / "skills").glob("*.json")):
        specs = json.loads(path.read_text(encoding="utf-8"))
        for name, spec in specs.items():
            if db.scalar(select(SkillRevision.id).where(SkillRevision.name == name)):
                continue
            db.add(SkillRevision(name=name, version=1, specification=spec,
                                 status="active", validation=validate(spec)))
    db.flush()


def active_skill(db, name):
    row = db.scalar(select(SkillRevision).where(SkillRevision.name == name, SkillRevision.status == "active")
                    .order_by(SkillRevision.version.desc()))
    if not row:
        raise ValueError("Unknown skill")
    return row


def propose_revision(db, name, specification, evidence_ids):
    previous = active_skill(db, name)
    validation = validate(specification)
    if not evidence_ids or len(list(db.scalars(select(Evidence.id).where(Evidence.id.in_(evidence_ids))))) != len(set(evidence_ids)):
        raise ValueError("Skill changes require retained outcome evidence")
    latest = db.scalar(select(SkillRevision).where(SkillRevision.name == name).order_by(SkillRevision.version.desc()))
    revision = SkillRevision(name=name, version=latest.version + 1, specification=specification,
                             status="candidate", evidence_ids=evidence_ids, validation=validation)
    db.add(revision)
    db.flush()
    record(db, f"skill:{name}:{revision.version}", "SKILL_PROPOSED", name,
           {"previous": previous.version, "candidate": revision.version, "evidence_ids": evidence_ids})
    return revision


def activate_revision(db, name, version):
    # Owner-only API; activation also provides rollback to any validated revision.
    target = db.scalar(select(SkillRevision).where(SkillRevision.name == name, SkillRevision.version == version))
    if not target:
        raise ValueError("Unknown skill revision")
    validate(target.specification)
    for row in db.scalars(select(SkillRevision).where(SkillRevision.name == name, SkillRevision.status == "active")):
        row.status = "retired"
    target.status = "active"
    record(db, f"skill-activation:{name}:{version}:{__import__('time').time_ns()}", "SKILL_ACTIVATED", name,
           {"version": version}, source="owner")
