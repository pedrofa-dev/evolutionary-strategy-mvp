from evo_system.domain.agent import Agent


class Selector:
    """
    Selects the best agents according to fitness score.
    """

    def select_top_agents(
        self,
        evaluated_agents: list[tuple[Agent, float]],
        survivors_count: int,
    ) -> list[Agent]:
        if survivors_count <= 0:
            raise ValueError("survivors_count must be greater than 0")

        if survivors_count > len(evaluated_agents):
            raise ValueError("survivors_count cannot be greater than the number of evaluated agents")

        sorted_agents = sorted(
            evaluated_agents,
            key=lambda item: item[1],
            reverse=True,
        )

        return [agent for agent, _ in sorted_agents[:survivors_count]]