"""Built-in component registry and the three supported preset specifications."""

from __future__ import annotations

from aim_tool.domain import StepSpec, WorkflowSpec
from aim_tool.workflow.contracts import Step


class WorkflowError(ValueError):
    """A workflow is not safe or complete enough to run."""


class StepRegistry:
    def __init__(self) -> None:
        self._steps: dict[str, Step] = {}

    def register(self, step: Step) -> None:
        if (
            not step.id
            or step.version < 1
            or step.id in self._steps
            or not step.required_parameters <= step.parameter_schema.keys()
        ):
            raise WorkflowError(f"Invalid or duplicate component: {step.id}")
        self._steps[step.id] = step

    def get(self, component_id: str) -> Step:
        try:
            return self._steps[component_id]
        except KeyError as error:
            raise WorkflowError(f"Unknown component: {component_id}") from error


def preset(name: str) -> WorkflowSpec:
    """Create a plan; raw_develop applies only to NEF during planning."""
    ids: tuple[str, ...]
    if name == "location_only":
        ids = ("location", "export")
    elif name == "watermark_only":
        ids = ("raw_develop", "watermark", "export")
    elif name == "location_and_watermark":
        ids = ("location", "raw_develop", "watermark", "export")
    else:
        raise WorkflowError(f"Unknown preset: {name}")
    return WorkflowSpec(tuple(StepSpec(component_id) for component_id in ids))
