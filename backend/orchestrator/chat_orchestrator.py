from __future__ import annotations

from backend.adapters.llm.base import LLMAdapter, LLMChatMessage, LLMResponse
from backend.models.db import ChatMessage, ChatSession
from backend.services.prompt_loader import load_prompt
from backend.tooling.base import ToolInfo
from backend.tooling.registry import ToolRegistry, create_default_tool_registry


class ChatOrchestrator:
    def __init__(self, llm_adapter: LLMAdapter, tool_registry: ToolRegistry | None = None):
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry or create_default_tool_registry()

    def generate_response(
        self,
        *,
        session: ChatSession,
        messages: list[ChatMessage],
        latest_user_content: str,
        attachment_context: str | None = None,
        use_tools: bool = True,
    ) -> tuple[LLMResponse, list[ToolInfo]]:
        suggestions = self.tool_registry.suggest_tools(latest_user_content) if use_tools else []
        llm_messages = self._build_llm_messages(
            session=session,
            messages=messages,
            tool_suggestions=suggestions,
            attachment_context=attachment_context,
        )
        return self.llm_adapter.generate_chat(messages=llm_messages), suggestions

    def _build_llm_messages(
        self,
        *,
        session: ChatSession,
        messages: list[ChatMessage],
        tool_suggestions: list[ToolInfo],
        attachment_context: str | None,
    ) -> list[LLMChatMessage]:
        system_parts = [load_prompt("chat_system_prompt.md")]
        if session.system_prompt:
            system_parts.append(f"セッション追加指示:\n{session.system_prompt}")
        if attachment_context:
            system_parts.append(
                "このチャットに添付された文書コンテキスト:\n"
                f"{attachment_context}\n\n"
                "ユーザーが「この文書」「添付文書」「資料」などと言った場合は、上記の添付文書を対象として扱ってください。"
                "添付文書があるにもかかわらず、文書が添付されていないとは言わないでください。"
            )
        if tool_suggestions:
            tool_lines = "\n".join(
                f"- {tool.name}: {tool.description} status={tool.status}" for tool in tool_suggestions
            )
            system_parts.append(
                "関連しそうな専用ツール候補:\n"
                f"{tool_lines}\n"
                "添付文書コンテキストだけで回答できる場合は、そのまま回答してください。"
                "長大な全文確認や複数文書比較が必要な場合だけ、専用画面への導線を短く案内してください。"
            )

        llm_messages = [LLMChatMessage(role="system", content="\n\n".join(system_parts))]
        for message in messages[-20:]:
            if message.role in {"user", "assistant", "system"}:
                llm_messages.append(LLMChatMessage(role=message.role, content=message.content))
        return llm_messages
