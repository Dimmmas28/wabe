from a2a.types import AgentSkill, AgentCard, AgentCapabilities


def prepare_agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="execute_task",
        name="WEB tasks executor",
        description="Follow language instructions to complete complex tasks on any website.",
        tags=["web"],
        examples=[],
    )

    public_agent_card = AgentCard(
        name="web_agent",
        description="Follow language instructions to complete complex tasks on any website",
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    return public_agent_card
