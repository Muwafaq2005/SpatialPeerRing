"""
Peer Error Taxonomy & Isolation Guardrails.

Defines the strict separation between:
- Arithmetic Error Peer (Alice): calculation slips, sign flips, off-by-one, addition/multiplication mistakes.
- Conceptual Error Peer (Charlie): structural misconceptions, order of operations violations, illegal cancellations.

Zero cross-contamination is allowed.
"""

from enum import Enum
from typing import List, Dict, Any, Tuple


class ArithmeticErrorType(str, Enum):
    """Specific categories of arithmetic calculation slips for Alice."""
    SIGN_FLIP = "sign_flip"  # e.g., -3 * -4 = -12 or -(x - 5) = -x - 5
    OFF_BY_ONE = "off_by_one"  # e.g., 7 + 8 = 16 or counting fenceposts
    MULTIPLICATION_SLIP = "multiplication_slip"  # e.g., 6 * 7 = 48 or 3 * 4 = 7
    ADDITION_SLIP = "addition_slip"  # e.g., 17 + 25 = 41
    DISTRIBUTION_ARITHMETIC = "distribution_arithmetic"  # e.g., 3(x + 4) = 3x + 7 (added instead of multiplied)


class ConceptualErrorType(str, Enum):
    """Specific categories of structural/conceptual misconceptions for Charlie."""
    ORDER_OF_OPERATIONS = "order_of_operations"  # e.g., 2 + 3 * 5 = (2 + 3) * 5 = 25
    FRESHMAN_DREAM = "freshman_dream"  # e.g., (a + b)^2 = a^2 + b^2 or sqrt(a^2 + b^2) = a + b
    ILLEGAL_CANCELLATION = "illegal_cancellation"  # e.g., (x + 3) / x = 3
    LIKE_TERMS_CONFUSION = "like_terms_confusion"  # e.g., 3x + 2 = 5x or x^2 + x = x^3
    NON_LINEAR_DISTRIBUTION = "non_linear_distribution"  # e.g., 2(3 * x) = 6 * 2x


def validate_error_isolation(
    agent_id: str,
    error_type: str
) -> Tuple[bool, str]:
    """
    Validate that an agent only emits errors within its assigned taxonomy.
    """
    if agent_id in ["alice-peer", "mock-alice-arithmetic"]:
        valid_arithmetic = [e.value for e in ArithmeticErrorType]
        if error_type in valid_arithmetic:
            return True, f"Valid arithmetic error '{error_type}' for Alice."
        return False, f"Violation: Alice cannot emit non-arithmetic error '{error_type}'."

    elif agent_id in ["charlie-peer", "mock-charlie-conceptual"]:
        valid_conceptual = [e.value for e in ConceptualErrorType]
        if error_type in valid_conceptual:
            return True, f"Valid conceptual error '{error_type}' for Charlie."
        return False, f"Violation: Charlie cannot emit non-conceptual error '{error_type}'."

    return True, f"Unrestricted agent {agent_id}"
