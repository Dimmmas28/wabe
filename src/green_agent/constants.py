import os

MAX_HTML_CONTEXT_LENGTH = 40000  # Increased from 25K for more page context
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "1"))  # Increased from 1 to 2

TASK_RESULT_OUTPUT_DIR = ".output/results"
TASK_RESULT_FILE_NAME = "result"
TASK_RESULT_SCREENSHOTS_FOLDER = "trajectory"

# Use gemini-3-flash-preview for evaluation - more capable model for accurate judging
# Can be overridden via EVAL_MODEL environment variable
EVAL_MODEL = os.getenv("EVAL_MODEL", "gemini-3-flash-preview")
EVAL_MODE = "WebJudge_Online_Mind2Web_eval"
EVAL_RESULT_OUTPUT_DIR = ".output/eval"
