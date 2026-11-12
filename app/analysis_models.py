"""Strict local validation of model findings and application-scored findings."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from evidence_rubric import BANDS
Category=Literal['documented_fact','possible_policy_inconsistency','insufficient_evidence']
Band=Literal['direct_contradiction','procedural_failure','discretionary_gray_area','weak_or_unsupported']
class StrictModel(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid',hide_input_in_errors=True)
class Finding(StrictModel):
    category:Category
    statement:str
    evidence_ids:list[str]
    policy_source_ids:list[str]
    reasoning:str
    limitations:list[str]
    rubric_band:Band
    policy_excerpt:str
    evidence_excerpt:str
    score_reason:str
    anticipated_corporate_defense:str = Field(min_length=1)
    rebuttal:str = Field(min_length=1)
TOSFinding = Finding

class Findings(StrictModel):
    summary:str
    findings:list[Finding]
    missing_evidence:list[str]
    review_questions:list[str]
    limitations:list[str]
class ScoredFinding(Finding):
    requested_rubric_band:Band
    rubric_score:int=Field(ge=0,le=100)
    score_adjustments:list[str]
    included_in_report:bool
    @model_validator(mode='after')
    def rubric_consistent(self):
        if self.rubric_score!=BANDS[self.rubric_band]:raise ValueError('Score must match the fixed rubric band.')
        if self.included_in_report!=(self.rubric_score>=40):raise ValueError('Report inclusion must match the score threshold.')
        return self
class ScoredFindings(StrictModel):
    summary:str
    findings:list[ScoredFinding]
    missing_evidence:list[str]
    review_questions:list[str]
    limitations:list[str]

def api_schema():
    # Inline the sole nested model so existing JSON Schema consumers stay stable.
    schema=Findings.model_json_schema();definition=schema.pop('$defs')['Finding']
    schema['properties']['findings']['items']=definition
    return schema
