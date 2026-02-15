# ============================================================================
# COMPOSIO MCP ORCHESTRATION LAYER - GOOGLE COLAB OPTIMIZED
# ============================================================================
# Architectural Components:
# - MCP Session Management with Tool Router
# - Asynchronous Multi-Platform Operations
# - Granular Permission Control
# - Comprehensive Error Handling & Logging
# ============================================================================

# Cell 1: Environment Configuration & Dependency Installation
# ============================================================================
# Cell 2: Core Orchestration Logic
# ============================================================================
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import nest_asyncio
from composio import Composio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
# !pip install -q composio-claude-agent-sdk claude-agent-sdk composio

from dotenv import load_dotenv

# Enable nested event loops for Colab compatibility
# nest_asyncio.apply()

# Load environment variables from .env file
load_dotenv()

class ComposioMCPOrchestrator:
    """
    Orchestrates multi-platform operations via Composio's MCP abstraction.
    
    Capabilities:
    - Calendar event scheduling (Google Calendar)
    - Email dispatch (Gmail/Outlook)
    - LinkedIn content publishing
    - Slack message ingestion & analysis
    """
    
    def __init__(self, api_key: str, user_id: str):
        """
        Initialize MCP session with authentication context.
        
        Args:
            api_key: Composio API key for authentication
            user_id: External user identifier for session management
        """
        self.composio = Composio(api_key=api_key)
        self.user_id = user_id
        self.session = None
        self.mcp_config = None
        
    def initialize_session(self) -> Dict:
        """
        Instantiate tool router session and configure MCP endpoint.
        
        Returns:
            Dictionary containing MCP configuration metadata
        """
        self.session = self.composio.create(user_id=self.user_id)
        
        self.mcp_config = {
            "type": self.session.mcp.type,
            "url": self.session.mcp.url,
            "headers": self.session.mcp.headers
        }
        
        print(f"[MCP SESSION] Initialized for user: {self.user_id}")
        print(f"[MCP ENDPOINT] {self.mcp_config['url']}")
        
        return self.mcp_config
    
    async def execute_operation(
        self, 
        prompt: str, 
        system_context: Optional[str] = None,
        max_iterations: int = 10
    ) -> List[str]:
        """
        Execute LLM-driven operation via MCP tool invocation.
        
        Args:
            prompt: Natural language instruction for the agent
            system_context: Optional system-level behavioral constraints
            max_iterations: Maximum agentic reasoning turns
            
        Returns:
            List of textual responses from the agent
        """
        if not self.session:
            raise RuntimeError("MCP session not initialized. Call initialize_session() first.")
        
        options = ClaudeAgentOptions(
            system_prompt=system_context or "You are a sophisticated multi-platform orchestration agent with access to calendar, email, LinkedIn, and Slack integrations.",
            permission_mode="bypassPermissions",  # For testing; use 'interactive' in production
            max_turns=max_iterations,
            mcp_servers={
                "composio": self.mcp_config
            }
        )
        
        responses = []
        print(f"\n[OPERATION INITIATED] {prompt}\n")
        
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"[AGENT RESPONSE] {block.text}\n")
                        responses.append(block.text)
        
        return responses


# Cell 3: Multi-Platform Test Suite
# ============================================================================
async def run_comprehensive_test_suite():
    """
    Executes test operations across all integrated platforms.
    Demonstrates calendar, email, LinkedIn, and Slack capabilities.
    """
    
    # Configuration - Replace with your credentials
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "wjdz4czdigly4l6r4pr9ql")
    EXTERNAL_USER_ID = os.getenv("USER_ID", "colab-test-user-001")
    
    # Initialize orchestrator
    orchestrator = ComposioMCPOrchestrator(
        api_key=COMPOSIO_API_KEY,
        user_id=EXTERNAL_USER_ID
    )
    
    # Establish MCP session
    orchestrator.initialize_session()
    
    print("=" * 80)
    print("COMPOSIO MCP TEST SUITE - MULTI-PLATFORM OPERATIONS")
    print("=" * 80)
    
    # ========================================================================
    # Test 1: Email Dispatch
    # ========================================================================
    print("\n[TEST 1] EMAIL TRANSMISSION\n" + "-" * 80)
    
    email_prompt = """
    Send an email with the following specifications:
    - Recipient: pqo14@txstate.edu
    - Subject: Composio MCP Integration Test - Production Ready
    - Body: This is an automated test email dispatched via Composio's MCP abstraction layer. 
            The integration successfully orchestrates multi-platform operations through Claude's 
            agentic reasoning framework.
            
            Timestamp: {timestamp}
    """.format(timestamp=datetime.now().isoformat())
    
    await orchestrator.execute_operation(email_prompt)
    
    # ========================================================================
    # Test 2: Calendar Event Scheduling
    # ========================================================================
    print("\n[TEST 2] CALENDAR EVENT CREATION\n" + "-" * 80)
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    calendar_prompt = f"""
    Schedule a calendar event with these parameters:
    - Title: MCP Integration Review Session
    - Date: {tomorrow}
    - Time: 10:00 AM - 11:00 AM PST
    - Description: Technical review of Composio MCP orchestration layer. 
                   Discuss multi-platform operation patterns, authentication flows, 
                   and production deployment considerations.
    - Location: Virtual (Zoom)
    """
    
    await orchestrator.execute_operation(calendar_prompt)
    
    # ========================================================================
    # Test 3: Slack Message Retrieval & Analysis
    # ========================================================================
    print("\n[TEST 3] SLACK MESSAGE INGESTION\n" + "-" * 80)
    
    slack_prompt = """
    Retrieve the last 5 messages from the #general Slack channel and provide:
    1. Message timestamps
    2. Sender identities
    3. Semantic analysis of content themes
    4. Identification of any action items or urgent requests
    """
    
    await orchestrator.execute_operation(slack_prompt)
    
    # ========================================================================
    # Test 4: LinkedIn Content Publishing
    # ========================================================================
    print("\n[TEST 4] LINKEDIN POST CREATION\n" + "-" * 80)
    
    linkedin_prompt = """
    Compose and draft a LinkedIn post with the following content:
    
    "Architecting agentic systems with Model Context Protocol (MCP) enables 
    unprecedented interoperability across digital platforms. By abstracting 
    authentication complexity and providing structured tool schemas, MCP 
    facilitates sophisticated multi-platform orchestration patterns.
    
    Key architectural benefits:
    • Unified authentication layer with automatic token rotation
    • LLM-optimized action schemas for reliable tool invocation
    • Centralized audit trails for enterprise compliance
    • Granular permission scoping per user context
    
    #AIEngineering #AgenticSystems #MCP #ComposioAI"
    """
    
    await orchestrator.execute_operation(linkedin_prompt)
    
    # ========================================================================
    # Test 5: Complex Multi-Tool Workflow
    # ========================================================================
    print("\n[TEST 5] ORCHESTRATED MULTI-TOOL WORKFLOW\n" + "-" * 80)
    
    workflow_prompt = """
    Execute this multi-step workflow:
    
    1. Query Slack #aiteam channel for messages containing "NVIDIA" in the last 24 hours
    2. Synthesize findings into a concise summary
    3. Schedule a calendar event titled "Deployment Sync" for tomorrow at 2 PM PST
    4. Send email to pqo14@txstate.edu with:
       - Subject: "Deployment Activity Summary"
       - Body: Include the synthesized Slack summary and calendar event details
    5. Post a LinkedIn update announcing successful MCP integration testing
    
    Execute these operations sequentially with appropriate error handling.
    """
    
    await orchestrator.execute_operation(
        workflow_prompt,
        system_context="You are an expert DevOps orchestration agent. Execute tasks methodically with comprehensive error reporting.",
        max_iterations=15
    )
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED - Review agent responses above")
    print("=" * 80)


# Cell 4: Execution Entry Point
# ============================================================================
if __name__ == "__main__":
    asyncio.run(run_comprehensive_test_suite())


# Cell 5: Advanced Use Case - Intelligent Email Triage Agent
# ============================================================================
async def intelligent_email_triage():
    """
    Demonstrates sophisticated agentic reasoning with multi-platform state.
    
    Agent autonomously:
    - Retrieves unread emails
    - Classifies by urgency & category
    - Schedules follow-up calendar events for high-priority items
    - Posts LinkedIn updates for public-facing communications
    - Sends Slack notifications for internal coordination
    """
    
    COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "wjdz4czdigly4l6r4pr9ql")
    EXTERNAL_USER_ID = os.getenv("USER_ID", "colab-test-user-001")
    
    orchestrator = ComposioMCPOrchestrator(
        api_key=COMPOSIO_API_KEY,
        user_id=EXTERNAL_USER_ID
    )
    orchestrator.initialize_session()
    
    triage_prompt = """
    Execute intelligent email triage workflow:
    
    1. Retrieve all unread emails from the past 48 hours
    2. Classify each email by:
       - Urgency (High/Medium/Low)
       - Category (Business/Technical/Personal/Marketing)
       - Sentiment (Positive/Neutral/Negative)
    3. For emails categorized as High urgency:
       - Schedule a calendar reminder 24 hours from now
       - Send myself a summary via email with subject "HIGH PRIORITY EMAIL ALERT"
    4. Generate LinkedIn post summarizing interesting insights from business-related emails
    5. Post summary to Slack #inbox-digest channel
    
    Provide structured output with:
    - Total emails processed
    - Distribution across urgency levels
    - Key action items scheduled
    - Public communication generated
    """
    
    await orchestrator.execute_operation(
        triage_prompt,
        system_context="You are an executive assistant AI with expertise in information synthesis, priority assessment, and cross-platform coordination.",
        max_iterations=20
    )
    
# Uncomment to execute advanced use case:
# asyncio.run(intelligent_email_triage())
