"""
Multi-Agent Orchestrator

Coordinates multiple agents to work simultaneously and combine their results.
Currently supports:
- Database Agent: For querying Supabase
- Web Search Agent: For searching the web

Example:
    from multi_agent_orchestrator import run_multi_agent_task

    results = run_multi_agent_task({
        "database_query": {
            "table": "interventions",
            "limit": 5
        },
        "web_search": {
            "query": "AI content monitoring",
            "limit": 3
        }
    })
"""
  
import asyncio
import concurrent.futures
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable

# Import the agents
from database_agent import execute_query
from web_search_agent import search_web, fetch_webpage_content


class MultiAgentOrchestrator:
    """Orchestrates multiple agents to work simultaneously."""
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.results = {}
        self.errors = {}
    
    async def _run_async(self, func: Callable, args: Dict[str, Any], agent_name: str) -> None:
        """Run a function asynchronously and store its result."""
        try:
            # Use a thread pool for CPU-bound or blocking I/O operations
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await asyncio.get_event_loop().run_in_executor(
                    pool, lambda: func(args)
                )
            self.results[agent_name] = result
        except Exception as e:
            self.errors[agent_name] = str(e)
    
    async def run_tasks(self, tasks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Run multiple agent tasks concurrently.
        
        Args:
            tasks: A dictionary mapping agent names to their parameters
            
        Returns:
            A dictionary with the results and any errors
        """
        coroutines = []
        
        # Database agent task
        if "database_query" in tasks:
            coroutines.append(
                self._run_async(execute_query, tasks["database_query"], "database_agent")
            )
        
        # Web search agent task
        if "web_search" in tasks:
            coroutines.append(
                self._run_async(search_web, tasks["web_search"], "web_search_agent")
            )
            
        # Web content fetch task
        if "web_fetch" in tasks:
            coroutines.append(
                self._run_async(fetch_webpage_content, tasks["web_fetch"], "web_fetch_agent")
            )
        
        # Run all tasks concurrently
        await asyncio.gather(*coroutines)
        
        return {
            "results": self.results,
            "errors": self.errors,
            "timestamp": time.time()
        }


def run_multi_agent_task(tasks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Run multiple agent tasks concurrently.
    
    This is a synchronous wrapper around the async orchestrator.
    
    Args:
        tasks: A dictionary mapping agent names to their parameters
        
    Returns:
        A dictionary with the results and any errors
    """
    orchestrator = MultiAgentOrchestrator()
    
    # Create and run the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(orchestrator.run_tasks(tasks))
    finally:
        loop.close()


# Example usage
if __name__ == "__main__":
    # Example task that uses both agents
    tasks = {
        "database_query": {
            "table": "interventions",
            "limit": 5
        },
        "web_search": {
            "query": "AI content monitoring",
            "limit": 3
        }
    }
    
    results = run_multi_agent_task(tasks)
    print("Results:", results)
