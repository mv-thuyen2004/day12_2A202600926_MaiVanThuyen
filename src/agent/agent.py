import re
import time
from typing import List, Dict, Any

class ReActAgent:
    def __init__(self, llm: Any, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.tools_description = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools])

    def get_system_prompt(self) -> str:
        return f"""You are an AI Travel Agent. Use the provided tools to answer.
Available tools: 
{self.tools_description}

FORMAT RULES:
You must strictly follow this format for every step:
Thought: [Reasoning about the user request]
Action: tool_name(key='value')
Observation: [Result of the tool]

EXAMPLE:
Thought: I need to check the weather for DaNang.
Action: check_weather_forecast(city='DaNang')
Observation: Weather is Sunny.
Final Answer: The weather is sunny.
"""

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """Thực thi công cụ dựa trên tên và tham số"""
        for tool in self.tools:
            if tool.get("name") == tool_name:
                func = tool.get("func")
                if callable(func):
                    try:
                        return str(func(args))
                    except Exception as e:
                        return f"Error executing {tool_name}: {str(e)}"
        return "ERROR_NO_DATA: Tool not found."

    def run(self, user_input: str) -> Dict[str, Any]:
        start_time = time.time()
        trace_history = []
        current_context = f"User Request: {user_input}\n"
        
        for step in range(1, self.max_steps + 1):
            result = self.llm.generate(prompt=current_context, system_prompt=self.get_system_prompt())
            llm_output = result.get("content", "").strip()
            
            # Khởi tạo dữ liệu bước
            step_data = {"thought": llm_output, "action": "None", "observation": "None"}
            
            # Tách Action bằng Regex
            action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", llm_output, re.IGNORECASE | re.DOTALL)
            
            if action_match:
                tool_name, tool_args = action_match.group(1).strip(), action_match.group(2).strip()
                step_data["action"] = f"{tool_name}({tool_args})"
                
                # Thực thi tool
                observation = self._execute_tool(tool_name, tool_args)
                step_data["observation"] = observation
                
                # Cập nhật ngữ cảnh cho bước tiếp theo
                current_context += f"\n{llm_output}\nObservation: {observation}"
            else:
                current_context += f"\n{llm_output}"

            trace_history.append(step_data)

            # Kiểm tra Final Answer
            final_match = re.search(r"Final Answer:\s*(.*)", llm_output, re.DOTALL | re.IGNORECASE)
            if final_match:
                return {
                    "final_answer": final_match.group(1).strip(),
                    "trace": trace_history,
                    "metrics": {"steps": step, "latency_ms": int((time.time() - start_time) * 1000)}
                }
        
        return {
            "final_answer": "Agent không tìm được câu trả lời sau số bước tối đa.",
            "trace": trace_history,
            "metrics": {"steps": self.max_steps, "latency_ms": int((time.time() - start_time) * 1000)}
        }