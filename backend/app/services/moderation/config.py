"""Configuration and severity definitions for the moderation engine."""

from dataclasses import dataclass, field
from typing import Mapping, Sequence


# Explicit platform policy moderation categories and their base severities (0.0 to 1.0)
DEFAULT_POLICY_SEVERITIES: dict[str, float] = {
    "child_safety": 1.0,
    "self_harm": 1.0,
    "extreme_violence": 0.95,
    "violence": 0.85,
    "threats": 0.85,
    "graphic_content": 0.80,
    "weapons": 0.70,
    "dangerous_behavior": 0.60,
    "harassment": 0.60,
    "toxic_language": 0.50,
    "toxicity": 0.50,
    "insult": 0.45,
    "profanity": 0.30,
}

# Context-to-policy category mapping: maps contextual descriptions/situations to platform policy categories
DEFAULT_CONTEXT_POLICY_MAPPING: dict[str, tuple[str, ...]] = {
    # Threat / Hostile / Altercation
    "threatening interaction": ("threats",),
    "threatening altercation": ("threats",),
    "threatening behavior": ("threats",),
    "threats": ("threats",),
    "threat": ("threats",),
    "threatening": ("threats",),
    # Violence / Assault / Physical Fight
    "violent confrontation": ("violence",),
    "violent interaction": ("violence",),
    "violent altercation": ("violence",),
    "physical assault": ("violence",),
    "physical altercation": ("violence",),
    "physical violence": ("violence",),
    "assault": ("violence",),
    "violence": ("violence",),
    "violent": ("violence",),
    "fight": ("violence",),
    "fighting": ("violence",),
    "slapping": ("violence",),
    "hitting": ("violence",),
    "punching": ("violence",),
    "extreme violence": ("extreme_violence",),
    # Self-Harm
    "self-harm situation": ("self_harm",),
    "self harm situation": ("self_harm",),
    "self-harm": ("self_harm",),
    "self harm": ("self_harm",),
    "suicide": ("self_harm",),
    "suicidal behavior": ("self_harm",),
    # Child Safety
    "child endangerment": ("child_safety",),
    "child abuse": ("child_safety",),
    "child safety concern": ("child_safety",),
    "child exploitation": ("child_safety",),
    "child safety": ("child_safety",),
    # Harassment / Bullying
    "harassment": ("harassment",),
    "bullying": ("harassment",),
    "intimidation": ("harassment",),
    # Dangerous behavior
    "dangerous behavior": ("dangerous_behavior",),
    "dangerous stunt": ("dangerous_behavior",),
    "reckless behavior": ("dangerous_behavior",),
    # Weapons
    "weapon brandishing": ("weapons",),
    "armed altercation": ("weapons", "violence"),
    "gun violence": ("weapons", "violence"),
    # Toxic speech / hate
    "hate speech": ("toxic_language",),
    "verbal abuse": ("toxic_language", "harassment"),
}

# Verified benign context categories that mitigate dual-use objects
BENIGN_CONTEXT_CATEGORIES: frozenset[str] = frozenset({
    "cooking",
    "food_preparation",
    "culinary",
    "educational",
    "crafts",
    "sports",
    "benign",
    "safe",
    "peaceful",
    "neutral_scene",
})

# Threatening or hostile context categories that escalate risk
HOSTILE_CONTEXT_CATEGORIES: frozenset[str] = frozenset({
    "threat",
    "threats",
    "violence",
    "violent",
    "threatening",
    "assault",
    "fight",
    "hostile",
    "dangerous_behavior",
    "self_harm",
    "child_safety",
})

# Objects that may be weapons in hostile/unverified context but benign tools in appropriate context
DUAL_USE_OBJECTS: frozenset[str] = frozenset({
    "knife",
    "scissors",
    "baseball bat",
})

# Explicit dedicated weapon categories
EXPLICIT_WEAPONS: frozenset[str] = frozenset({
    "gun",
    "pistol",
    "rifle",
    "firearm",
    "sword",
    "dagger",
    "weapon",
    "weapons",
})


@dataclass(frozen=True)
class ModerationConfig:
    """Configurable weights, thresholds, and severity ratings."""

    policy_severities: Mapping[str, float] = field(default_factory=lambda: DEFAULT_POLICY_SEVERITIES.copy())
    context_policy_mapping: Mapping[str, Sequence[str] | str] = field(
        default_factory=lambda: DEFAULT_CONTEXT_POLICY_MAPPING.copy()
    )
    benign_context_categories: frozenset[str] = BENIGN_CONTEXT_CATEGORIES
    hostile_context_categories: frozenset[str] = HOSTILE_CONTEXT_CATEGORIES
    low_risk_threshold: float = 0.30
    medium_risk_threshold: float = 0.60
    high_risk_threshold: float = 0.85
    auto_reject_threshold: float = 0.85
    review_threshold: float = 0.40
    min_signal_confidence: float = 0.30

    benign_mitigation_multiplier: float = 0.0  # Fully mitigates dual-use objects in verified benign context
    hostile_aggravation_multiplier: float = 1.30
    cross_modal_corroboration_multiplier: float = 1.25

    def get_policy_severity(self, category: str) -> float:
        """Lookup base severity for a policy category, returning 0.0 for harmless everyday objects."""
        norm_cat = category.strip().lower()
        if norm_cat in self.policy_severities:
            return self.policy_severities[norm_cat]
        # Check substring matches against policy categories
        for key, val in self.policy_severities.items():
            if key in norm_cat or norm_cat in key:
                return val
        # Unknown non-policy items are treated as 0.0 severity (not inherently policy violations)
        return 0.0

    def map_context_category(self, category: str) -> tuple[str, ...]:
        """Map a contextual interpretation category into standard platform policy categories."""
        if not category:
            return ()
        orig_norm = category.strip().lower()
        norm_cat = orig_norm.replace("_", " ")

        # 1. Benign check: if category contains benign markers, return empty
        if any(b in norm_cat for b in self.benign_context_categories):
            return ()

        # 2. Exact match in context_policy_mapping (check original & normalized)
        if orig_norm in self.context_policy_mapping:
            val = self.context_policy_mapping[orig_norm]
            return tuple(val) if isinstance(val, (tuple, list, set)) else (str(val),)
        if norm_cat in self.context_policy_mapping:
            val = self.context_policy_mapping[norm_cat]
            return tuple(val) if isinstance(val, (tuple, list, set)) else (str(val),)

        # 3. Substring / phrase matching against context_policy_mapping
        mapped: list[str] = []
        for phrase, policy_cats in self.context_policy_mapping.items():
            norm_phrase = phrase.strip().lower().replace("_", " ")
            if norm_phrase in norm_cat or norm_cat in norm_phrase:
                if isinstance(policy_cats, (tuple, list, set)):
                    for cat in policy_cats:
                        if cat not in mapped:
                            mapped.append(cat)
                else:
                    if policy_cats not in mapped:
                        mapped.append(str(policy_cats))

        if mapped:
            return tuple(mapped)

        # 4. Check against direct policy severities
        for policy_cat in self.policy_severities:
            norm_policy = policy_cat.replace("_", " ")
            if norm_policy in norm_cat or norm_cat in norm_policy or policy_cat in orig_norm:
                if policy_cat not in mapped:
                    mapped.append(policy_cat)

        return tuple(mapped)
