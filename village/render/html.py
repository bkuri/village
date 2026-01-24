"""HTML renderer for resume output."""

import json
import logging

from village.contracts import ContractEnvelope

logger = logging.getLogger(__name__)


def render_resume_html(contract: ContractEnvelope) -> str:
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
        contract: ContractEnvelope object

    Returns:
        HTML string with embedded JSON metadata
    """
    # Convert contract to JSON and then parse back to dict
    json_str = contract.to_json()
    metadata = json.loads(json_str)

    # Format JSON with 2-space indentation
    json_metadata = json.dumps(metadata, sort_keys=True, indent=2)

    # Minimal HTML structure
    html = f"""<pre>
<script type="application/json" id="village-meta">
{json_metadata}
</script>
</pre>"""

    logger.debug(f"Generated HTML contract for task_id={contract.task_id}")
    return html
