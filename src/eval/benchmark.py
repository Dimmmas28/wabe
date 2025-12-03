import logging
from openai import BaseModel

from eval.online_mind2web.run import parallel_eval

logger = logging.getLogger(__name__)


class Config(BaseModel):
    api_key: str
    mode: str = "WebJudge_Online_Mind2Web_eval"
    trajectories_dir: str
    model: str = "gemini-2.5-flash"
    output_path: str
    score_threshold: int = 3


def run_benchmark_eval(data: Config, num_workers: int = 60) -> float:
    try:
        success_rate = parallel_eval(data, num_workers)
        return success_rate
    except Exception as e:
        logger.exception(f"Unexpected error during evaluation: {str(e)}")
        return 0
