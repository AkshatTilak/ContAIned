"""Unit tests for GuardRoute visual JSON graph parser and topology validator.
"""

import pytest
from projects.guardroute.src.core.graph_parser import GraphParser, GraphValidationError, parse_graph_json_to_langgraph


def test_graph_parser_valid_topology():
    graph_json = {
        "nodes": [
            {"id": "classify", "type": "ClassifierNode"},
            {"id": "retrieval", "type": "RetrievalNode"},
            {"id": "coding", "type": "CodingNode"},
            {"id": "gather", "type": "SynthesisNode"}
        ],
        "edges": [
            {"id": "e1", "source": "classify", "target": "retrieval"},
            {"id": "e2", "source": "classify", "target": "coding"},
            {"id": "e3", "source": "retrieval", "target": "gather"},
            {"id": "e4", "source": "coding", "target": "gather"}
        ]
    }

    parser = GraphParser(graph_json)
    assert parser.validate_graph() is True

    compiled_graph = parser.build_langgraph()
    assert compiled_graph is not None


def test_graph_parser_invalid_edge_node():
    graph_json = {
        "nodes": [
            {"id": "n1", "type": "ClassifierNode"}
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "non_existent_node"}
        ]
    }

    parser = GraphParser(graph_json)
    with pytest.raises(GraphValidationError, match="Edge references invalid node ID"):
        parser.validate_graph()


def test_graph_parser_cycle_detection():
    graph_json = {
        "nodes": [
            {"id": "n1", "type": "ClassifierNode"},
            {"id": "n2", "type": "AgentNode"}
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n1"}
        ]
    }

    parser = GraphParser(graph_json)
    with pytest.raises(GraphValidationError, match="Workflow graph contains an infinite cycle"):
        parser.validate_graph()


def test_graph_parser_convenience_function():
    graph_json = {
        "nodes": [
            {"id": "agent-1", "type": "AgentNode"},
            {"id": "gather-1", "type": "GatherNode"}
        ],
        "edges": [
            {"id": "e1", "source": "agent-1", "target": "gather-1"}
        ]
    }

    compiled = parse_graph_json_to_langgraph(graph_json)
    assert compiled is not None
