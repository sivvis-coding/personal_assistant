"""Time entry parameter extractor migrated from the legacy assistant agent."""

import re
from datetime import date, datetime, time, timedelta


class TimeAgentParameterExtractor:
    """Extract time entry parameters from natural language user messages.

    Parameters:
        today: Date used as the reference for relative date words such as "hoy".

    Returns:
        Extractor capable of parsing Spanish time-tracking requests.

    Edge cases:
        Relative dates and missing time components are intentionally left incomplete
        so the agent can ask the user for clarification rather than guessing.
    """

    def __init__(self, today: date | None = None) -> None:
        self._today = today or date.today()

    def extract(self, message: str) -> "TimeEntryParameters":
        """Extract time entry parameters from a user message.

        Parameters:
            message: Natural language request in Spanish.

        Returns:
            Extracted parameters, possibly incomplete if information is missing.
        """
        original = message.strip()
        normalized = self._normalize(original)
        duration_minutes, duration_span = self._extract_duration_minutes(normalized)
        text_without_duration = self._remove_span(normalized, duration_span)

        return TimeEntryParameters(
            task_name=self._extract_task_name(original),
            client_name=self._extract_client(original),
            description=self._extract_description(original),
            duration_minutes=duration_minutes,
            start_date=self._extract_start_date(normalized),
            start_time=self._extract_start_time(text_without_duration),
        )

    def _normalize(self, message: str) -> str:
        """Normalize the message for safer pattern matching."""
        return " ".join(message.lower().strip().split())

    def _extract_duration_minutes(self, message: str) -> tuple[int, tuple[int, int] | None]:
        """Extract duration in minutes and its span from common Spanish time patterns."""
        combined_match = re.search(r"(\d+(?:[.,]\d+)?)\s*h\s*(?:(\d+)\s*m?)?\b", message)
        if combined_match:
            hours = float(combined_match.group(1).replace(",", "."))
            minutes = int(combined_match.group(2)) if combined_match.group(2) else 0
            return int(hours * 60) + minutes, combined_match.span()

        minute_match = re.search(r"(\d+)\s*(?:min|minutos?)\b", message)
        if minute_match:
            return int(minute_match.group(1)), minute_match.span()

        hour_word_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:hora|horas)\b", message)
        if hour_word_match:
            return int(float(hour_word_match.group(1).replace(",", ".")) * 60), hour_word_match.span()

        return 0, None

    def _remove_span(self, message: str, span: tuple[int, int] | None) -> str:
        """Return the message with the matched span removed."""
        if span is None:
            return message
        start, end = span
        return message[:start] + " DURACION " + message[end:]

    def _extract_client(self, message: str) -> str:
        """Extract the client name from common Spanish patterns."""
        normalized = self._normalize(message)
        patterns = [
            r"cliente\s+([^,\.]+?)(?:\s+(?:por|para|sobre|hoy|ayer|mañana|\d))",
            r"al cliente\s+([^,\.]+?)(?:\s+(?:por|para|sobre|hoy|ayer|mañana|\d))",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                start, end = match.span(1)
                return message[start:end].strip()
        return ""

    def _extract_start_date(self, message: str) -> date | None:
        """Extract a start date from the message."""
        if "hoy" in message:
            return self._today
        if "ayer" in message:
            return self._today - timedelta(days=1)
        if "mañana" in message:
            return self._today + timedelta(days=1)

        iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", message)
        if iso_match:
            try:
                return datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                return None

        return None

    def _extract_start_time(self, message: str) -> time | None:
        """Extract a start time from the message."""
        time_match = re.search(r"(\d{1,2}):(\d{2})\b", message)
        if time_match:
            try:
                return time(int(time_match.group(1)), int(time_match.group(2)))
            except ValueError:
                return None

        hour_shorthand = re.search(r"\b(\d{1,2})h(?:00)?\b", message)
        if hour_shorthand:
            try:
                return time(int(hour_shorthand.group(1)), 0)
            except ValueError:
                return None

        return None

    def _extract_description(self, message: str) -> str:
        """Extract a human-readable work description from the message."""
        work_match = re.search(r"(?:por|sobre|para)\s+(.+)$", message)
        if work_match:
            return self._clean_description(work_match.group(1))
        return self._clean_description(message)

    def _extract_task_name(self, message: str) -> str:
        """Build a short ClickUp task name from the message."""
        description = self._extract_description(message)
        words = description.split()
        if not words:
            return "Trabajo sin descripción"
        short_name = " ".join(words[:6])
        if len(short_name) > 80:
            short_name = short_name[:77] + "..."
        return short_name.capitalize()

    def _clean_description(self, text: str) -> str:
        """Remove command boilerplate from a description candidate."""
        command_words = (
            r"^\s*(?:imputa|imputar|registra|registrar|apunta|anota|guarda|guardar|guardes)\s+(?:por\s+)?"
        )
        cleaned = re.sub(command_words, "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+(?:hoy|ayer|mañana)\b", "", cleaned)
        cleaned = re.sub(r"\bcliente\s+[^,\.]+?\s+(?:por|para|sobre)\s+", "", cleaned)
        cleaned = re.sub(r"\b(?:\d+h(?:\d+m)?|\d+\s*(?:min|minutos?|hora|horas))\b", "", cleaned)
        cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", cleaned)
        cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", "", cleaned)
        cleaned = re.sub(r"\b\d{1,2}h(?:00)?\b", "", cleaned)
        cleaned = " ".join(cleaned.split())
        return cleaned.strip(" ,.")


class TimeEntryParameters:
    """Simple mutable parameter bag for extraction results."""

    def __init__(
        self,
        task_name: str = "",
        client_name: str = "",
        description: str = "",
        duration_minutes: int = 0,
        start_date: date | None = None,
        start_time: time | None = None,
    ) -> None:
        self.task_name = task_name
        self.client_name = client_name
        self.description = description
        self.duration_minutes = duration_minutes
        self.start_date = start_date
        self.start_time = start_time

    def is_complete(self) -> bool:
        """Return whether all required parameters are present."""
        return bool(
            self.task_name
            and self.description
            and self.duration_minutes > 0
            and self.start_date is not None
            and self.start_time is not None
        )

    def missing_fields(self) -> list[str]:
        """Return human-readable labels for missing required parameters."""
        missing: list[str] = []
        if not self.task_name:
            missing.append("nombre de la tarea")
        if not self.description:
            missing.append("descripción del trabajo")
        if self.duration_minutes <= 0:
            missing.append("duración (ej. 2h, 30min)")
        if self.start_date is None or self.start_time is None:
            missing.append("fecha y hora de inicio")
        return missing

    def build_start_datetime(self) -> datetime:
        """Build a local start datetime from date and time components."""
        if self.start_date is None or self.start_time is None:
            raise ValueError("start_date and start_time are required to build a datetime")
        return datetime.combine(self.start_date, self.start_time)

    def build_end_datetime(self) -> datetime:
        """Build a local end datetime by adding the duration to the start."""
        return self.build_start_datetime() + timedelta(minutes=self.duration_minutes)
