from enum import Enum
from dataclasses import dataclass
import re
from typing import Optional

class AdversarialIntent(Enum):
    NORMAL_QUESTION = "NORMAL_QUESTION"
    SOLUTION_DEMAND = "SOLUTION_DEMAND"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    POLICY_BYPASS = "POLICY_BYPASS"

@dataclass
class AdversarialClassificationResult:
    intent: AdversarialIntent
    confidence: float
    is_adversarial: bool
    reason: Optional[str] = None

class AdversarialClassifier:
    def __init__(self):
        self.solution_patterns = [
            r"(?i)\b(?:just|only)\s+give\s+(?:me\s+)?(?:the\s+)?(?:answer|solution)\b",
            r"(?i)\bwhat\s+is\s+(?:the\s+)?(?:final\s+)?answer\b",
            r"(?i)\btell\s+me\s+the\s+answer\b"
        ]
        self.injection_patterns = [
            r"(?i)\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)\b",
            r"(?i)\byou\s+(?:are|must)\s+now\b",
            r"(?i)\bsystem\s+prompt\b"
        ]
        self.bypass_patterns = [
            r"(?i)\b(?:pretend|act)\s+as\s+(?:if|though)\b",
            r"(?i)\bthis\s+is\s+(?:a\s+)?(?:test|experiment)\b",
            r"(?i)\bi\s+already\s+(?:know|did)\s+the\s+work\b"
        ]

    def evaluate(self, user_content: str) -> AdversarialClassificationResult:
        for pattern in self.injection_patterns:
            if re.search(pattern, user_content):
                return AdversarialClassificationResult(
                    intent=AdversarialIntent.PROMPT_INJECTION,
                    confidence=0.9,
                    is_adversarial=True,
                    reason="Matched prompt injection pattern"
                )
                
        for pattern in self.bypass_patterns:
            if re.search(pattern, user_content):
                return AdversarialClassificationResult(
                    intent=AdversarialIntent.POLICY_BYPASS,
                    confidence=0.8,
                    is_adversarial=True,
                    reason="Matched policy bypass pattern"
                )
                
        for pattern in self.solution_patterns:
            if re.search(pattern, user_content):
                return AdversarialClassificationResult(
                    intent=AdversarialIntent.SOLUTION_DEMAND,
                    confidence=0.9,
                    is_adversarial=True,
                    reason="Matched solution demand pattern"
                )

        return AdversarialClassificationResult(
            intent=AdversarialIntent.NORMAL_QUESTION,
            confidence=1.0,
            is_adversarial=False
        )
