from __future__ import annotations

from backend.adapters.llm.base import LLMResponse


class MockLLMAdapter:
    provider_name = "mock"
    model_name = "mock-local-llm"

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResponse:
        if "修正案作成担当" in system_prompt:
            text = self._revision_suggestions_text(user_prompt)
        elif (
            "議事録案作成担当" in system_prompt
            or "## 決定事項" in system_prompt
            or "議事録を作成" in system_prompt
        ):
            text = self._minutes_text(user_prompt)
        else:
            text = self._cleanup_text(user_prompt)
        return LLMResponse(text=text, provider=self.provider_name, model=self.model_name)

    def _cleanup_text(self, user_prompt: str) -> str:
        body = user_prompt.split("文字起こし:", 1)[-1].strip()
        if not body:
            body = "（文字起こし内容が空です）"
        return f"【整形済み文字起こし mock】\n{body}\n\n※ mock出力です。意味の補完は行っていません。"

    def _minutes_text(self, user_prompt: str) -> str:
        meeting_name = self._extract_field(user_prompt, "面談名") or "不明"
        meeting_date = self._extract_field(user_prompt, "実施日") or "不明"
        participants = self._extract_field(user_prompt, "参加者") or "不明"
        return "\n".join(
            [
                f"# 議事録案 mock: {meeting_name}",
                "",
                f"- 面談名: {meeting_name}",
                f"- 実施日: {meeting_date}",
                f"- 参加者: {participants}",
                "- 主な相談内容: mockアダプタによるデモ出力です。整形済みテキストを確認してください。",
                "- 決定事項: 不明",
                "- 今後の対応: 不明",
                "- 注意事項: LLM実体を使わないmock出力のため、内容確認が必要です。",
                "- 自由記述: ローカル処理フロー確認用の議事録案です。",
            ]
        )

    def _revision_suggestions_text(self, user_prompt: str) -> str:
        flagged_lines = [
            line.strip()
            for line in user_prompt.splitlines()
            if any(word in line for word in ("要確認", "不明", "聞き取れない", "確認が必要"))
        ]
        target = flagged_lines[0] if flagged_lines else "要確認箇所"
        return "\n".join(
            [
                f"- 要確認箇所: {target}",
                "- 修正候補: raw transcript の該当箇所と照合し、聞き取れる語だけに置き換えてください。",
                "- 根拠: mockアダプタのため候補は確定しません。元音声またはraw transcriptの確認が必要です。",
                "- 追加で人間が確認すべきこと: 参加者名、決定事項、日時などは推測で確定しないでください。",
            ]
        )

    def _extract_field(self, text: str, label: str) -> str | None:
        prefix = f"{label}:"
        for line in text.splitlines():
            if line.startswith(prefix):
                value = line.removeprefix(prefix).strip()
                return value or None
        return None
