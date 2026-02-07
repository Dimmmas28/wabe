import argparse
import asyncio
import copy
import json
import logging
import multiprocessing
import os
import re
import time

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Delay between tasks within a worker process (seconds)
INTER_TASK_DELAY = 60.0


def get_step_number(filename: str) -> int:
    """Extract step number from filename for sorting.

    Args:
        filename: Filename like 'step_000.jpg' or 'step_003_final.jpg'

    Returns:
        Integer step number, or 999999 for files without digits (sorted last)
    """
    matches = re.findall(r"\d+", filename)
    if matches:
        return int(matches[0])
    return 999999  # Files without digits go last


from eval.online_mind2web.methods.agenttrek_eval import *
from eval.online_mind2web.methods.automomous_eval import *
from eval.online_mind2web.methods.webjudge_general_eval import *
from eval.online_mind2web.methods.webjudge_online_mind2web import *
from eval.online_mind2web.methods.webvoyager_eval import *
from eval.online_mind2web.utils import OpenaiEngine, extract_predication

load_dotenv()


def auto_eval(args, task_subset, final_predicted_labels, lock, model):
    ################## get the already done task id ###############
    output_json_path = os.path.join(
        args.output_path,
        f"{args.mode}_{args.model}_score_threshold_{args.score_threshold}_auto_eval_results.json",
    )
    already_ids = []
    if os.path.exists(output_json_path):
        with open(output_json_path, "r") as f:
            already_data = f.read()
        already_tasks = already_data.splitlines()
        for item in already_tasks:
            item = json.loads(item)
            already_ids.append(item["task_id"])

    logger.info(f"The number of already done tasks: {len(already_ids)}")
    print(f"The number of already done tasks: {len(already_ids)}")

    for idx, task_id in enumerate(task_subset):
        # Add delay between tasks to avoid rate limiting (skip first task)
        if idx > 0:
            logger.info(f"Waiting {INTER_TASK_DELAY}s before next task evaluation...")
            time.sleep(INTER_TASK_DELAY)
        # Skip already done task
        if task_id in already_ids:
            continue

        trajectory_images_path = os.path.join(
            args.trajectories_dir, task_id, "trajectory"
        )
        screenshot_paths = []
        thoughts = None
        action_history = None
        final_result_response = None
        input_image_paths = None
        task_description = None
        # Load results
        with open(os.path.join(args.trajectories_dir, task_id, "result.json")) as f:
            result = json.load(f)
            output_results = copy.deepcopy(result)
            task_description = result["task"]
            if "action_history" in result:
                action_history = result["action_history"]
            if "thoughts" in result:
                thoughts = result["thoughts"]
            if "final_result_response" in result:
                final_result_response = result["final_result_response"]
            if "input_image_paths" in result:
                input_image_paths = result["input_image_paths"]

        logger.info(f"Start evaluation for task: {task_id}")
        print(f"Start evaluation for {task_description}")
        # Do the auto-eval
        if args.mode == "Autonomous_eval":
            for image in sorted(
                os.listdir(trajectory_images_path),
                key=get_step_number,
            ):
                screenshot_paths.append(os.path.join(trajectory_images_path, image))
            messages, text, system_msg = Autonomous_eval(
                task_description, action_history, screenshot_paths[-1]
            )

        elif args.mode == "AgentTrek_eval":
            for image in sorted(
                os.listdir(trajectory_images_path),
                key=get_step_number,
            ):
                screenshot_paths.append(os.path.join(trajectory_images_path, image))
            messages, text, system_msg = AgentTrek_eval(
                task_description, action_history, thoughts, screenshot_paths[-1]
            )

        elif args.mode == "WebVoyager_eval":
            for image in sorted(
                os.listdir(trajectory_images_path),
                key=get_step_number,
            ):
                screenshot_paths.append(os.path.join(trajectory_images_path, image))
            messages, text, system_msg = WebVoyager_eval(
                task_description, screenshot_paths, final_result_response
            )

        elif args.mode == "WebJudge_Online_Mind2Web_eval":
            print("trajectory_images_path")
            print(trajectory_images_path)

            for image in sorted(
                os.listdir(trajectory_images_path),
                key=get_step_number,
            ):
                screenshot_paths.append(os.path.join(trajectory_images_path, image))
            messages, text, system_msg, record, key_points = asyncio.run(
                WebJudge_Online_Mind2Web_eval(
                    task_description,
                    action_history,
                    screenshot_paths,
                    model,
                    args.score_threshold,
                )
            )
            output_results["image_judge_record"] = record
            output_results["key_points"] = key_points

        elif args.mode == "WebJudge_general_eval":
            for image in sorted(
                os.listdir(trajectory_images_path),
                key=get_step_number,
            ):
                screenshot_paths.append(os.path.join(trajectory_images_path, image))
            messages, text, system_msg, record, key_points = asyncio.run(
                WebJudge_general_eval(
                    task_description,
                    input_image_paths,
                    thoughts,
                    action_history,
                    screenshot_paths,
                    model,
                    args.score_threshold,
                )
            )
            output_results["image_judge_record"] = record
            output_results["key_points"] = key_points

        else:
            raise ValueError(f"Unknown mode: {args.mode}")

        try:
            response = model.generate(messages)[0]
            predicted_label = extract_predication(response, args.mode)
        except Exception as e:
            logger.error(
                f"EVALUATION FAILED for task {task_id}: {e}. "
                "This task will not have LLM evaluation results."
            )
            print(f"ERROR: Evaluation failed for {task_description}: {e}")
            continue

        # Store evaluation details
        evaluation_results = {"response": response, "predicted_label": predicted_label}
        output_results["task_id"] = task_id
        output_results["input_text"] = text
        output_results["system_msg"] = system_msg
        output_results["evaluation_details"] = evaluation_results
        output_results["predicted_label"] = predicted_label

        with lock:
            final_predicted_labels.append(predicted_label)

        logger.info(
            f"Finish evaluation for task {task_id}: predicted_label={predicted_label}"
        )
        print(f"Finish evaluation for {task_description}")
        print("=" * 20)
        os.makedirs(args.output_path, exist_ok=True)
        with lock:
            with open(
                os.path.join(
                    args.output_path,
                    f"{args.mode}_{args.model}_score_threshold_{args.score_threshold}_auto_eval_results.json",
                ),
                "a+",
            ) as f_out:
                f_out.write(json.dumps(output_results) + "\n")


def process_subset(task_subset, args, final_predicted_labels, lock, model):
    auto_eval(args, task_subset, final_predicted_labels, lock, model)


def parallel_eval(args, num_workers=1):
    """
    Evaluate tasks in parallel with rate limit protection.

    Args:
        args: Evaluation arguments (mode, model, paths, etc.)
        num_workers: Number of parallel worker processes (default: 5)
                    Lower values reduce API rate limit pressure.

    Returns:
        Pass rate as a percentage (0-100)
    """
    # Evaluate in parallel based on num of works
    task_dirs = [
        d
        for d in sorted(os.listdir(args.trajectories_dir))
        if os.path.isdir(os.path.join(args.trajectories_dir, d))
    ]

    logger.info(f"Starting evaluation: {len(task_dirs)} tasks, {num_workers} workers")
    logger.info(
        f"Rate limit protection: {INTER_TASK_DELAY}s delay between tasks, "
        "exponential backoff on 429 errors"
    )
    print(f"Evaluating {len(task_dirs)} tasks in total.")
    chunk_size = len(task_dirs) // num_workers
    print(f"Chunk size {chunk_size}.")

    if chunk_size == 0:
        chunk_size = 1

    task_subsets = [
        task_dirs[i : i + chunk_size] for i in range(0, len(task_dirs), chunk_size)
    ]

    # Load model
    model = OpenaiEngine(model=args.model, api_key=args.api_key)

    lock = multiprocessing.Lock()
    with multiprocessing.Manager() as manager:
        final_predicted_labels = manager.list()
        processes = []
        for subset in task_subsets:
            p = multiprocessing.Process(
                target=process_subset,
                args=(subset, args, final_predicted_labels, lock, model),
            )
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

        success_num = sum(final_predicted_labels)
        evaluated_count = len(final_predicted_labels)

    print("Evaluation complete.")
    logger.info(
        f"Evaluation complete: {evaluated_count}/{len(task_dirs)} tasks evaluated, "
        f"{success_num} passed"
    )

    if evaluated_count < len(task_dirs):
        logger.warning(
            f"INCOMPLETE EVALUATION: Only {evaluated_count}/{len(task_dirs)} tasks "
            "were evaluated. Some tasks may have failed due to rate limits or errors. "
            "Check logs for details."
        )

    pass_rate = (success_num / len(task_dirs)) * 100 if task_dirs else 0
    return pass_rate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto evaluation of web navigation tasks."
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="WebJudge_Online_Mind2Web_eval",
        help="the mode of evaluation",
    )
    parser.add_argument("--model", type=str, default="gpt-4o")
    parser.add_argument(
        "--trajectories_dir",
        type=str,
        required=True,
        help="Path to trajectories directory",
    )
    parser.add_argument("--api_key", type=str, required=False, help="The api key")
    parser.add_argument(
        "--output_path",
        type=str,
        required=True,
        help="The output path",
    )
    parser.add_argument("--score_threshold", type=int, default=3)
    parser.add_argument("--num_worker", type=int, default=60)
    args = parser.parse_args()

    print(args)
    parallel_eval(args, args.num_worker)
