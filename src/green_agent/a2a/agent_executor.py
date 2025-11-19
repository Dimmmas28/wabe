import asyncio
from venv import logger
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils.errors import ServerError
from a2a.types import (
    InvalidParamsError,
    Task,
    Part,
    TextPart,
    TaskState,
    UnsupportedOperationError,
    InternalError,
)
from pydantic import ValidationError
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from green_agent.agent import EvalRequest, GreenAgent
from a2a.server.tasks import TaskUpdater


class GreenExecutor(AgentExecutor):
    def __init__(self, green_agent: GreenAgent):
        self.agent = green_agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        if not context.message:
            raise ValueError("RequestContext must have a message")

        task = context.current_task

        if not task:
            task = new_task(context.message)
            logger.info(f"Enqueue event task {task}")
            await event_queue.enqueue_event(task)

        if not context.context_id or not context.task_id:
            raise ValueError("RequestContext must have context_id and task_id")

        req = self._validate_request(context)

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.submit()
        await updater.start_work()
        logger.info(f"Run in background")
        asyncio.create_task(self._run_agent_background(req, updater))
        # try:
        #     await self.agent.run_eval(req, updater)

        #     await updater.complete()
        # except Exception as e:
        #     print(f"Agent error: {e}")
        #     await updater.failed(
        #         updater.new_agent_message(
        #             [Part(root=TextPart(text=f"Agent error: {e}"))]
        #         )
        #     )
        #     raise ServerError(error=InternalError(message=str(e))) from e

    async def _run_agent_background(self, req, updater: TaskUpdater):
        """Run the actual agent work in background"""
        try:
            # This is the long-running operation
            await self.agent.run_eval(req, updater)

            # Update status when done
            await updater.complete()

        except Exception as e:
            print(f"Agent error: {e}")
            await updater.failed(
                updater.new_agent_message(
                    [Part(root=TextPart(text=f"Agent error: {e}"))]
                )
            )

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())

    def _validate_request(
        self,
        context: RequestContext,
    ) -> EvalRequest:
        request_text = context.get_user_input()
        try:
            req: EvalRequest = EvalRequest.model_validate_json(request_text)

            ok, msg = self.agent.validate_request(req)
            if not ok:
                raise ServerError(error=InvalidParamsError(message=msg))

            return req
        except ValidationError as e:
            raise ServerError(error=InvalidParamsError(message=e.json()))
