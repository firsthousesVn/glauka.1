from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from glauka.core.probe import ProbeResult


@dataclass
class ScanTask:
    task_type: str
    args: Optional[List[str]] = None


class DecisionEngine:
    """
    Simple rule-based engine to propose follow-up scan tasks from probe intel.
    """

    def evaluate(self, probe_result: ProbeResult) -> List[ScanTask]:
        tasks: List[ScanTask] = []
        status = probe_result.status_code
        techs = probe_result.technologies or []
        content_length = probe_result.content_length or 0

        if status == 403:
            tasks.append(ScanTask("403_BYPASS"))
        if "Jenkins" in techs:
            tasks.append(ScanTask("NUCLEI_SCAN", ["jenkins-cves"]))
        if "WordPress" in techs:
            tasks.append(ScanTask("WP_SCAN"))
        if status == 200 and content_length > 0:
            tasks.append(ScanTask("JS_ANALYSIS"))
        if status == 200:
            tasks.append(ScanTask("FUZZING"))

        return tasks
