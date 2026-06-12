    def extract_case_person_names(self, text: str) -> list[str]:
        """Extract unique character names from case text using focused LLM call."""
        messages = [
            {"role": "system", "content": NAME_EXTRACTION_PROMPT},
            {"role": "user", "content": str(text or "")[:8000]},
        ]
        try:
            from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
            response = create_json_chat_completion(messages=messages, model=get_chat_model(), temperature=0.1, max_tokens=1000)
            payload = self._safe_json_loads(extract_message_text(response), [])
            if isinstance(payload, list):
                valid_names = []
                seen = set()
                for name in payload:
                    clean = self._normalize_person_name(str(name or "").strip())
                    if clean and self._is_valid_person_name(clean) and clean not in seen:
                        seen.add(clean)
                        valid_names.append(clean)
                return valid_names
        except Exception:
            pass
        return []