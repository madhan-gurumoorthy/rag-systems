"""
agent.py
--------
Builds a unified LangChain v0.3 AgentExecutor with two tools:

  1. pandas_analysis_tool
     – Wraps a PandasDataFrameAgent over the current month's processed
       incident DataFrame.  Handles questions like "which category has
       the most incidents?" or "list all Authentication Failure incidents".

  2. historical_comparison_tool
     – Performs a similarity search on the Milvus vector store of past
       monthly summaries.  Handles questions like "how does this month
       compare to last month?" by retrieving the most semantically
       relevant stored reports and returning them as context.

Architecture
------------
    User question
          │
          ▼
    AgentExecutor  (OpenAI functions / tool-calling agent)
          │
    ┌─────┴─────┐
    │           │
    pandas   milvus
    tool     tool
    │           │
    ▼           ▼
  current    past monthly
  DataFrame  reports (vector store)

This design means the LLM decides which tool(s) to call per turn — it can
call both in the same turn for a comparison question.

Usage
-----
    from agent import build_agent
    agent_executor = build_agent(monthly_df, categorized_df)
    response = agent_executor.invoke({"input": "How does this month compare to last?"})
    print(response["output"])
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

from milvus_store import get_vector_store, format_retrieved_docs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM factory (swap model / provider here if needed)
# ---------------------------------------------------------------------------

def _build_llm(model: str = "gpt-4o-mini", temperature: float = 0) -> ChatOpenAI:
    """
    Build the ChatOpenAI LLM.

    Requires OPENAI_API_KEY in the environment.
    Change `model` to "gpt-4o" for higher quality at higher cost.
    """
    return ChatOpenAI(model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# Tool 1 – Pandas analysis (current month's data)
# ---------------------------------------------------------------------------

def _build_pandas_tool(
    categorized_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    llm: ChatOpenAI,
) -> Tool:
    """
    Wrap a PandasDataFrameAgent over two DataFrames as a single Tool.

    The inner agent receives BOTH DataFrames so it can answer questions
    about raw incidents and aggregated monthly counts.

    NOTE: `allow_dangerous_code=True` is required by LangChain v0.3 for any
    agent that executes arbitrary Python.  Only use this with trusted input.
    """
    inner_agent = create_pandas_dataframe_agent(
        llm=llm,
        df=[categorized_df, monthly_df],          # pass both frames
        verbose=True,
        allow_dangerous_code=True,
        agent_executor_kwargs={"handle_parsing_errors": True},
    )

    def _run_pandas_agent(query: str) -> str:
        """Execute the pandas agent with the given query."""
        try:
            result = inner_agent.invoke({"input": query})
            return str(result.get("output", result))
        except Exception as exc:
            logger.exception("Pandas agent error: %s", exc)
            return f"Pandas agent encountered an error: {exc}"

    return Tool(
        name="pandas_analysis_tool",
        func=_run_pandas_agent,
        description=(
            "Use this tool to analyse the current incident data. "
            "It has access to two pandas DataFrames: "
            "(1) categorized_df — one row per incident, with columns: "
            "sys_created_on, short_description, description, state, category, month. "
            "(2) monthly_df — pivot table with monthly incident counts per category. "
            "Use for questions about counts, trends, top categories, or filtering specific incidents."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 2 – Milvus historical similarity search
# ---------------------------------------------------------------------------

def _build_milvus_tool(k: int = 3) -> Tool:
    """
    Build a Tool that queries the Milvus vector store for historical reports.

    Returns a formatted string of the top-k most similar past monthly summaries.
    """
    vector_store = get_vector_store()

    def _search_history(query: str) -> str:
        """Search Milvus for past monthly summaries similar to the query."""
        try:
            docs = vector_store.similarity_search(query, k=k)
            return format_retrieved_docs(docs)
        except Exception as exc:
            logger.exception("Milvus search error: %s", exc)
            return f"Could not retrieve historical data: {exc}"

    return Tool(
        name="historical_comparison_tool",
        func=_search_history,
        description=(
            "Use this tool to retrieve historical monthly incident summary reports "
            "from the vector store.  Call it when the user asks about trends over time, "
            "comparisons to previous months, or historical context (e.g. 'how does this "
            "month compare to last month?', 'what was the trend in Q1?'). "
            "Input should be a natural-language description of what you are looking for, "
            "e.g. 'incident summary for February 2025'."
        ),
    )


# ---------------------------------------------------------------------------
# Agent prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert incident analytics assistant for an operations team.

You have access to two tools:
1. **pandas_analysis_tool** – query the current incident data (row-level and monthly aggregates).
2. **historical_comparison_tool** – retrieve past monthly incident summaries from the vector store.

When the user asks about trends or comparisons across months:
  - First call `historical_comparison_tool` to fetch relevant past reports.
  - Then call `pandas_analysis_tool` to get current figures.
  - Synthesise both results into a clear, concise comparison.

Always cite specific numbers and month labels in your answers.
If data is insufficient for a comparison, say so clearly.
"""


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_agent(
    categorized_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    model: str = "gpt-4o-mini",
    milvus_k: int = 3,
    verbose: bool = True,
) -> AgentExecutor:
    """
    Build and return the unified AgentExecutor.

    Parameters
    ----------
    categorized_df : pd.DataFrame
        Row-level incident data (output of ``categorize_incidents()``).
    monthly_df : pd.DataFrame
        Monthly pivot table (output of ``aggregate_by_month()``).
    model : str
        OpenAI chat model name.  Defaults to "gpt-4o-mini".
    milvus_k : int
        Number of historical documents to retrieve per similarity search.
    verbose : bool
        Whether to print agent reasoning steps.

    Returns
    -------
    AgentExecutor
        Call ``.invoke({"input": "<question>"})`` to query the agent.
    """
    llm = _build_llm(model=model)
    tools = [
        _build_pandas_tool(categorized_df, monthly_df, llm),
        _build_milvus_tool(k=milvus_k),
    ]
    prompt = _build_prompt()

    # create_tool_calling_agent uses the model's native function-calling API
    # (OpenAI tool-use), which is more reliable than ReAct string parsing.
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        handle_parsing_errors=True,
        max_iterations=8,       # prevent infinite loops
        return_intermediate_steps=False,
    )

    logger.info("AgentExecutor built with tools: %s", [t.name for t in tools])
    return executor


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def ask(
    agent_executor: AgentExecutor,
    question: str,
    chat_history: list[Any] | None = None,
) -> str:
    """
    Ask the agent a question and return the string answer.

    Parameters
    ----------
    agent_executor : AgentExecutor
    question : str
    chat_history : list | None
        Optional prior conversation turns for multi-turn dialogue.

    Returns
    -------
    str
        The agent's final answer.
    """
    inputs: dict[str, Any] = {"input": question}
    if chat_history:
        inputs["chat_history"] = chat_history

    logger.info("Agent query: %r", question)
    result = agent_executor.invoke(inputs)
    answer = str(result.get("output", result))
    logger.info("Agent answer: %r", answer[:200])
    return answer
