"""Locust performance test for agent-factory /invoke endpoint."""
from locust import HttpUser, task, between


class AgentFactoryUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def invoke(self):
        self.client.post(
            "/",
            json={
                "message": "What is the status?",
                "user_id": "perf-test-user",
                "session_id": "perf-sess-001",
            },
        )
