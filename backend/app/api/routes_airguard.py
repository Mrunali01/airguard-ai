import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.groq_supervisor_agent import GroqSupervisorAgent
from ml.config import PROJECT_ROOT


router = APIRouter(prefix="/api/airguard", tags=["airguard"])

DATA_DIR = PROJECT_ROOT / "backend" / "data" / "sample"


class CommandActionRequest(BaseModel):
    action: str = Field(..., description="Human-readable operation or intervention name.")
    action_id: str | None = Field(default=None, description="Stable frontend/backend intervention identifier.")
    station_id: str | int | None = Field(default=None, description="Monitoring station identifier.")
    screen: str | None = Field(default=None, description="Dashboard screen that initiated the action.")
    notes: str | None = Field(default=None, description="Optional operator note.")


class VerificationUpdateRequest(BaseModel):
    action_id: str
    check: str
    checked: bool
    action: str | None = None
    station_id: str | int | None = None


WorkflowState = Dict[str, Any]

WORKFLOW_STORE: Dict[str, WorkflowState] = {}
VERIFICATION_KEYS = {"photo", "evidence", "engineer"}
TERMINAL_STATUSES = {"Rejected", "Outcome recorded"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_workflow(action_id: str, action: str | None = None) -> WorkflowState:
    return {
        "action_id": action_id,
        "action": action,
        "status": "Proposed",
        "checks": {
            "photo": False,
            "evidence": False,
            "engineer": False,
        },
        "audit_log": [
            {
                "event": "created",
                "at": utc_now(),
                "message": "Intervention proposed by AirGuard evidence workflow.",
            }
        ],
        "updated_at": utc_now(),
    }


def workflow_for(payload: CommandActionRequest) -> WorkflowState | None:
    if not payload.action_id:
        return None

    workflow = WORKFLOW_STORE.setdefault(
        payload.action_id,
        default_workflow(payload.action_id, payload.action),
    )
    workflow["action"] = payload.action
    return workflow


def checks_complete(workflow: WorkflowState) -> bool:
    checks = workflow.get("checks", {})
    return all(bool(checks.get(key)) for key in VERIFICATION_KEYS)


def append_event(workflow: WorkflowState, event: str, message: str, notes: str | None = None) -> None:
    workflow["updated_at"] = utc_now()
    workflow.setdefault("audit_log", []).append(
        {
            "event": event,
            "at": workflow["updated_at"],
            "message": message,
            "notes": notes,
        }
    )


def apply_transition(action_type: str, payload: CommandActionRequest) -> WorkflowState | None:
    workflow = workflow_for(payload)
    if workflow is None:
        return None

    current = workflow["status"]
    if current in TERMINAL_STATUSES and action_type != "reject_intervention":
        raise HTTPException(status_code=409, detail=f"Workflow is terminal: {current}")

    transitions = {
        "request_verification": ({"Proposed"}, "Under verification"),
        "approve_intervention": ({"Proposed", "Under verification"}, "Approved"),
        "reject_intervention": (
            {"Proposed", "Under verification", "Approved", "Dispatched", "In progress", "Completed"},
            "Rejected",
        ),
        "dispatch_intervention": ({"Approved"}, "Dispatched"),
        "start_intervention": ({"Dispatched"}, "In progress"),
        "complete_intervention": ({"In progress"}, "Completed"),
        "record_outcome": ({"Completed"}, "Outcome recorded"),
    }

    if action_type not in transitions:
        return workflow

    allowed, next_status = transitions[action_type]
    if current not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot {action_type.replace('_', ' ')} from status {current}",
        )

    if action_type == "approve_intervention" and not checks_complete(workflow):
        raise HTTPException(
            status_code=409,
            detail="Approval requires field photo, evidence confirmation, and ward engineer approval.",
        )

    workflow["status"] = next_status
    append_event(
        workflow,
        action_type,
        f"Workflow moved from {current} to {next_status}.",
        payload.notes,
    )
    return workflow


def command_ack(action_type: str, payload: CommandActionRequest) -> Dict[str, Any]:
    workflow = apply_transition(action_type, payload)
    return {
        "status": "accepted",
        "action_type": action_type,
        "action": payload.action,
        "action_id": payload.action_id,
        "station_id": payload.station_id,
        "screen": payload.screen,
        "human_review_required": True,
        "workflow": workflow,
        "workflows": WORKFLOW_STORE,
        "message": (
            "Command recorded. Workflow state updated by backend; field verification "
            "and authorized municipal approval remain required."
        ),
    }


def read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path.name}",
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/health")
def airguard_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "AirGuard AI",
        "message": "AirGuard API is running",
    }


@router.get("/real-snapshot")
def get_real_snapshot() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "real_geospatial_snapshot.json")


@router.get("/forecast-benchmark")
def get_forecast_benchmark() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "real_forecast_benchmark_metrics.json")


@router.get("/forecast-validation")
def get_forecast_validation() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "forecast_validation_tool_output.json")


@router.get("/supervisor")
def get_supervisor_output() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "supervisor_agent_output.json")


@router.get("/citizen-advisory")
def get_citizen_advisory() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "citizen_advisory_agent_output.json")

@router.get("/demo-output")
def get_airguard_demo_output() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "airguard_demo_output.json")


@router.get("/intervention-workflows")
def get_intervention_workflows() -> Dict[str, Any]:
    return {
        "status": "ok",
        "workflows": WORKFLOW_STORE,
    }


@router.post("/intervention-workflows/verification")
def update_intervention_verification(payload: VerificationUpdateRequest) -> Dict[str, Any]:
    if payload.check not in VERIFICATION_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown verification check: {payload.check}")

    workflow = WORKFLOW_STORE.setdefault(
        payload.action_id,
        default_workflow(payload.action_id, payload.action),
    )

    if workflow["status"] in {"Approved", "Dispatched", "In progress", "Completed", "Outcome recorded", "Rejected"}:
        raise HTTPException(
            status_code=409,
            detail=f"Verification cannot be changed after status {workflow['status']}",
        )

    workflow["checks"][payload.check] = payload.checked
    append_event(
        workflow,
        "verification_updated",
        f"{payload.check} set to {payload.checked}.",
    )

    return {
        "status": "accepted",
        "workflow": workflow,
        "workflows": WORKFLOW_STORE,
        "message": "Verification checklist updated by backend.",
    }

@router.get("/cpcb-aqi")
def get_cpcb_aqi() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "cpcb_aqi_output.json")


@router.get("/remote-sensing")
def get_remote_sensing_evidence() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "remote_sensing_evidence.json")


@router.get("/groq-supervisor")
def get_groq_supervisor_output() -> Dict[str, Any]:
    return read_json_file(DATA_DIR / "groq_supervisor_agent_output.json")


@router.post("/run-groq-supervisor")
def run_groq_supervisor() -> Dict[str, Any]:
    try:
        agent = GroqSupervisorAgent()
        result = agent.run()

        output_path = DATA_DIR / "groq_supervisor_agent_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/commands/request-verification")
def request_verification(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("request_verification", payload)


@router.post("/commands/approve-intervention")
def approve_intervention(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("approve_intervention", payload)


@router.post("/commands/reject-intervention")
def reject_intervention(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("reject_intervention", payload)


@router.post("/commands/dispatch-intervention")
def dispatch_intervention(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("dispatch_intervention", payload)


@router.post("/commands/start-intervention")
def start_intervention(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("start_intervention", payload)


@router.post("/commands/complete-intervention")
def complete_intervention(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("complete_intervention", payload)


@router.post("/commands/record-outcome")
def record_outcome(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("record_outcome", payload)


@router.post("/commands/approve-advisory")
def approve_advisory(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("approve_advisory", payload)


@router.post("/commands/regenerate-advisory")
def regenerate_advisory(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("regenerate_advisory", payload)


@router.post("/commands/export-memo")
def export_memo(payload: CommandActionRequest) -> Dict[str, Any]:
    return command_ack("export_memo", payload)
