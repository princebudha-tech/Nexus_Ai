"""DeterministicGuardrail orchestrating all five evaluation stages."""
from dataclasses import dataclass
from typing import Optional

from nexus.core.config import SecurityConfig
from nexus.core.exceptions import GuardrailViolation, PermissionDeniedError
from nexus.core.interfaces import ActionPlan, GuardrailDecision, GuardrailResult, GuardrailEngine

from nexus.security.validation import validate_action_plan
from nexus.security.permissions import PermissionProfile, DEFAULT_PROFILES, PermissionLevel
from nexus.security.rate_limiter import RateLimiter
from nexus.security.confirmation import ConfirmationStore
from nexus.security.audit import AuditLogger


class ConfirmationRequiredError(GuardrailViolation):
    """Raised when confirmation is required, carries confirmation_id in details."""


@dataclass
class DeterministicGuardrail(GuardrailEngine):
    security_config: SecurityConfig
    permission_profile: PermissionProfile = DEFAULT_PROFILES[PermissionLevel.STANDARD]
    rate_limiter: Optional[RateLimiter] = None
    confirmation_store: Optional[ConfirmationStore] = None
    audit_logger: Optional[AuditLogger] = None

    def __post_init__(self):
        if self.rate_limiter is None:
            self.rate_limiter = RateLimiter(self.security_config.max_actions_per_minute)
        if self.confirmation_store is None:
            self.confirmation_store = ConfirmationStore()
        if self.audit_logger is None:
            self.audit_logger = AuditLogger(self.security_config.audit_log_path)

    def set_permission_profile(self, profile: PermissionProfile) -> None:
        """Switch runtime permission profile."""
        self.permission_profile = profile

    def evaluate(self, plan: ActionPlan) -> GuardrailResult:
        """Run through all five stages; first match wins."""
        # Stage 1: Structural validation
        try:
            validate_action_plan(plan)
        except GuardrailViolation as exc:
            result = GuardrailResult(decision=GuardrailDecision.BLOCKED, reason=exc.message, plan=plan)
            self.audit_logger.log_decision(result)
            return result

        # Stage 2: Hard denylist (never overridable)
        for blocked in self.security_config.blocked_package_substrings:
            if plan.target and blocked in plan.target:
                reason = f"Target matches blocked package substring: {blocked}"
                result = GuardrailResult(decision=GuardrailDecision.BLOCKED, reason=reason, plan=plan)
                self.audit_logger.log_decision(result)
                return result

        # Stage 3: Permission profile
        if plan.action_type in self.permission_profile.blocked_action_types:
            reason = f"Action type {plan.action_type!r} blocked by profile {self.permission_profile.name}"
            result = GuardrailResult(decision=GuardrailDecision.BLOCKED, reason=reason, plan=plan)
            self.audit_logger.log_decision(result)
            return result

        # Stage 4: Rate limiting
        if not self.rate_limiter.allow_action():
            reason = "Rate limit exceeded (max actions per minute)"
            result = GuardrailResult(decision=GuardrailDecision.BLOCKED, reason=reason, plan=plan)
            self.audit_logger.log_decision(result)
            return result

        # Stage 5: Confirmation required?
        if plan.action_type in self.security_config.confirm_required_actions:
            confirmation_id = self.confirmation_store.issue(plan)
            result = GuardrailResult(
                decision=GuardrailDecision.REQUIRES_CONFIRMATION,
                reason="Action requires user confirmation",
                plan=plan,
                confirmation_id=confirmation_id,
            )
            self.audit_logger.log_decision(result)
            return result

        # Otherwise: ALLOWED
        result = GuardrailResult(decision=GuardrailDecision.ALLOWED, reason="Allowed by policy", plan=plan)
        self.audit_logger.log_decision(result)
        return result

    def confirm(self, confirmation_id: str, plan: ActionPlan) -> bool:
        """Redeem a confirmation token. Returns True if successful."""
        if self.confirmation_store.redeem(confirmation_id, plan):
            # Log an allowed decision after confirmation
            result = GuardrailResult(decision=GuardrailDecision.ALLOWED, reason="Confirmed by user", plan=plan)
            self.audit_logger.log_decision(result)
            return True
        return False

    def evaluate_or_raise(self, plan: ActionPlan) -> ActionPlan:
        """Evaluate and raise exception on block or confirmation."""
        result = self.evaluate(plan)
        if result.decision == GuardrailDecision.BLOCKED:
            raise GuardrailViolation(result.reason, details={"plan": plan})
        if result.decision == GuardrailDecision.REQUIRES_CONFIRMATION:
            raise ConfirmationRequiredError(
                "Confirmation required",
                details={"confirmation_id": result.confirmation_id, "plan": plan},
            )
        return plan