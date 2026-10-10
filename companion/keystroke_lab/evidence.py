"""Immutable evidence shared by two independent coaching domains."""
from dataclasses import dataclass
from typing import Any
import math
from types import MappingProxyType
from collections.abc import Mapping

def freeze(value):
    if isinstance(value, Mapping):return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value,(list,tuple)):return tuple(freeze(v) for v in value)
    if isinstance(value,set):return frozenset(freeze(v) for v in value)
    return value

def plain(value):
    if isinstance(value,Mapping):return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,frozenset)):return [plain(v) for v in value]
    return value

@dataclass(frozen=True)
class Evidence:
    id: str
    value: Any
    observed_at: float
    source: str
    quality: str = 'observed'
    uncertainty: float = 0.0
    profile_id: str | None = None
    session_id: str | None = None
    def __post_init__(self):object.__setattr__(self,'value',freeze(self.value))

@dataclass(frozen=True)
class Snapshot:
    profile_id: str
    revision: int
    session_id: str
    captured_at: float
    evidence: tuple[Evidence, ...] = ()
    def to_dict(self):
        return {'profile_id':self.profile_id,'profile_revision':self.revision,
                'session_id':self.session_id,'captured_at':self.captured_at,
                'evidence':[dict(id=e.id,value=plain(e.value),observed_at=e.observed_at,
                                 source=e.source,quality=e.quality,uncertainty=e.uncertainty) for e in self.evidence]}

class ContextAssembler:
    def assemble(self, profile, session, now, evidence, max_age=.25):
        evidence=tuple(evidence)
        counts={e.id:sum(other.id==e.id for other in evidence) for e in evidence}
        accepted = tuple(e for e in evidence if counts[e.id]==1 and math.isfinite(e.observed_at)
                         and 0 <= now-e.observed_at <= max_age
                         and math.isfinite(e.uncertainty) and 0<=e.uncertainty<=1
                         and e.profile_id in (None,profile.profile_id) and e.session_id in (None,session)
                         and e.quality in ('observed','derived','inferred','unknown'))
        return Snapshot(profile.profile_id, profile.revision, session, now, accepted)


def validate_choice(answer, options):
    if not isinstance(answer, dict) or answer.get('choice') not in options:
        return False
    probabilities = answer.get('probabilities')
    confidence = answer.get('confidence')
    number = lambda x: type(x) in (float,int) and math.isfinite(x) and 0 <= x <= 1
    return (number(confidence) and isinstance(probabilities, dict)
            and set(probabilities) == set(options)
            and all(number(p) for p in probabilities.values())
            and abs(sum(probabilities.values())-1) < .001
            and probabilities[answer['choice']] >= max(probabilities.values())-1e-9)

class FeedbackPresenter:
    """Measurements never acquire certainty from an AI interpretation."""
    def render(self, finding):
        if finding.get('uncertainty', True): return ''
        domain = finding.get('domain')
        if domain == 'keystroke':
            return 'Possible input slip; review this attempt.' if finding.get('interpretation') == 'slip' else ''
        if domain == 'edit': return 'Possible edit for this observed situation.'
        return ''
