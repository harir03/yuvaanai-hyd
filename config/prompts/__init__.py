# config/prompts package
# All LLM prompt templates — never hardcode prompts in agent code.

from config.prompts.extraction_prompts import *  # noqa: F401,F403
from config.prompts.consolidation_prompts import *  # noqa: F401,F403
from config.prompts.validation_prompts import *  # noqa: F401,F403
from config.prompts.organization_prompts import *  # noqa: F401,F403
from config.prompts.reasoning_prompts import *  # noqa: F401,F403
from config.prompts.research_prompts import *  # noqa: F401,F403
from config.prompts.evidence_prompts import *  # noqa: F401,F403
from config.prompts.cam_prompts import *  # noqa: F401,F403
from config.prompts.scoring_decision_prompts import *  # noqa: F401,F403
