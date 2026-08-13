
import pytest
pytestmark = pytest.mark.unit
"""Unit and integration tests for GuardRoute visual workflow graph parser and hub sync.
"""

import pytest
from projects.guardroute.src.core.graph_parser import GraphParser, GraphValidationError


def test_workflow_graph_parser_topology():
    graph_json = {
        "nodes": [
            {"id": "classify", "type": "ClassifierNode"},
            {"id": "gather", "type": "SynthesisNode"}
        ],
        "edges": [
            {"id": "e1", "source": "classify", "target": "gather"}
        ]
    }
    parser = GraphParser(graph_json)
    assert parser.validate_graph() is True


def test_workflow_graph_parser_invalid_topology():
    graph_json = {
        "nodes": [
            {"id": "n1", "type": "ClassifierNode"}
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "non_existent_node"}
        ]
    }
    parser = GraphParser(graph_json)
    with pytest.raises(GraphValidationError):
        parser.validate_graph()
