# Branch: feature/adversarial-resistance

## Feature B3: Adversarial Resistance

This branch implements the `AdversarialClassifier` to detect and mitigate malicious intents.

### Changes Made

- Created `AdversarialClassifier` in `backend/app/governance/adversarial_classifier.py` with a 4-intent taxonomy:
  - `NORMAL_QUESTION`
  - `SOLUTION_DEMAND`
  - `PROMPT_INJECTION`
  - `POLICY_BYPASS`
- Wired the classifier as a pre-routing hook in `backend/app/api/ws_router.py`.
- Flipped `state.policy.strict_mode = True` when adversarial intent is detected.
- Added comprehensive unit tests in `backend/tests/governance/test_adversarial.py`.
- Exported new classes in `backend/app/governance/__init__.py`.

All tests pass.
