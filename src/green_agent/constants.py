import os

MAX_HTML_CONTEXT_LENGTH = 40000  # Increased from 25K for more page context
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "1"))  # Increased from 1 to 2

TASK_RESULT_OUTPUT_DIR = ".output/results"
TASK_RESULT_FILE_NAME = "result"
TASK_RESULT_SCREENSHOTS_FOLDER = "trajectory"

EVAL_MODEL = os.getenv("EVAL_MODEL", "gemini-2.5-flash")
EVAL_MODE = "WebJudge_Online_Mind2Web_eval"
EVAL_RESULT_OUTPUT_DIR = ".output/eval"
