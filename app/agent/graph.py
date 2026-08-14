from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes.deliver import deliver_node
from app.agent.nodes.research import research_node
from app.agent.nodes.review import review_node, route_after_review
from app.agent.nodes.write import write_node
from app.agent.state import ArticleState


def build_graph_builder() -> StateGraph:
    graph = StateGraph(ArticleState)
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node)
    graph.add_node("deliver", deliver_node)

    graph.add_edge(START, "research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", route_after_review, {"write": "write", "deliver": "deliver"})
    graph.add_edge("deliver", END)
    return graph


async def build_graph(checkpointer: AsyncSqliteSaver):
    return build_graph_builder().compile(checkpointer=checkpointer)
