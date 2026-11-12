import pytest


@pytest.fixture(scope="session")
def neo4j_url():
    from testcontainers.neo4j import Neo4jContainer

    with Neo4jContainer("neo4j:5.26-community", password="test-password") as c:
        yield c.get_connection_url()
