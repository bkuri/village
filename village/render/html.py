"""HTML renderer for resume output."""

import logging

from village.contracts import ResumeContract, contract_to_dict

logger = logging.getLogger(__name__)


def render_resume_html(contract: ResumeContract) -> str:
    """
    Render resume contract as minimal HTML with JSON metadata.

    HTML format:
    ```html
    <pre>
    <script type="application/json" id="village-meta">
    {JSON metadata}
    </script>
    </pre>
    ```

    Args:
        contract: ResumeContract object

    Returns:
        HTML string with embedded JSON metadata
    """
    # Convert contract to dict and then format as JSON
    metadata = contract_to_dict(contract)

    # Format JSON with 2-space indentation
    import json

    json_metadata = json.dumps(metadata, sort_keys=True, indent=2)

    # Minimal HTML structure
    html = f"""<pre>
<script type="application/json" id="village-meta">
{json_metadata}
</script>
</pre>"""

    logger.debug(f"Generated HTML contract for task_id={contract.task_id}")
    return html
