from a2a.types import AgentSkill, AgentCard, AgentCapabilities


def prepare_agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="host_assess_mind2web_bench",
        name="Mind2Web assessment hosting",
        description="Assess the web tasks execution ability of an agent.",
        tags=["green agent", "assessment hosting", "web"],
        examples=[
            """
            {
                "white_agent_url": "https://pro-debater.example.com:443"
            }        
        """
        ],
    )

    public_agent_card = AgentCard(
        name="web_green_agent",
        description="The assessment hosting agent for Mind2Web-bench.",
        url=url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    return public_agent_card
