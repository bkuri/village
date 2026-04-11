"""Orchestrates running multiple analyzers."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from village.doctor.base import Analyzer, AnalyzerResult
from village.logging import get_logger

logger = get_logger(__name__)


def run_analyzers(
    analyzers: list[Analyzer],
    parallel: bool = True,
) -> list[AnalyzerResult]:
    """Run all analyzers and collect results."""
    results = []

    if parallel:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(a.run): a for a in analyzers}
            for future in as_completed(futures):
                analyzer = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Analyzer {analyzer.name} found {len(result.findings)} findings")
                except Exception as e:
                    logger.error(f"Analyzer {analyzer.name} failed: {e}")
                    results.append(
                        AnalyzerResult(
                            analyzer_name=analyzer.name,
                            analyzer_description=analyzer.description,
                            findings=[],
                            error=str(e),
                        )
                    )
    else:
        for analyzer in analyzers:
            try:
                result = analyzer.run()
                results.append(result)
            except Exception as e:
                logger.error(f"Analyzer {analyzer.name} failed: {e}")
                results.append(
                    AnalyzerResult(
                        analyzer_name=analyzer.name,
                        analyzer_description=analyzer.description,
                        findings=[],
                        error=str(e),
                    )
                )

    return results
