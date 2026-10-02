"""AI assistance contracts. Suggestions always remain ordinary editor drafts."""
from typing import Any, List, Literal, Optional, Union

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr

from .schemas import Assertion, Contract, Path, Step


class SuggestAssertionsRequest(Contract):
    steps: List[Step] = Field(min_length=1, max_length=100)
    debug_session_id: str = Field(min_length=1, max_length=100)
    editor_id: str = Field(min_length=1, max_length=100)
    env_id: Optional[int] = None
    step_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(default="", max_length=2000)
    draft_token: str = Field(min_length=1, max_length=200)


class ExplainFailureRequest(Contract):
    run_id: str = Field(min_length=1, max_length=100)


class FeedbackRequest(Contract):
    call_id: str = Field(min_length=1, max_length=100)
    action: Literal["accepted", "modified", "dismissed", "undone"]
    selected_count: int = Field(default=0, ge=0, le=20)
    modified_count: int = Field(default=0, ge=0, le=20)


class Evidence(Contract):
    path: Path
    type: str


class Suggestion(Contract):
    assertion: Assertion
    reason: str
    evidence: Evidence


class Fact(Contract):
    id: str
    step_id: str
    path: Path
    message: str


class ExplainedItem(Contract):
    text: str = Field(max_length=800)
    evidence_ids: List[str] = Field(min_length=1, max_length=20)


class ModelAssertion(Contract):
    path: Path
    op: Literal["eq", "ne", "contains", "exists", "not_empty", "gt", "gte", "lt", "lte", "type", "length", "is_2xx"]
    expected: Union[StrictStr, StrictInt, StrictFloat, StrictBool, None]


class ModelSuggestion(Contract):
    assertion: ModelAssertion
    reason: str = Field(max_length=500)


class ModelSuggestions(Contract):
    # Each item is validated separately so rejected suggestions are visible.
    suggestions: List[Any] = Field(max_length=20)


class ModelExplanation(Contract):
    possible_causes: List[ExplainedItem] = Field(max_length=5)
    next_steps: List[ExplainedItem] = Field(max_length=5)
