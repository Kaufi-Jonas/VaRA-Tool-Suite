"""Report module to create and handle trace event format files, e.g., created
with chrome tracing."""

import json
import typing as tp
from enum import Enum
from json import JSONDecodeError
from pathlib import Path

import numpy as np

from varats.report.report import BaseReport, ReportAggregate


class TraceEventType(Enum):
    """Enum to represent the different event types of trace format events,
    defined by the Trace Event Format specification."""

    value: str  # pylint: disable=invalid-name

    DURATION_EVENT_BEGIN = 'B'
    DURATION_EVENT_END = 'E'
    COMPLETE_EVENT = 'X'
    INSTANT_EVENT = 'i'
    COUNTER_EVENT = 'C'
    ASYNC_EVENT_START = 'b'
    ASYNC_EVENT_INSTANT = 'n'
    ASYNC_EVENT_END = 'e'
    FLOW_EVENT_START = 's'
    FLOW_EVENT_STEP = 't'
    FLOW_EVENT_END = 'f'
    SAMPLE_EVENT = 'P'

    @staticmethod
    def parse_event_type(raw_event_type: str) -> 'TraceEventType':
        """Parses a raw string that represents a trace-format event type and
        converts it to the corresponding enum value."""
        for trace_event_type in TraceEventType:
            if trace_event_type.value == raw_event_type:
                return trace_event_type

        raise LookupError("Could not find correct trace event type")

    def __str__(self) -> str:
        return str(self.value)


class TraceEvent():
    """Represents a trace event that was captured during the analysis of a
    target program."""

    def __init__(self, json_trace_event: tp.Dict[str, tp.Any]) -> None:
        self.__name = str(json_trace_event["name"])
        self.__category = str(json_trace_event["cat"])
        self.__event_type = TraceEventType.parse_event_type(
            json_trace_event["ph"]
        )
        self.__tracing_clock_timestamp = int(json_trace_event["ts"])
        self.__pid = int(json_trace_event["pid"])
        self.__tid = int(json_trace_event["tid"])

    @property
    def name(self) -> str:
        return self.__name

    @property
    def category(self) -> str:
        return self.__category

    @property
    def event_type(self) -> TraceEventType:
        return self.__event_type

    @property
    def timestamp(self) -> int:
        return self.__tracing_clock_timestamp

    @property
    def pid(self) -> int:
        return self.__pid

    @property
    def tid(self) -> int:
        return self.__tid

    def __str__(self) -> str:
        return f"""{{
    name: {self.name}
    cat: {self.category}
    ph: {self.event_type}
    ts: {self.timestamp}
    pid: {self.pid}
    tid: {self.tid}
}}
"""

    def __repr__(self) -> str:
        return str(self)


class TEFReport(BaseReport, shorthand="TEF", file_type="json"):
    """Report class to access trace event format files."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)

        with open(self.path, "r", encoding="utf-8") as json_tef_report:
            try:
                data = json.load(json_tef_report)
            except JSONDecodeError:
                print(f"Error while parsing JSON of report {self.filename}.")
                raise

            self.__display_time_unit = str(data["displayTimeUnit"])
            self.__trace_events = self._parse_trace_events(data["traceEvents"])
            # Parsing stackFrames is currently not implemented
            # x = data["stackFrames"]

    @property
    def display_time_unit(self) -> str:
        return self.__display_time_unit

    @property
    def trace_events(self) -> tp.List[TraceEvent]:
        return self.__trace_events

    @property
    def stack_frames(self) -> None:
        raise NotImplementedError(
            "Stack frame parsing is currently not implemented!"
        )

    @staticmethod
    def _parse_trace_events(
        raw_event_list: tp.List[tp.Dict[str, tp.Any]]
    ) -> tp.List[TraceEvent]:
        return [TraceEvent(data_item) for data_item in raw_event_list]


class TEFReportAggregate(
    ReportAggregate[TEFReport],
    shorthand=TEFReport.SHORTHAND + ReportAggregate.SHORTHAND,
    file_type=ReportAggregate.FILE_TYPE
):
    """Context Manager for parsing multiple TEF reports stored inside a zip
    file."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, TEFReport)

        # Compute wall clock times from start and end events of base feature.
        self._wall_clock_times: tp.List[float] = []
        for report in self.reports:
            error_base_text = "Feature 'Base' in report {}/{}".format(
                self.filename, report.filename
            )

            base_events = filter(
                lambda trace_event: trace_event.name == "Base",
                report.trace_events
            )

            # Find begin and end timestamps.
            time_start = None
            time_end = None

            for base_event in base_events:
                if base_event.event_type == TraceEventType.DURATION_EVENT_BEGIN:
                    time_start = base_event.timestamp
                elif base_event.event_type == TraceEventType.DURATION_EVENT_END:
                    time_end = base_event.timestamp
                else:
                    print(
                        error_base_text,
                        "contains unexpected event type '{}'".format(
                            base_event.event_type
                        )
                    )

            if time_start is None or time_end is None:
                print(
                    error_base_text, "is missing begin or end event. Skipping."
                )
                continue

            # Calculate execution time.
            execution_ticks = time_end - time_start
            if report.display_time_unit == "ms":
                execution_time = execution_ticks / 10**6
            elif report.display_time_unit == "ns":
                execution_time = execution_ticks / 10**9
            else:
                print(
                    error_base_text,
                    "has unexpected display time unit '{}'. Skipping.".format(
                        report.display_time_unit
                    )
                )
                continue

            self._wall_clock_times.append(execution_time)

        if not self._wall_clock_times:
            self._wall_clock_times.append(0)

    @property
    def wall_clock_times(self) -> tp.List[float]:
        """Wall clock times from all reports, computed through the base
        feature's start and end events."""
        return self._wall_clock_times

    @property
    def mean_std_wall_clock_times(self) -> tp.Tuple[float, float]:
        """Returns (mean, std)."""
        return (np.mean(self.ctx_switches), np.std(self.ctx_switches))

    @property
    def min_max_wall_clock_times(self) -> tp.Tuple[float, float]:
        """Returns (min, max)."""
        return (np.min(self.ctx_switches), np.max(self.ctx_switches))
