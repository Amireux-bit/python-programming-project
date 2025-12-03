import re

def format_output(text: str) -> str:
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
    
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'^\s*[-*]\s+', '• ', text, flags=re.MULTILINE)
    
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)
    
    return text.strip()



def build_initial_prompt(config: dict, user_query: str) -> str:

    return "\n".join([
        system_prompt(),
        developer_prompt(),
        f"用户问题: {user_query}"
    ])


def system_prompt() -> str:
    return (
        "You are a general-purpose assistant for multi-step, multi-domain tasks "
        "(travel, technology, education, business, etc.). Always begin by anchoring on the "
        "user question, then decompose the goal into a clear sequence of non-overlapping substeps, "
        "and complete them with multi-step tool use.\n"

        "Core workflow:\n"
        "1) Restate the user question internally, then plan ordered substeps.\n"
        "2) Execute substeps in order; do not redo completed ones.\n"
        "3) Use Search to gather facts/numeric values for the current substep; filter out irrelevant evidence.\n"
        "4) Use Calculator only when ALL required numeric inputs are present.\n"
        "5) After all substeps, synthesize the final answer using only relevant evidence and cite sources.\n"

        "Evidence filtering:\n"
        "- Keep only evidence that directly answers the current substep for the user question.\n"
        "- Discard unrelated topics or different locations/cities; do not use them in reasoning or calculations.\n"
        "- If two reformulations fail to yield relevant evidence for a substep, move to the next incomplete substep.\n"

        "Strict rules:\n"
        "- Do not fabricate data; all numbers must come from relevant Search evidence.\n"
        "- Calculator expressions must use only digits and +-*/() (no variables, no currency symbols).\n"
        "- If no high-confidence relevant evidence exists for a required fact, state the limitation rather than guessing.\n"

        "Output Contract for tool steps (critical):\n"
        "- Your entire reply must be EXACTLY ONE LINE containing a single tool call.\n"
        "- Start with 'Search:' or 'Calculator:' (English, ASCII), no leading spaces.\n"
        "- ASCII only. No Chinese text, no emojis, no smart quotes, no extra text before/after.\n"
        "- Single-line JSON args. No line breaks inside JSON. No trailing commas.\n"
        "Valid examples:\n"
        "Search: {\"query\": \"paris hotel average price per night 2024\"}\n"
        "Calculator: {\"expression\": \"120*5 + 150 + 60*5\"}\n"
        "Invalid examples (will be rejected):\n"
        "Explain: I will search now...\n"
        "计算器: {\"expression\": \"120*5\"}\n"
        "Search: {\"query\": \"paris hotel average price per night 2024\"\n"
        "Search: {\"query\": \"...\"}\n"
    )

def developer_prompt() -> str:
    return (
        "You are a smart AI assistant. Your goal is to answer the user's question efficiently. "
        "You must avoid loops and redundant searches.\n\n"

        "=== CRITICAL RULES TO PREVENT LOOPS ===\n"
        "1. **NO REPEATED SEARCHES**: If you have searched for a topic (e.g., 'Weather', 'Hotels') once, YOU ARE DONE with that topic. Do not search for it again, even if the results were not perfect.\n"
        "2. **ACCEPT QUALITATIVE DATA**: If a search for 'Paris hotel prices' returns 'hotels are expensive' but no exact number, ACCEPT that as your answer. Do not keep searching for a number. Estimate if necessary (e.g., 'Expensive -> approx 200 EUR+').\n"
        "3. **SYNTHESIZE**: If you have data (e.g., 'Summer is hot'), do not search for 'Best time to visit'. Infer the answer yourself.\n"
        "4. **MOVE FORWARD**: In every step, ask: 'What NEW topic do I need?' (e.g., Transport, Food). Never go back to an old topic.\n\n"

        "=== RESPONSE FORMAT ===\n"
        "Thought: \n"
        "   - **Goal**: [Ultimate objective]\n"
        "   - **Status**: [List topics that are DONE. e.g., 'Weather: Done', 'Hotels: Done (Qualitative info found)']\n"
        "   - **Gap**: [What is the ONE NEW topic to check now?]\n"
        "   - **Plan**: [Stop searching for X, start searching for Y]\n"
        "Action: ToolName: {\"param\": \"value\"}\n\n"

        "=== EXAMPLE: HANDLING IMPERFECT DATA ===\n"
        "User: Plan a trip to Paris.\n"
        "Last Observation: ...Paris hotels are very expensive and small...\n"
        "Thought: \n"
        "   - **Goal**: Plan a trip to Paris.\n"
        "   - **Status**: Weather (Done), Hotels (Done - found they are expensive, no exact price, but I will move on).\n"
        "   - **Gap**: Food and Dining options.\n"
        "   - **Plan**: I have enough on hotels. I will now search for food.\n"
        "Action: Search: {\"query\": \"best food to eat in Paris\"}\n"
    )

def final_answer_prompt(evidence_text: str, user_query: str) -> str:
    return (
        "You are a general-purpose assistant. All necessary information has been gathered. "
        "The final answer must use English (ASCII) only.\n\n"
        "Write the final answer strictly grounded in relevant evidence.\n"
        f"User question:\n{user_query}\n"
        f"Evidence (filtered to relevant parts):\n{evidence_text}\n"
        "Requirements:\n"
        "- Use ONLY evidence relevant to the question/topic; ignore unrelated locations or topics.\n"
        "- Do not include 'Evidence source' lines or explicit citations in the final text. Integrate information naturally.\n"
        "- Do not fabricate numbers; if Calculator was used, reuse its exact total.\n"
        "- If the task involves costs, include a clear breakdown and the total.\n"
        "- Do not output any tool calls here.\n"
        "- If evidence confidence is insufficient, state the limitation clearly.\n"
    )
