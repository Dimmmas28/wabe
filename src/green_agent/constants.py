import os

MAX_HTML_CONTEXT_LENGTH = 20000
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "5"))

TASK_RESULT_OUTPUT_DIR = ".output/results"
TASK_RESULT_FILE_NAME = "result"
TASK_RESULT_SCREENSHOTS_FOLDER = "trajectory"

EVAL_MODEL = "gemini-2.5-pro"
EVAL_MODE = "WebJudge_Online_Mind2Web_eval"
EVAL_RESULT_OUTPUT_DIR = ".output/eval"
