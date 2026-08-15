"""
ODrive Firmware Enum & Bitfield Validator
Cross-checks enum names and integer/hex values referenced in markdown documentation
against ground-truth data extracted from the official ODriveArduino library
(rules/odrive_enum_reference.json), so docs can't silently drift from the real API.
"""

import difflib
import json
import os
import re
from typing import Any, Dict, List

_ENUM_TOKEN_PATTERN = re.compile(
    r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`\s*\|\s*`(0x[0-9A-Fa-f]+|\d+)`"
)

_KNOWN_PREFIXES = (
    "GPIO_MODE_", "STREAM_PROTOCOL_TYPE_", "PROTOCOL_", "AXIS_STATE_",
    "CONTROL_MODE_", "COMPONENT_STATUS_", "ODRIVE_ERROR_", "ERROR_",
    "PROCEDURE_RESULT_", "ENCODER_ID_", "SPI_ENCODER_MODE_",
    "INCREMENTAL_ENCODER_FILTER_", "RS485_ENCODER_MODE_", "INPUT_MODE_",
    "MOTOR_TYPE_", "THERMISTOR_MODE_", "CAN_ERROR_",
)


class EnumValidator:
    def __init__(self, reference_path: str = "rules/odrive_enum_reference.json"):
        self.reference_path = reference_path
        self.reference: Dict[str, int] = {}
        if os.path.exists(reference_path):
            with open(reference_path, "r", encoding="utf-8") as f:
                self.reference = json.load(f).get("enums", {})

    def _resolve(self, token: str) -> Any:
        """Looks up a token directly, falling back to legacy ERROR_ -> ODRIVE_ERROR_ aliasing."""
        if token in self.reference:
            return token
        if token.startswith("ERROR_"):
            aliased = "ODRIVE_" + token
            if aliased in self.reference:
                return aliased
        return None

    def _suggest(self, token: str) -> str:
        matches = difflib.get_close_matches(token, self.reference.keys(), n=1, cutoff=0.5)
        return matches[0] if matches else ""

    def validate(self, filepath: str, markdown: str, line_offset: int = 0) -> List[Dict[str, Any]]:
        issues = []
        if not self.reference:
            return issues

        lines = markdown.split("\n")
        for idx, line in enumerate(lines, start=1 + line_offset):
            if line.strip().startswith("```"):
                continue

            for match in _ENUM_TOKEN_PATTERN.finditer(line):
                token, raw_value = match.group(1), match.group(2)
                if not token.startswith(_KNOWN_PREFIXES):
                    continue

                canonical = self._resolve(token)
                if canonical is None:
                    suggestion = self._suggest(token)
                    hint = f" Did you mean '{suggestion}'?" if suggestion else " No equivalent exists in the current library."
                    issues.append({
                        "file": filepath,
                        "line": idx,
                        "rule": "unknown_odrive_enum",
                        "severity": "error",
                        "message": f"'{token}' is not a real ODrive enum member (checked against ODriveArduino library reference).{hint}"
                    })
                    continue

                declared_value = int(raw_value, 16) if raw_value.lower().startswith("0x") else int(raw_value)
                actual_value = self.reference[canonical]
                if declared_value != actual_value:
                    issues.append({
                        "file": filepath,
                        "line": idx,
                        "rule": "odrive_enum_value_mismatch",
                        "severity": "error",
                        "message": f"'{token}' is documented as {raw_value} but the ODriveArduino library defines {canonical} = {actual_value} ({hex(actual_value)})."
                    })

        return issues
