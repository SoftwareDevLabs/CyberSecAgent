from __future__ import annotations


class PipelineError(Exception):
    """Base class for all pipeline errors."""


class PipelineStageError(PipelineError):
    """Raised when a pipeline stage fails. Carries the stage number."""

    def __init__(self, message: str, stage: int) -> None:
        super().__init__(message)
        self.stage = stage


class SBOMGenerationError(PipelineStageError):
    def __init__(self, message: str) -> None:
        super().__init__(message, stage=1)


class CVEMatchingError(PipelineStageError):
    def __init__(self, message: str) -> None:
        super().__init__(message, stage=2)


class ReachabilityAnalysisError(PipelineStageError):
    def __init__(self, message: str) -> None:
        super().__init__(message, stage=3)


class ExploitEnrichmentError(PipelineStageError):
    def __init__(self, message: str) -> None:
        super().__init__(message, stage=4)


class ReportGenerationError(PipelineStageError):
    def __init__(self, message: str) -> None:
        super().__init__(message, stage=5)
