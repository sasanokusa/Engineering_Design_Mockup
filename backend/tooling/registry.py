from __future__ import annotations

from backend.tooling.base import ChatTool, ToolInfo


class KeywordTool:
    def __init__(self, info: ToolInfo, keywords: tuple[str, ...]):
        self.info = info
        self.keywords = keywords

    def matches(self, user_message: str) -> bool:
        lowered = user_message.lower()
        return any(keyword.lower() in lowered for keyword in self.keywords)


def create_default_tool_registry() -> "ToolRegistry":
    return ToolRegistry(
        tools=[
            KeywordTool(
                ToolInfo(
                    name="document_search_tool",
                    display_name="資料検索",
                    description="永続資料群から関連箇所を検索するAPIへ接続済みのツール候補です。",
                    status="api-ready",
                ),
                keywords=("資料", "校則", "規程", "検索", "handbook", "document"),
            ),
            KeywordTool(
                ToolInfo(
                    name="document_read_tool",
                    display_name="文書読解",
                    description="登録済み文書の正規化Markdownとchunkを読むためのツール候補です。",
                    status="api-ready",
                ),
                keywords=("論文", "レポート", "添削", "要約", "読解", "pdf", "docx"),
            ),
            KeywordTool(
                ToolInfo(
                    name="document_compare_tool",
                    display_name="文書比較",
                    description="複数文書の差分、類似チャンク、版差サマリを比較ジョブAPIで確認できます。",
                    status="api-ready",
                ),
                keywords=("比較", "差分", "類似", "流用", "コピペ"),
            ),
            KeywordTool(
                ToolInfo(
                    name="minutes_tool",
                    display_name="議事録作成",
                    description="音声起点のASR、整形、議事録生成ワークフローへ接続する専用ツールです。",
                    status="dedicated-ui",
                ),
                keywords=("議事録", "面談", "録音", "文字起こし", "相談記録"),
            ),
        ]
    )


class ToolRegistry:
    def __init__(self, tools: list[ChatTool]):
        self.tools = tools

    def list_tools(self) -> list[ToolInfo]:
        return [tool.info for tool in self.tools]

    def suggest_tools(self, user_message: str) -> list[ToolInfo]:
        return [tool.info for tool in self.tools if tool.matches(user_message)]
