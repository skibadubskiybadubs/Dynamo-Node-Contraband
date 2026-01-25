#!/usr/bin/env python
"""Tool 6: Output Reader - Parse DynamoCLI XML output and extract node results.

Usage:
    dynamo-output-read output.xml                   # Show all outputs
    dynamo-output-read output.xml --node <guid>     # Show specific node output
    dynamo-output-read output.xml --json            # Output as JSON (default)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def infer_value_type(value: str) -> tuple[str, Any]:
    """Infer the type and convert value from string.

    Returns:
        Tuple of (type_name, converted_value).
    """
    if value == "null":
        return ("null", None)

    # Try number
    try:
        if "." in value:
            return ("number", float(value))
        else:
            return ("number", int(value))
    except ValueError:
        pass

    # Try list (simple detection)
    if value.startswith("[") and value.endswith("]"):
        return ("list", value)

    # Try dict/object
    if value.startswith("{") and value.endswith("}"):
        return ("object", value)

    # Try boolean
    if value.lower() == "true":
        return ("boolean", True)
    if value.lower() == "false":
        return ("boolean", False)

    # Default to string
    return ("string", value)


def parse_execution_xml(xml_path: str) -> Dict[str, Any]:
    """Parse DynamoCLI verbose output XML.

    Args:
        xml_path: Path to the XML file.

    Returns:
        Dict with parsed evaluation data.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    evaluations = []

    # Find all evaluation elements (evaluation0, evaluation1, etc.)
    for child in root:
        if child.tag.startswith("evaluation"):
            eval_num = child.tag.replace("evaluation", "")
            nodes = []

            for node_elem in child.findall("Node"):
                node_guid = node_elem.get("guid", "")
                outputs = []

                # Find all output elements (output0, output1, etc.)
                for output_elem in node_elem:
                    if output_elem.tag.startswith("output"):
                        output_idx = int(output_elem.tag.replace("output", ""))
                        raw_value = output_elem.get("value", "")
                        value_type, converted_value = infer_value_type(raw_value)

                        outputs.append({
                            "index": output_idx,
                            "raw_value": raw_value,
                            "value": converted_value,
                            "type": value_type
                        })

                # Sort outputs by index
                outputs.sort(key=lambda x: x["index"])

                nodes.append({
                    "guid": node_guid,
                    "outputs": outputs
                })

            evaluations.append({
                "evaluation_index": int(eval_num) if eval_num.isdigit() else 0,
                "nodes": nodes
            })

    # Sort evaluations by index
    evaluations.sort(key=lambda x: x["evaluation_index"])

    return {
        "evaluation_count": len(evaluations),
        "evaluations": evaluations
    }


def get_node_outputs(parsed_data: Dict[str, Any], node_guid: str,
                     evaluation_index: int = 0) -> Optional[Dict[str, Any]]:
    """Get outputs for a specific node from parsed data.

    Args:
        parsed_data: Parsed XML data.
        node_guid: GUID of the node to find.
        evaluation_index: Which evaluation to look in (default: 0).

    Returns:
        Node output data or None if not found.
    """
    if evaluation_index >= len(parsed_data["evaluations"]):
        return None

    evaluation = parsed_data["evaluations"][evaluation_index]
    for node in evaluation["nodes"]:
        if node["guid"] == node_guid:
            return node

    return None


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


@click.command()
@click.argument("xml_path", type=click.Path(exists=True))
@click.option("--node", "node_guid", help="Show specific node output by GUID")
@click.option("--evaluation", "eval_index", type=int, default=0, help="Evaluation index (default: 0)")
@click.option("--json", "as_json", is_flag=True, default=True, help="Output as JSON (default)")
def main(xml_path: str, node_guid: Optional[str], eval_index: int, as_json: bool):
    """Parse DynamoCLI XML output and extract node results.

    XML_PATH: Path to the verbose output XML file.
    """
    try:
        parsed = parse_execution_xml(xml_path)

        # Get specific node
        if node_guid:
            node_data = get_node_outputs(parsed, node_guid, eval_index)
            if not node_data:
                output_result({
                    "success": False,
                    "error": f"Node not found: {node_guid} in evaluation {eval_index}"
                })
                sys.exit(1)

            output_result({
                "success": True,
                "evaluation_index": eval_index,
                "node": node_data
            })
            return

        # Return all data
        output_result({
            "success": True,
            **parsed
        })

    except ET.ParseError as e:
        output_result({"success": False, "error": f"XML parse error: {e}"})
        sys.exit(1)
    except FileNotFoundError as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": f"Unexpected error: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
