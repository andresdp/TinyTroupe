"""
:class:`ATAMReportGenerator` — aggregate phase outputs into an ATAM report.

Produces :class:`ATAMReport` dataclass instances and serializes them to JSON
or Markdown. The :meth:`generate` method depends on a fully-populated session;
the serialization methods (:meth:`to_json`, :meth:`to_markdown`, :meth:`to_dict`)
are pure data transformations and are implemented here.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from ..models import ATAMReport

if TYPE_CHECKING:
    from ..session.atam_session import ATAMSession


class ATAMReportGenerator:
    """Aggregate all phase outputs into a structured :class:`ATAMReport`."""

    def __init__(self, session: "ATAMSession") -> None:
        """Initialize the generator with a reference to the session.

        Args:
            session: The :class:`ATAMSession` whose accumulators will be
                aggregated into the report.
        """
        self.session = session

    def generate(self) -> ATAMReport:
        """Assemble an :class:`ATAMReport` from the session's accumulators.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMReportGenerator.generate is not yet implemented."
        )

    # ------------------------------------------------------------------
    # Serialization helpers (pure data transformation — fully implemented)
    # ------------------------------------------------------------------
    def to_dict(self, report: ATAMReport) -> dict:
        """Convert an :class:`ATAMReport` to a serializable dictionary.

        Args:
            report: The report to convert.

        Returns:
            A nested dictionary with all report fields, suitable for
            ``json.dumps``.
        """
        return {
            "project_name": report.project_name,
            "evaluation_date": report.evaluation_date,
            "business_drivers": report.business_drivers,
            "architecture_summary": report.architecture_summary,
            "stakeholders": list(report.stakeholders),
            "scenarios": [self._scenario_to_dict(s) for s in report.scenarios],
            "prioritized_scenarios": [
                self._scenario_to_dict(s) for s in report.prioritized_scenarios
            ],
            "approaches": [
                self._approach_to_dict(a) for a in report.approaches
            ],
            "concerns": [self._concern_to_dict(c) for c in report.concerns],
            "phase_summaries": dict(report.phase_summaries),
        }

    def to_json(self, report: ATAMReport, path: str) -> str:
        """Serialize *report* to a JSON file.

        Args:
            report: The report to serialize.
            path: File path for the output JSON.

        Returns:
            The path written to.
        """
        data = self.to_dict(report)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def to_markdown(self, report: ATAMReport, path: str) -> str:
        """Serialize *report* to a Markdown file.

        Args:
            report: The report to serialize.
            path: File path for the output Markdown.

        Returns:
            The path written to.
        """
        lines = [
            f"# ATAM Evaluation Report: {report.project_name}",
            "",
            f"**Evaluation Date:** {report.evaluation_date}",
            f"**Stakeholders:** {', '.join(report.stakeholders) if report.stakeholders else 'N/A'}",
            "",
            "## Business Drivers",
            "",
            report.business_drivers,
            "",
            "## Architecture Summary",
            "",
            report.architecture_summary,
            "",
        ]

        if report.scenarios or report.prioritized_scenarios:
            scenarios = report.prioritized_scenarios or report.scenarios
            lines.append("## Scenarios")
            lines.append("")
            for s in scenarios:
                priority = (
                    f" (priority: {s.priority_score:.2f})"
                    if s.priority_score is not None
                    else ""
                )
                lines.append(f"### {s.name}{priority}")
                lines.append("")
                lines.append(f"- **Quality Attribute:** {s.quality_attribute.value}")
                lines.append(f"- **Description:** {s.description}")
                lines.append(f"- **Stimulus Source:** {s.stimulus_source}")
                lines.append(f"- **Stimulus:** {s.stimulus}")
                lines.append(f"- **Environment:** {s.environment}")
                lines.append(f"- **Artifact:** {s.artifact}")
                lines.append(f"- **Response:** {s.response}")
                lines.append(f"- **Response Measure:** {s.response_measure}")
                lines.append("")

        if report.approaches:
            lines.append("## Architectural Approaches")
            lines.append("")
            for a in report.approaches:
                lines.append(f"### {a.name}")
                lines.append("")
                lines.append(f"{a.description}")
                lines.append("")
                if a.patterns:
                    lines.append(f"**Patterns:** {', '.join(a.patterns)}")
                if a.attributes_addressed:
                    attrs = ", ".join(qa.value for qa in a.attributes_addressed)
                    lines.append(f"**Attributes Addressed:** {attrs}")
                lines.append("")

        if report.concerns:
            lines.append("## Concerns (Risks, Tradeoffs, Sensitivity Points)")
            lines.append("")
            for c in report.concerns:
                lines.append(f"### [{c.type.value.upper()}] {c.description[:80]}")
                lines.append("")
                lines.append(f"- **Severity:** {c.severity or 'unspecified'}")
                if c.architectural_element:
                    lines.append(
                        f"- **Architectural Element:** {c.architectural_element}"
                    )
                if c.related_scenarios:
                    lines.append(
                        f"- **Related Scenarios:** {', '.join(c.related_scenarios)}"
                    )
                if c.mitigation:
                    lines.append(f"- **Mitigation:** {c.mitigation}")
                lines.append("")

        if report.phase_summaries:
            lines.append("## Phase Summaries")
            lines.append("")
            for phase_name, summary in report.phase_summaries.items():
                lines.append(f"### {phase_name}")
                lines.append("")
                lines.append(summary)
                lines.append("")

        lines.append(f"---\n*Generated by atamsim on {datetime.now().isoformat()}*")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _scenario_to_dict(self, scenario) -> dict:
        return {
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description,
            "stimulus_source": scenario.stimulus_source,
            "stimulus": scenario.stimulus,
            "environment": scenario.environment,
            "artifact": scenario.artifact,
            "response": scenario.response,
            "response_measure": scenario.response_measure,
            "quality_attribute": scenario.quality_attribute.value,
            "generated_by": scenario.generated_by,
            "priority_score": scenario.priority_score,
            "votes": dict(scenario.votes),
        }

    def _concern_to_dict(self, concern) -> dict:
        return {
            "id": concern.id,
            "type": concern.type.value,
            "description": concern.description,
            "related_scenarios": list(concern.related_scenarios),
            "related_attributes": [
                qa.value for qa in concern.related_attributes
            ],
            "architectural_element": concern.architectural_element,
            "severity": concern.severity,
            "mitigation": concern.mitigation,
            "identified_by": concern.identified_by,
        }

    def _approach_to_dict(self, approach) -> dict:
        return {
            "name": approach.name,
            "description": approach.description,
            "patterns": list(approach.patterns),
            "attributes_addressed": [
                qa.value for qa in approach.attributes_addressed
            ],
        }