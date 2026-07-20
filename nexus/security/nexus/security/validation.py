"""Structural validation of ActionPlan."""
from nexus.core.exceptions import GuardrailViolation
from nexus.core.interfaces import ActionPlan

# Exhaustive registry of known action types
KNOWN_ACTION_TYPES = frozenset({
    "tap",
    "type",
    "swipe",
    "open_app",
    "close_app",
    "send_message",
    "make_call",
    "delete_app",
    "power_state",
    "delete_file",
    "deploy_code",
    "browse_url",
    "click",
    "scroll",
    "take_screenshot",
    "get_element_text",
})


def validate_action_plan(plan: ActionPlan) -> None:
    """
    Structural checks only. Raises GuardrailViolation if malformed.
    """
    if not isinstance(plan, ActionPlan):
        raise GuardrailViolation("Plan must be an ActionPlan instance", details={"plan": str(plan)})

    if plan.action_type not in KNOWN_ACTION_TYPES:
        raise GuardrailViolation(
            f"Unknown action type: {plan.action_type!r}",
            details={"action_type": plan.action_type, "known_types": sorted(KNOWN_ACTION_TYPES)}
        )

    # Check that target is provided if needed (optional)
    # Check params type
    if not isinstance(plan.params, dict):
        raise GuardrailViolation("params must be a dict", details={"params": plan.params})

    # Check field sizes to prevent abuse
    if len(plan.action_type) > 100:
        raise GuardrailViolation("action_type too long", details={"length": len(plan.action_type)})
    if plan.target and len(plan.target) > 500:
        raise GuardrailViolation("target too long", details={"length": len(plan.target)})
    if len(plan.reasoning) > 2000:
        raise GuardrailViolation("reasoning too long", details={"length": len(plan.reasoning)})
    # Ensure no control characters in strings
    for field in ("action_type", "target", "reasoning", "requested_by_agent"):
        val = getattr(plan, field)
        if val and any(ord(c) < 32 for c in val):
            raise GuardrailViolation(f"Control character in {field}", details={"field": field})